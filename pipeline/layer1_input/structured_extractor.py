"""
统一结构化提取器

跨格式（DOCX/TXT/Markdown）的结构化文档解析接口。
将各种来源的文档层级结构统一转换为 StructuredSection 树。
"""

import re
from models.slide_spec import StructuredSection, TableData


class StructuredExtractor:
    """
    统一的结构化提取接口。

    三种来源：
    1. DOCX段落样式（Heading1/2/3）→ 由 docx_parser 直接提取
    2. 章节编号（4.1, 4.2.1）→ 正则检测
    3. Markdown标题（# / ## / ###）→ 标记检测
    """

    # 章节编号模式：4.1, 4.2.1, 12.3 等
    _SECTION_HEADER = re.compile(r'^(\d+(?:\.\d+){1,3})\s+(.+)$', re.MULTILINE)

    # Markdown 标题模式
    _MD_HEADER = re.compile(r'^(#{1,6})\s+(.+)$', re.MULTILINE)

    def extract_from_text(self, text: str) -> list[StructuredSection]:
        """
        从纯文本中提取结构化章节。

        优先级：
        1. 编号章节头（4.1, 4.2.1）
        2. Markdown标题（## 标题）

        Returns:
            StructuredSection 列表（展平的），或空列表（无法检测结构时）
        """
        sections = self._extract_numbered_sections(text)
        if sections:
            return sections

        sections = self._extract_markdown_sections(text)
        return sections

    def _extract_numbered_sections(self, text: str) -> list[StructuredSection]:
        """从编号章节头（4.1, 4.2.1）提取结构"""
        matches = list(self._SECTION_HEADER.finditer(text))
        if len(matches) < 4:
            return []

        sections = []
        for i, match in enumerate(matches):
            section_num = match.group(1)
            title = match.group(2).strip()
            dot_count = section_num.count('.')
            level = dot_count  # 1=4.1, 2=4.2.1

            start = match.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            body = text[start:end].strip()

            # 跳过太短的章节（可能是子标题，无实质内容）
            if len(body) < 20 and sections:
                # 合并到前一个同级或父级章节
                for prev in reversed(sections):
                    if prev.level >= level:
                        prev.content += "\n\n" + section_num + " " + title + "\n" + body
                        prev.char_count = len(prev.content)
                        break
                continue

            sections.append(StructuredSection(
                title=title,
                level=level,
                content=body,
                char_count=len(body),
            ))

        return sections if len(sections) >= 4 else []

    def _extract_markdown_sections(self, text: str) -> list[StructuredSection]:
        """从Markdown标题提取结构"""
        matches = list(self._MD_HEADER.finditer(text))
        if len(matches) < 3:
            return []

        # 用 ## (h2) 作为主要分页级别
        h2_matches = [(m, len(m.group(1))) for m in matches]
        # 按最常见的标题级别分组
        level_counts = {}
        for _, level in h2_matches:
            level_counts[level] = level_counts.get(level, 0) + 1

        if not level_counts:
            return []

        # 选择数量最多且 >= 3 的标题级别作为分页级别
        best_level = min(level_counts, key=lambda l: (-level_counts[l], l))
        filtered = [(m, l) for m, l in h2_matches if l == best_level]

        if len(filtered) < 3:
            # 尝试用更高级别
            for l in sorted(level_counts):
                if level_counts[l] >= 3:
                    best_level = l
                    filtered = [(m, lv) for m, lv in h2_matches if lv <= l]
                    break

        if len(filtered) < 3:
            return []

        sections = []
        for i, (match, _) in enumerate(filtered):
            title = match.group(2).strip()
            start = match.end()
            end = filtered[i + 1][0].start() if i + 1 < len(filtered) else len(text)
            body = text[start:end].strip()

            if len(body) < 20 and sections:
                sections[-1].content += "\n\n" + "# " + title + "\n" + body
                sections[-1].char_count = len(sections[-1].content)
                continue

            sections.append(StructuredSection(
                title=title,
                level=1,
                content=body,
                char_count=len(body),
            ))

        return sections if len(sections) >= 3 else []

    def build_hierarchy(self, flat_sections: list[StructuredSection]) -> list[StructuredSection]:
        """
        将展平的章节列表组织为层级树。

        例如：
          [4.1(1), 4.2(1), 4.2.1(2), 4.2.2(2), 4.3(1)]
        → [4.1(1), 4.2(1, children=[4.2.1, 4.2.2]), 4.3(1)]
        """
        if not flat_sections:
            return []

        root_sections = []
        stack = []  # (section, level)

        for section in flat_sections:
            # 弹出栈中 level >= 当前的
            while stack and stack[-1][1] >= section.level:
                stack.pop()

            if stack:
                stack[-1][0].children.append(section)
            else:
                root_sections.append(section)

            stack.append((section, section.level))

        return root_sections

    def count_slides_from_sections(
        self,
        sections: list[StructuredSection],
        min_chars_per_slide: int = 300,
        max_chars_per_slide: int = 800,
    ) -> int:
        """
        根据章节内容量估算需要多少页slides。

        短章节（< min_chars）可能合并，长章节（> max_chars）可能拆分。
        """
        total = 0
        for section in sections:
            chars = section.total_char_count()
            if chars == 0:
                continue
            # 每个章节至少1页
            pages = max(1, round(chars / max_chars_per_slide))
            total += pages
            # 递归子章节
            total += self.count_slides_from_sections(
                section.children, min_chars_per_slide, max_chars_per_slide
            )
        return total
