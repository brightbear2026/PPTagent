"""
Node.js html2pptx bridge — Python side

Connects to a persistent Node.js HTTP server (render_server.js) for
HTML→PPTX rendering, reusing a single Chromium browser across calls.
Falls back to per-render subprocess (html2pptx_wrapper.js) if the
server is unavailable.
"""

import atexit
import json
import logging
import os
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.request import Request, urlopen
from urllib.error import URLError

logger = logging.getLogger(__name__)

# Resolve paths relative to this file
_LAYER6_DIR = Path(__file__).parent
_WRAPPER_JS = _LAYER6_DIR / "html2pptx_wrapper.js"
_SERVER_JS = _LAYER6_DIR / "render_server.js"

DEFAULT_PORT = 19876


class NodeRenderBridge:
    """Python ↔ Node.js bridge for html2pptx rendering.

    Tries the persistent HTTP server first; falls back to subprocess mode.
    """

    def __init__(self, timeout_per_slide: int = 30):
        self.timeout_per_slide = timeout_per_slide
        self._node_cmd = self._find_node()
        self._port = int(os.environ.get("RENDER_PORT", DEFAULT_PORT))
        self._server_proc: Optional[subprocess.Popen] = None
        self._lock = threading.Lock()
        self._started = False

    @staticmethod
    def _find_node() -> str:
        for cmd in ("node", "nodejs"):
            try:
                result = subprocess.run(
                    [cmd, "--version"],
                    capture_output=True, text=True, timeout=5,
                )
                if result.returncode == 0:
                    logger.info("Found Node.js %s at '%s'", result.stdout.strip(), cmd)
                    return cmd
            except (FileNotFoundError, subprocess.TimeoutExpired):
                continue
        raise RuntimeError(
            "Node.js not found. Install Node.js and ensure 'node' is in PATH."
        )

    # ------------------------------------------------------------------
    # Persistent server lifecycle
    # ------------------------------------------------------------------

    def _ensure_server(self) -> bool:
        """Start the persistent server if not running. Returns True if server is ready."""
        if self._server_proc is not None and self._server_proc.poll() is None:
            if self._health_check():
                return True
            # Server process alive but unresponsive — kill and restart
            self._kill_server()

        try:
            self._start_server()
            return True
        except Exception as e:
            logger.warning("Failed to start render server, will use subprocess: %s", e)
            return False

    def _start_server(self):
        """Launch the persistent Node.js render server."""
        env = os.environ.copy()
        env["RENDER_PORT"] = str(self._port)

        self._server_proc = subprocess.Popen(
            [self._node_cmd, str(_SERVER_JS)],
            cwd=str(_LAYER6_DIR),
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )

        # Wait up to 10s for the server to become ready
        deadline = time.time() + 10
        while time.time() < deadline:
            if self._server_proc.poll() is not None:
                stderr = self._server_proc.stderr.read().decode() if self._server_proc.stderr else ""
                raise RuntimeError(f"render_server exited: {stderr[:500]}")
            if self._health_check():
                logger.info("render_server started on port %d", self._port)
                self._started = True
                return
            time.sleep(0.3)

        self._kill_server()
        raise RuntimeError("render_server did not become ready within 10s")

    def _kill_server(self):
        if self._server_proc and self._server_proc.poll() is None:
            try:
                self._server_proc.terminate()
                self._server_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._server_proc.kill()
            except Exception:
                pass
        self._server_proc = None

    def _health_check(self) -> bool:
        try:
            req = Request(f"http://127.0.0.1:{self._port}/health")
            with urlopen(req, timeout=2) as resp:
                data = json.loads(resp.read())
                return data.get("ok") is True
        except Exception:
            return False

    def _shutdown(self):
        """Graceful shutdown — called via atexit."""
        self._kill_server()

    # ------------------------------------------------------------------
    # Render — server mode
    # ------------------------------------------------------------------

    def _render_via_server(
        self, html_dir: str, output_path: str, layout: str,
    ) -> Dict[str, Any]:
        payload = json.dumps({
            "html_dir": html_dir,
            "output_path": output_path,
            "layout": layout,
        }).encode()

        req = Request(
            f"http://127.0.0.1:{self._port}/render",
            data=payload,
            headers={"Content-Type": "application/json"},
        )

        slide_count = len([f for f in os.listdir(html_dir) if f.endswith(".html")])
        timeout = max(60, self.timeout_per_slide * slide_count)

        logger.info("Rendering %d slides via render_server (timeout=%ds)", slide_count, timeout)

        try:
            with urlopen(req, timeout=timeout) as resp:
                body = resp.read()
                status = resp.status
        except URLError as e:
            raise RuntimeError(f"render_server request failed: {e}")

        data = json.loads(body)
        if status >= 400 or "error" in data:
            raise RuntimeError(f"render_server error: {data.get('error', data)}")

        return data

    # ------------------------------------------------------------------
    # Render — subprocess fallback
    # ------------------------------------------------------------------

    def _render_via_subprocess(
        self, html_dir: str, output_path: str, layout: str,
    ) -> Dict[str, Any]:
        html_dir = str(Path(html_dir).resolve())
        output_path = str(Path(output_path).resolve())

        slide_count = len([f for f in os.listdir(html_dir) if f.endswith(".html")])
        timeout = max(60, self.timeout_per_slide * slide_count)

        cmd = [self._node_cmd, str(_WRAPPER_JS), html_dir, output_path, layout]

        logger.info("Rendering %d slides via subprocess (timeout=%ds)", slide_count, timeout)

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(_LAYER6_DIR),
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError(
                f"Node.js rendering timed out after {timeout}s ({slide_count} slides)"
            )

        if result.returncode != 0:
            raise RuntimeError(f"html2pptx failed: {result.stderr.strip()}")

        try:
            data = json.loads(result.stdout.strip())
        except json.JSONDecodeError:
            raise RuntimeError(f"html2pptx returned invalid JSON: {result.stdout[:500]}")

        return data

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def render_slides(
        self,
        html_dir: str,
        output_path: str,
        layout: str = "LAYOUT_16x9",
    ) -> Dict[str, Any]:
        """Render all HTML slides in html_dir into a single .pptx file.

        Tries persistent server first, falls back to subprocess.
        """
        with self._lock:
            server_ok = self._ensure_server()

        if server_ok:
            try:
                data = self._render_via_server(html_dir, output_path, layout)
            except Exception as e:
                logger.warning("render_server failed, falling back to subprocess: %s", e)
                with self._lock:
                    self._kill_server()
                data = self._render_via_subprocess(html_dir, output_path, layout)
        else:
            data = self._render_via_subprocess(html_dir, output_path, layout)

        if data.get("errors"):
            for err in data["errors"]:
                logger.warning(
                    "Slide %d (%s) render error: %s",
                    err.get("slide_index", -1),
                    err.get("file", "?"),
                    err.get("error", "unknown"),
                )

        logger.info(
            "Rendered %d slides, %d placeholders, %d errors",
            data.get("slide_count", 0),
            sum(len(p.get("items", [])) for p in data.get("placeholders", [])),
            len(data.get("errors", [])),
        )

        return data

    def validate_single_slide(self, html_path: str) -> Dict[str, Any]:
        """Dry-run validate a single HTML slide via Node.js."""
        validate_js = _LAYER6_DIR / "html2pptx_validate.js"
        if not validate_js.exists():
            return {"ok": False, "errors": ["html2pptx_validate.js not found"]}

        cmd = [self._node_cmd, str(validate_js), str(Path(html_path).resolve())]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                cwd=str(_LAYER6_DIR),
            )
        except subprocess.TimeoutExpired:
            return {"ok": False, "errors": ["validation timed out (30s)"]}

        try:
            data = json.loads(result.stdout.strip())
            return {"ok": data.get("ok", False), "errors": data.get("errors", [])}
        except json.JSONDecodeError:
            return {"ok": False, "errors": [f"invalid validator output: {result.stdout[:200]}"]}


# Module-level singleton — shared across all pipeline runs in the same process
_bridge: Optional[NodeRenderBridge] = None
_bridge_lock = threading.Lock()


def get_bridge() -> NodeRenderBridge:
    """Get or create the shared NodeRenderBridge singleton."""
    global _bridge
    with _bridge_lock:
        if _bridge is None:
            _bridge = NodeRenderBridge()
            atexit.register(_bridge._shutdown)
        return _bridge


def is_node_available() -> bool:
    """Check if Node.js rendering is available."""
    try:
        get_bridge()
        return True
    except RuntimeError:
        return False
