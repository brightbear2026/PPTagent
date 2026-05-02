"""Detects prefix-of-superset duplicate text in LLM-generated HTML.

When LLM fills the same takeaway into multiple slots (e.g. headline + body),
one slot truncates to fit width and becomes a strict prefix of the other.
This module detects that pattern post-LLM, before commit to render.
"""
import re
from typing import Optional
from bs4 import BeautifulSoup


def detect_dup_prefix(
    html: str,
    min_short: int = 5,
    max_short: int = 30,
    ratio: float = 1.3,
) -> Optional[str]:
    """Return error message if any text node is a strict short prefix of another.

    Args:
        html: rendered HTML string
        min_short: shortest text to consider as potentially-truncated
        max_short: longest text to consider as headline-truncation
        ratio: long/short length ratio threshold (long must be > ratio x short)

    Returns:
        None if no duplicate detected. Error string otherwise (suitable for
        injection into LLM retry prompt).
    """
    texts = [t.strip() for t in BeautifulSoup(html, "html.parser").stripped_strings]
    texts = [t for t in texts if len(t) >= min_short]
    seen = set()
    for short in texts:
        if not (min_short <= len(short) <= max_short):
            continue
        for long in texts:
            if long is short or len(long) < len(short) * ratio:
                continue
            if long.startswith(short):
                pair = (short, long[:80])
                if pair in seen:
                    continue
                seen.add(pair)
                return (
                    f"Detected duplicate text: '{short}' is a prefix of "
                    f"'{long[:50]}...'. The same takeaway must not be "
                    f"filled into two text slots. Use distinct content "
                    f"per slot, or use a stat_highlight visual_block "
                    f"with separate title/value/description fields."
                )
    return None


def detect_exact_duplicate(html: str, min_len: int = 20) -> Optional[str]:
    """Return error message if any two identical text nodes ≥ min_len chars.

    Normalizes text by stripping whitespace and punctuation before comparison.
    Catches cases where LLM fills the exact same text into two slots (e.g. P4/P6
    in v8 both had identical 80-char takeaway text).

    Returns:
        None if clean. Error string if duplicate found.
    """
    texts = [t.strip() for t in BeautifulSoup(html, "html.parser").stripped_strings]

    def _normalize(s: str) -> str:
        return re.sub(r'\s+', '', s)

    normalized = [(t, _normalize(t)) for t in texts if len(t) >= min_len]

    seen: dict[str, str] = {}
    for original, norm in normalized:
        if norm in seen:
            return (
                f"Detected exact duplicate text: '{original[:60]}' appears "
                f"at least twice on this slide. Each text slot must contain "
                f"distinct content — do not repeat the same takeaway or "
                f"takeaway_message in multiple positions."
            )
        seen[norm] = original
    return None
