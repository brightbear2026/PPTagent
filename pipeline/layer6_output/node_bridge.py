"""
Node.js html2pptx bridge — Python side

Calls the Node.js html2pptx_wrapper.js to render HTML slides into a .pptx file,
then returns placeholder coordinates for chart injection.
"""

import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Resolve paths relative to this file
_LAYER6_DIR = Path(__file__).parent
_WRAPPER_JS = _LAYER6_DIR / "html2pptx_wrapper.js"


class NodeRenderBridge:
    """Python ↔ Node.js subprocess bridge for html2pptx rendering."""

    def __init__(self, timeout_per_slide: int = 30):
        self.timeout_per_slide = timeout_per_slide
        self._node_cmd = self._find_node()

    @staticmethod
    def _find_node() -> str:
        for cmd in ("node", "nodejs"):
            try:
                result = subprocess.run(
                    [cmd, "--version"],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    logger.info("Found Node.js %s at '%s'", result.stdout.strip(), cmd)
                    return cmd
            except (FileNotFoundError, subprocess.TimeoutExpired):
                continue
        raise RuntimeError(
            "Node.js not found. Install Node.js and ensure 'node' is in PATH."
        )

    def render_slides(
        self,
        html_dir: str,
        output_path: str,
        layout: str = "LAYOUT_16x9",
    ) -> Dict[str, Any]:
        """
        Render all HTML slides in html_dir into a single .pptx file.

        Args:
            html_dir: Directory containing slide_00.html, slide_01.html, ...
            output_path: Where to write the .pptx file
            layout: pptxgenjs layout name (default LAYOUT_16x9)

        Returns:
            {
                "output_file": str,
                "slide_count": int,
                "placeholders": [{"slide_index": int, "items": [...]}],
                "errors": [{"slide_index": int, "error": str}]
            }
        """
        html_dir = str(Path(html_dir).resolve())
        output_path = str(Path(output_path).resolve())

        slide_count = len([
            f for f in os.listdir(html_dir) if f.endswith(".html")
        ])
        timeout = max(60, self.timeout_per_slide * slide_count)

        cmd = [self._node_cmd, str(_WRAPPER_JS), html_dir, output_path, layout]

        logger.info("Rendering %d slides via Node.js (timeout=%ds)", slide_count, timeout)

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
                f"Node.js rendering timed out after {timeout}s "
                f"({slide_count} slides)"
            )

        if result.returncode != 0:
            stderr = result.stderr.strip()
            raise RuntimeError(f"html2pptx failed: {stderr}")

        try:
            data = json.loads(result.stdout.strip())
        except json.JSONDecodeError:
            raise RuntimeError(
                f"html2pptx returned invalid JSON: {result.stdout[:500]}"
            )

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
        """
        Dry-run validate a single HTML slide via Node.js.
        Returns {"ok": bool, "errors": [str]}.
        """
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


def is_node_available() -> bool:
    """Check if Node.js rendering is available."""
    try:
        NodeRenderBridge()
        return True
    except RuntimeError:
        return False
