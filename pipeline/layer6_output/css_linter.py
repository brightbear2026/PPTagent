"""
CSS Linter — Auto-fix LLM-generated HTML before html2pptx.js processing.

Enforces the PPT-safe CSS subset:
- Text elements must not have background/border/box-shadow
- Fonts must be from the web-safe + CJK whitelist
- Body must have fixed dimensions (960×540 for 16:9)
- No gradients, inset shadows, or forbidden elements
"""

import re
import logging
from typing import List, Tuple

logger = logging.getLogger(__name__)

FONT_WHITELIST = {
    "arial", "helvetica", "times new roman", "georgia",
    "courier new", "verdana", "tahoma", "trebuchet ms", "impact",
    "microsoft yahei", "simhei", "simsun", "pingfang sc",
}

FORBIDDEN_ELEMENTS = {"iframe", "video", "form", "canvas", "svg"}

TEXT_TAGS = {"p", "h1", "h2", "h3", "h4", "h5", "h6", "ul", "ol", "li", "span"}

GRADIENT_RE = re.compile(r'(linear|radial|conic)-gradient\s*\(', re.IGNORECASE)


class CSSLinter:
    """Pre-processes LLM HTML output to comply with html2pptx constraints."""

    def __init__(self, body_width: int = 960, body_height: int = 540):
        self.body_width = body_width
        self.body_height = body_height

    def fix(self, html: str) -> Tuple[str, List[str]]:
        """
        Auto-fix HTML and return (fixed_html, warnings).

        Fixes applied:
        1. Body dimensions enforced
        2. Text elements with bg/border/shadow wrapped in <div>
        3. Non-whitelisted fonts replaced
        4. Gradients removed from inline styles
        5. Forbidden elements removed
        """
        warnings: List[str] = []

        html = self._fix_body_dimensions(html, warnings)
        html = self._fix_gradients(html, warnings)
        html = self._remove_forbidden_elements(html, warnings)
        html = self._fix_text_element_styles(html, warnings)
        html = self._fix_fonts(html, warnings)

        return html, warnings

    def _fix_body_dimensions(self, html: str, warnings: List[str]) -> str:
        pattern = re.compile(r'(<body[^>]*?style=["\'])(.*?)(["\'])', re.DOTALL)

        def replacer(m):
            prefix, style, suffix = m.group(1), m.group(2), m.group(3)
            has_width = re.search(r'width\s*:', style)
            has_height = re.search(r'height\s*:', style)

            if has_width and has_height:
                style = re.sub(r'width\s*:\s*[\d.]+\s*px', f'width: {self.body_width}px', style)
                style = re.sub(r'height\s*:\s*[\d.]+\s*px', f'height: {self.body_height}px', style)
            else:
                style += f'; width: {self.body_width}px; height: {self.body_height}px'

            return f'{prefix}{style}{suffix}'

        result = pattern.sub(replacer, html)
        if result == html and '<body' in html:
            html = html.replace('<body', f'<body style="width: {self.body_width}px; height: {self.body_height}px;"', 1)
            warnings.append("Added missing body dimensions")
        return result if result != html else html

    def _fix_gradients(self, html: str, warnings: List[str]) -> str:
        def replacer(m):
            full_style = m.group(0)
            if GRADIENT_RE.search(full_style):
                warnings.append("Removed CSS gradient (not supported by html2pptx)")
                full_style = GRADIENT_RE.sub(
                    lambda _: '', full_style
                )
                # Clean up trailing semicolons/commas from removal
                full_style = re.sub(r';\s*;', ';', full_style)
                full_style = re.sub(r':\s*;', ';', full_style)
            return full_style

        return re.sub(r'style=["\'].*?["\']', replacer, html, flags=re.DOTALL)

    def _remove_forbidden_elements(self, html: str, warnings: List[str]) -> str:
        for tag in FORBIDDEN_ELEMENTS:
            pattern = re.compile(rf'<{tag}[^>]*>.*?</{tag}>', re.DOTALL | re.IGNORECASE)
            if pattern.search(html):
                warnings.append(f"Removed forbidden <{tag}> element")
                html = pattern.sub('', html)
            # Self-closing
            html = re.compile(rf'<{tag}[^>]*/?\s*>', re.IGNORECASE).sub('', html)
        return html

    def _fix_text_element_styles(self, html: str, warnings: List[str]) -> str:
        """Wrap text elements that have background/border/box-shadow in a <div>."""

        tag_pattern = '|'.join(TEXT_TAGS)
        text_elem_re = re.compile(
            rf'<({tag_pattern})(\s[^>]*)?style=["\']([^"\']*?)["\']([^>]*)>(.*?)</\1>',
            re.DOTALL | re.IGNORECASE
        )

        def replacer(m):
            tag = m.group(1)
            pre_style = m.group(2) or ''
            style = m.group(3)
            post_style = m.group(4) or ''
            content = m.group(5)

            has_bg = bool(re.search(r'background(-color)?\s*:', style, re.IGNORECASE))
            has_border = bool(re.search(r'border(-?(top|right|bottom|left|-width)?)?\s*:', style, re.IGNORECASE))
            has_shadow = bool(re.search(r'box-shadow\s*:', style, re.IGNORECASE))

            if not (has_bg or has_border or has_shadow):
                return m.group(0)

            # Strip problematic properties from text element
            clean_style = style
            for prop in ['background-color', 'background', 'border', 'border-top',
                         'border-right', 'border-bottom', 'border-left',
                         'border-width', 'border-color', 'border-style', 'box-shadow']:
                clean_style = re.sub(rf'{prop}\s*:\s*[^;]+;?', '', clean_style, flags=re.IGNORECASE)
            clean_style = re.sub(r';\s*;', ';', clean_style).strip('; ')

            warnings.append(
                f"Wrapped <{tag}> with bg/border/shadow in <div>"
            )

            return (
                f'<div style="{style}">'
                f'<{tag}{pre_style}'
                f'{"; " if clean_style else ""}'
                f' style="{clean_style}"{post_style}>'
                f'{content}</{tag}></div>'
            )

        return text_elem_re.sub(replacer, html)

    def _fix_fonts(self, html: str, warnings: List[str]) -> str:
        font_re = re.compile(
            r'font-family\s*:\s*["\']?([^;"\']+)["\']?',
            re.IGNORECASE
        )

        def replacer(m):
            font_list = m.group(1)
            fonts = [f.strip().strip('"\'') for f in font_list.split(',')]

            fixed = False
            fixed_fonts = []
            for f in fonts:
                if f.lower() in FONT_WHITELIST:
                    fixed_fonts.append(f)
                else:
                    if not fixed:
                        warnings.append(f"Replaced non-whitelisted font '{f}' with fallback")
                    fixed = True
                    fixed_fonts.append('"Microsoft Yahei", Arial')

            return f'font-family: {", ".join(fixed_fonts)}'

        return font_re.sub(replacer, html)

    def validate(self, html: str, page_weight: str = "") -> List[str]:
        """
        Check HTML for issues without modifying. Returns list of error messages.
        Empty list means the HTML should pass html2pptx.js validation.
        """
        errors: List[str] = []

        if GRADIENT_RE.search(html):
            errors.append("Contains CSS gradients (html2pptx.js will reject)")

        if not re.search(r'<body[^>]*width\s*:\s*\d+\s*px', html, re.IGNORECASE):
            errors.append("Body missing explicit width")

        if not re.search(r'<body[^>]*height\s*:\s*\d+\s*px', html, re.IGNORECASE):
            errors.append("Body missing explicit height")

        for tag in FORBIDDEN_ELEMENTS:
            if re.search(rf'<{tag}[\s>]', html, re.IGNORECASE):
                errors.append(f"Contains forbidden <{tag}> element")

        # Check text elements with problematic styles
        tag_pattern = '|'.join(TEXT_TAGS)
        text_with_bg = re.compile(
            rf'<({tag_pattern})[^>]*style=["\'][^"\']*?background(-color)?\s*:',
            re.IGNORECASE
        )
        if text_with_bg.search(html):
            errors.append("Text element has background (must be on <div> only)")

        # Content density check
        density_err = self._check_content_density(html, page_weight)
        if density_err:
            errors.append(density_err)

        return errors

    def _check_content_density(self, html: str, page_weight: str = "") -> str | None:
        """粗估内容面积占比。使用最大元素面积避免重复计数。超过阈值则 reject。"""
        total_area = self.body_width * self.body_height

        # Determine threshold by page_weight
        if page_weight == "hero":
            threshold = 0.45
        elif page_weight == "transition":
            threshold = 0.35
        else:
            threshold = 0.75

        # Strip body tag to avoid counting body dimensions
        inner = re.sub(r'<body[^>]*>', '', html, flags=re.IGNORECASE)
        inner = re.sub(r'</body>', '', inner, flags=re.IGNORECASE)

        # Collect all element areas, use the largest as content estimate
        max_area = 0
        for m in re.finditer(
            r'style=["\'][^"\']*?width\s*:\s*(\d+)\s*px[^"\']*?height\s*:\s*(\d+)\s*px',
            inner, re.IGNORECASE,
        ):
            w, h = int(m.group(1)), int(m.group(2))
            if w * h > max_area:
                max_area = w * h
        for m in re.finditer(
            r'style=["\'][^"\']*?height\s*:\s*(\d+)\s*px[^"\']*?width\s*:\s*(\d+)\s*px',
            inner, re.IGNORECASE,
        ):
            w, h = int(m.group(2)), int(m.group(1))
            if w * h > max_area:
                max_area = w * h

        # Fallback: estimate from character count
        if max_area == 0:
            text_chars = len(re.sub(r'<[^>]+>', '', inner).strip())
            if text_chars > 0:
                est_lines = (text_chars * 10) / self.body_width
                max_area = int(est_lines * 20 * self.body_width)

        ratio = max_area / total_area if total_area > 0 else 0
        if ratio > threshold:
            return f"Content density {ratio:.0%} exceeds {threshold:.0%} limit for {page_weight or 'default'} page"

        return None
