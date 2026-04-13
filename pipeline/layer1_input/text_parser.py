"""
纯文本解析器 + 语言检测
将纯文本输入转换为RawContent对象
"""

import re
from models import RawContent


class TextParser:
    """纯文本解析器，包含语言自动检测"""

    # CJK Unified Ideographs 范围
    _CJK_PATTERN = re.compile(r'[\u4e00-\u9fff\u3400-\u4dbf]')

    def parse(self, text: str, metadata: dict = None) -> RawContent:
        """
        解析纯文本为RawContent

        Args:
            text: 原始文本
            metadata: 可选的额外元数据

        Returns:
            RawContent with source_type="text"
        """
        detected_lang = self._detect_language(text)

        meta = {
            "char_count": len(text),
            "line_count": text.count('\n') + 1,
        }
        if metadata:
            meta.update(metadata)

        return RawContent(
            source_type="text",
            raw_text=text,
            detected_language=detected_lang,
            metadata=meta,
        )

    def _detect_language(self, text: str) -> str:
        """
        检测文本语言

        规则：
        - 中文字符占比 > 15% → "zh"
        - 中文字符占比 > 5% → "mixed"
        - 否则 → "en"
        """
        if not text.strip():
            return "zh"  # 默认中文

        # 统计中文字符
        cjk_count = len(self._CJK_PATTERN.findall(text))

        # 统计有意义的字符（排除空白和标点）
        meaningful = re.sub(r'[\s\W]+', '', text)
        total = max(len(meaningful), 1)

        ratio = cjk_count / total

        if ratio > 0.15:
            return "zh"
        elif ratio > 0.05:
            return "mixed"
        else:
            return "en"
