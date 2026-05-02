"""
HTML density check — enforce H6 (≥8 visible elements, no placeholder chars).

Used by html_design_agent after _enforce_dup_prefix_guard to catch sparse
layouts before they reach the renderer.
"""
import re
from typing import Optional


_FORBIDDEN_PLACEHOLDERS = {"<>", "◇", "□", "—", "–", "N/A", "TBD", "N/A"}
_CONTENT_TAGS = {"p", "h1", "h2", "h3", "h4", "li", "span"}


def detect_sparse(html: str, min_visible: int = 8) -> Optional[str]:
    """Returns error msg if HTML has too few visible content elements.

    Counts elements in _CONTENT_TAGS that have non-empty text content.
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    visible = [
        el for el in soup.find_all(_CONTENT_TAGS)
        if el.get_text(strip=True)
    ]
    if len(visible) < min_visible:
        return (
            f"Sparse layout: only {len(visible)} visible elements "
            f"(need ≥{min_visible})"
        )
    return None


def detect_placeholder_char(html: str) -> Optional[str]:
    """Returns error msg if any large-font element contains a forbidden placeholder."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    for el in soup.find_all(["h1", "h2", "h3", "p", "span"]):
        text = el.get_text(strip=True)
        if text not in _FORBIDDEN_PLACEHOLDERS:
            continue
        style = el.get("style", "")
        m = re.search(r"font-size:\s*(\d+)", style)
        if m and int(m.group(1)) >= 24:
            return (
                f"Forbidden placeholder char {text!r} at "
                f"fontSize={m.group(1)}px"
            )
    return None
