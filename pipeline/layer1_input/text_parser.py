"""
纯文本解析器 + 语言检测 + 页面结构检测
将纯文本输入转换为RawContent对象
"""

import re
from models import RawContent, SourcePage


class TextParser:
    """纯文本解析器，包含语言自动检测和页面结构检测"""

    # CJK Unified Ideographs 范围
    _CJK_PATTERN = re.compile(r'[\u4e00-\u9fff\u3400-\u4dbf]')

    # 页面结构检测模式（按优先级排序）
    _PAGE_PATTERNS = [
        # "第N页：" 或 "第N页:"
        re.compile(r'第(\d+)页[：:]'),
        # "Page N" / "page N" / "PAGE N"
        re.compile(r'[Pp]age\s+(\d+)'),
        # "Slide N" / "slide N"
        re.compile(r'[Ss]lide\s+(\d+)'),
        # "P N" 独占一行
        re.compile(r'^P\s*(\d+)\s*$', re.MULTILINE),
        # Markdown 标题 "---" 分隔 + "# N." 模式
        re.compile(r'^#{1,2}\s+\d+[\.、]\s*', re.MULTILINE),
    ]

    # 章节编号模式：4.1, 4.2.1, 12.3 等
    _SECTION_HEADER = re.compile(r'^(\d+(?:\.\d+){1,3})\s+(.+)$', re.MULTILINE)

    # 中文编号模式：一、二、三...十一、十二...
    _CN_NUMERAL = r'([一二三四五六七八九十]+)、\s*(.+)'
    _CN_NUMERAL_RE = re.compile(r'^' + _CN_NUMERAL + r'$', re.MULTILINE)

    # 中文括号编号：（一）、（二）、（三）...
    _CN_PAREN = re.compile(r'^（([一二三四五六七八九十]+)）\s*(.*)$', re.MULTILINE)

    # 阿拉伯数字编号：1. 2. 3.（带句点，独立行）
    _ARABIC_DOT = re.compile(r'^(\d+)\.\s+(.+)$', re.MULTILINE)

    # 括号阿拉伯编号：(1) (2) (3)
    _ARABIC_PAREN = re.compile(r'^[(（](\d+)[)）]\s*(.*)$', re.MULTILINE)

    # Markdown 标题模式
    _MARKDOWN_HEADER = re.compile(r'^(#{1,4})\s+(.+)$', re.MULTILINE)

    def parse(self, text: str, metadata: dict = None) -> RawContent:
        """
        解析纯文本为RawContent，自动检测页面结构
        """
        detected_lang = self._detect_language(text)
        source_pages, is_structured = self._detect_page_structure(text)

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
            source_pages=source_pages,
            is_structured=is_structured,
        )

    def detect_structure(self, text: str) -> tuple[list[SourcePage], bool]:
        """
        公开方法：检测文本结构，返回 (source_pages, is_structured)。
        供 DocxParser 等外部调用者使用。
        """
        return self._detect_page_structure(text)

    def _detect_page_structure(self, text: str) -> tuple[list[SourcePage], bool]:
        """
        检测文本是否已按页/章节组织。
        策略优先级：
        1. 显式页码标记（第N页、Page N、Slide N）
        2. 编号章节头（4.1、4.2.1 等）
        3. Markdown 标题层级（#、##、###）
        """
        # 策略1：显式页码
        for pattern in self._PAGE_PATTERNS:
            matches = list(pattern.finditer(text))
            if len(matches) >= 5:
                pages = self._extract_pages(text, matches, pattern)
                if len(pages) >= 5:
                    return pages, True

        # 策略2：编号章节头
        section_pages = self._detect_section_structure(text)
        if section_pages:
            return section_pages, True

        # 策略3：Markdown 标题
        md_pages = self._detect_markdown_structure(text)
        if md_pages:
            return md_pages, True

        return [], False

    def _detect_section_structure(self, text: str) -> list[SourcePage]:
        """
        检测编号章节结构。
        依次尝试多种编号模式，返回 SourcePage 列表或空列表。
        当顶级章节太少时，自动降级到子级编号以保留更多内容。

        支持的模式（按优先级）：
        1. 阿拉伯多级编号：4.1, 4.2.1, 12.3
        2. 中文大写编号：一、二、三、十一、十二
        3. 中文括号编号：（一）、（二）、（三）
        4. 阿拉伯点编号：1. 2. 3.
        """
        # 策略1：阿拉伯多级编号
        result = self._try_arabic_multilevel(text)
        if result and len(result) >= 3:
            return result

        # 策略2：中文大写编号（一、二、三）
        cn_result = self._try_cn_numeral(text)

        # 策略3：中文括号编号（（一）、（二））
        paren_result = self._try_cn_paren(text)

        # 如果中文大写编号太少（<4），优先用括号编号（更细粒度）
        if paren_result and len(paren_result) >= 3:
            if not cn_result or len(cn_result) < 4:
                return paren_result
        if cn_result and len(cn_result) >= 2:
            return cn_result

        # 策略4：阿拉伯点编号
        result = self._try_arabic_dot(text)
        if result:
            return result

        return []

    def _try_arabic_multilevel(self, text: str) -> list[SourcePage]:
        """检测阿拉伯多级编号：4.1, 4.2.1, 12.3"""
        matches = list(self._SECTION_HEADER.finditer(text))
        if len(matches) < 3:
            return []

        level_groups: dict[int, list] = {}
        for m in matches:
            dot_count = m.group(1).count('.')
            level_groups.setdefault(dot_count, []).append(m)

        best_matches = level_groups.get(1, [])
        if len(best_matches) < 3 and 2 in level_groups:
            best_matches = level_groups[2]
        if len(best_matches) < 3:
            best_matches = sorted(matches, key=lambda m: m.start())

        if len(best_matches) < 3:
            return []

        # 确保只用顶级章节
        top_level = level_groups.get(1, [])
        if len(top_level) >= 3:
            best_matches = top_level
        else:
            best_matches = self._select_section_matches(text, matches)

        if len(best_matches) < 3:
            return []

        return self._matches_to_pages(text, sorted(best_matches, key=lambda m: m.start()))

    def _try_cn_numeral(self, text: str) -> list[SourcePage]:
        """检测中文大写编号：一、二、三、十一、十二"""
        matches = list(self._CN_NUMERAL_RE.finditer(text))
        if len(matches) < 2:
            return []

        return self._matches_to_pages(text, matches)

    def _try_cn_paren(self, text: str) -> list[SourcePage]:
        """检测中文括号编号：（一）、（二）、（三）"""
        matches = list(self._CN_PAREN.finditer(text))
        if len(matches) < 2:
            return []

        return self._matches_to_pages(text, matches)

    def _try_arabic_dot(self, text: str) -> list[SourcePage]:
        """检测阿拉伯点编号：1. 2. 3.（需 >= 4 个）"""
        matches = list(self._ARABIC_DOT.finditer(text))
        if len(matches) < 4:
            return []

        # 过滤：排除数字太大的（可能是编号列表而非章节）
        nums = [int(m.group(1)) for m in matches]
        if max(nums) > 100:
            return []

        return self._matches_to_pages(text, matches)

    def _matches_to_pages(self, text: str, matches: list) -> list[SourcePage]:
        """将正则匹配结果转换为 SourcePage 列表"""
        if len(matches) < 2:
            return []

        pages = []
        for i, match in enumerate(matches):
            start = match.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            body = text[start:end].strip()

            # 跳过内容太短的页面（合并到上一页）
            if len(body) < 30 and pages:
                pages[-1] = SourcePage(
                    title=pages[-1].title,
                    content=pages[-1].content + "\n\n" + match.group(0) + "\n" + body,
                    page_number=pages[-1].page_number,
                )
                continue

            # 取最后一个捕获组作为标题
            title = match.group(match.lastindex).strip()[:80]
            pages.append(SourcePage(
                title=title,
                content=match.group(0) + "\n" + body,
                page_number=len(pages) + 1,
            ))

        return pages

    def _select_section_matches(self, text: str, all_matches: list) -> list:
        """
        从所有章节匹配中，选择作为分页点的匹配项。
        策略：顶级章节总是分页；次级章节当内容超过200字时分页。
        """
        selected = []
        for i, m in enumerate(all_matches):
            section_num = m.group(1)
            dot_count = section_num.count('.')

            # 顶级章节（如 4.1）总是选中
            if dot_count == 1:
                selected.append(m)
                continue

            # 次级章节（如 4.2.1）：检查后续内容长度
            end = all_matches[i + 1].start() if i + 1 < len(all_matches) else len(text)
            content_len = end - m.end()
            if content_len >= 100:  # 有实质内容
                selected.append(m)

        return selected

    def _detect_markdown_structure(self, text: str) -> list[SourcePage]:
        """
        检测 Markdown 标题结构。
        使用 ## (h2) 级别作为分页点。
        """
        matches = list(self._MARKDOWN_HEADER.finditer(text))
        if len(matches) < 4:
            return []

        # 按 ## (h2) 级别分页
        h2_matches = [m for m in matches if len(m.group(1)) == 2]
        if len(h2_matches) < 4:
            # 降级到 # (h1)
            h1_matches = [m for m in matches if len(m.group(1)) == 1]
            if len(h1_matches) >= 3:
                h2_matches = h1_matches

        if len(h2_matches) < 3:
            return []

        pages = []
        for i, match in enumerate(h2_matches):
            start = match.end()
            end = h2_matches[i + 1].start() if i + 1 < len(h2_matches) else len(text)
            body = text[start:end].strip()

            if len(body) < 30 and pages:
                pages[-1] = SourcePage(
                    title=pages[-1].title,
                    content=pages[-1].content + "\n\n" + match.group(0) + "\n" + body,
                    page_number=pages[-1].page_number,
                )
                continue

            title = match.group(2).strip()[:80]
            pages.append(SourcePage(
                title=title,
                content=match.group(0) + "\n" + body,
                page_number=len(pages) + 1,
            ))

        return pages if len(pages) >= 3 else []

    def _extract_pages(self, text: str, matches: list, pattern) -> list[SourcePage]:
        """按匹配的页面标记拆分文本"""
        pages = []
        for i, match in enumerate(matches):
            # 当前标记到下一个标记之间的文本
            start = match.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            body = text[start:end].strip()

            # 标题：取标记后面的第一个非空行
            first_line = ""
            for line in body.split('\n'):
                line = line.strip()
                if line:
                    first_line = line[:80]
                    break

            # 页码
            page_num = i + 1
            try:
                page_num = int(match.group(1))
            except (IndexError, ValueError):
                pass

            pages.append(SourcePage(
                title=first_line,
                content=body,
                page_number=page_num,
            ))

        return pages

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
