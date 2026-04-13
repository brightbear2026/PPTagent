"""
Layer 1: Markdown解析器
使用mistune将Markdown解析为AST，提取标题层级、列表、表格、代码块
"""

from pathlib import Path
import re
from typing import Optional
from models import RawContent, TableData

try:
    import mistune
except ImportError:
    mistune = None


class MarkdownParser:
    """Markdown文件解析器"""

    def __init__(self):
        if mistune is None:
            raise ImportError("mistune未安装，请运行: pip install mistune")

    def parse(self, file_path: str) -> RawContent:
        """
        解析Markdown文件

        Args:
            file_path: Markdown文件路径

        Returns:
            RawContent对象
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")

        content = path.read_text(encoding="utf-8", errors="replace")

        # 提取表格（在AST解析前，用正则匹配原始表格文本）
        tables = self._extract_tables(content)

        # 用mistune解析AST，构建结构化文本
        structured_text = self._build_structured_text(content)

        # 语言检测
        language = self._detect_language(content)

        # 元数据
        metadata = self._extract_metadata(path, content)

        return RawContent(
            source_type="markdown",
            raw_text=structured_text,
            tables=tables,
            images=[],
            metadata=metadata,
            detected_language=language,
        )

    def _build_structured_text(self, content: str) -> str:
        """用mistune解析Markdown AST，构建结构化纯文本"""
        md = mistune.create_markdown(renderer='ast')
        ast = md(content)

        parts: list[str] = []
        for node in ast:
            node_type = node.get("type", "")

            if node_type == "heading":
                level = node.get("attrs", {}).get("level", 1)
                text = self._extract_text(node.get("children", []))
                parts.append(f"{'#' * level} {text}")

            elif node_type == "paragraph":
                text = self._extract_text(node.get("children", []))
                if text:
                    parts.append(text)

            elif node_type == "list":
                items = self._extract_list_items(node)
                parts.extend(items)

            elif node_type == "block_code":
                code = node.get("raw", "").strip()
                info = node.get("attrs", {}).get("info", "")
                lang_marker = f"[CODE:{info}]" if info else "[CODE]"
                parts.append(f"{lang_marker}\n{code}\n[END CODE]")

            elif node_type == "block_html":
                raw = node.get("raw", "").strip()
                if raw:
                    parts.append(raw)

            elif node_type == "thematic_break":
                parts.append("---")

            elif node_type == "table":
                # 表格已在_extract_tables中处理，这里添加占位标记
                parts.append("[TABLE]")

            elif node_type == "quote":
                text = self._extract_text(node.get("children", []))
                if text:
                    parts.append(f"> {text}")

        return "\n\n".join(parts)

    def _extract_text(self, children: list) -> str:
        """递归提取AST节点的纯文本"""
        if not children:
            return ""

        parts: list[str] = []
        for child in children:
            child_type = child.get("type", "")
            if child_type == "text":
                parts.append(child.get("raw", ""))
            elif child_type in ("codespan",):
                parts.append(f"`{child.get('raw', '')}`")
            elif child_type in ("emphasis", "strong", "link"):
                parts.append(self._extract_text(child.get("children", [])))
            elif child_type == "softbreak":
                parts.append("\n")
            elif child_type == "blank_line":
                pass
            else:
                parts.append(self._extract_text(child.get("children", [])))
        return "".join(parts)

    def _extract_list_items(self, node: dict) -> list[str]:
        """提取列表项"""
        items: list[str] = []
        children = node.get("children", [])
        ordered = node.get("attrs", {}).get("ordered", False)

        for i, item in enumerate(children):
            if item.get("type") == "list_item":
                text = self._extract_text(item.get("children", []))
                prefix = f"{i + 1}." if ordered else "-"
                items.append(f"{prefix} {text}")

        return items

    def _extract_tables(self, content: str) -> list[TableData]:
        """
        从原始Markdown文本中提取表格，转换为TableData
        mistune的AST渲染器对表格处理不够直观，直接用正则匹配原始文本
        """
        tables: list[TableData] = []
        lines = content.split("\n")
        i = 0
        table_index = 0

        while i < len(lines):
            line = lines[i].strip()

            # 检测表格开始：至少有|分隔符的行
            if "|" in line and i + 1 < len(lines):
                # 收集连续的表格行
                table_lines: list[str] = []
                while i < len(lines) and "|" in lines[i].strip():
                    table_lines.append(lines[i].strip())
                    i += 1

                if len(table_lines) >= 2:
                    table = self._parse_table_lines(table_lines, table_index)
                    if table:
                        tables.append(table)
                        table_index += 1
                continue

            i += 1

        return tables

    def _parse_table_lines(self, lines: list[str], index: int) -> Optional[TableData]:
        """解析Markdown表格行为TableData"""
        if len(lines) < 2:
            return None

        # 解析行
        rows: list[list[str]] = []
        for line in lines:
            # 跳过分隔行 (如 |---|---|)
            stripped = line.strip()
            if re.match(r"^[\|\s\-:]+$", stripped):
                continue

            cells = [cell.strip() for cell in stripped.split("|")]
            # 去掉首尾空元素（由前后|产生）
            if cells and cells[0] == "":
                cells = cells[1:]
            if cells and cells[-1] == "":
                cells = cells[:-1:]

            if cells:
                rows.append(cells)

        if not rows:
            return None

        # 第一行作为表头
        headers = rows[0]
        data_rows = rows[1:] if len(rows) > 1 else []

        # markdown格式文本
        header_line = "| " + " | ".join(headers) + " |"
        sep_line = "| " + " | ".join("---" for _ in headers) + " |"
        data_lines = ["| " + " | ".join(row) + " |" for row in data_rows]
        raw_text = "\n".join([header_line, sep_line] + data_lines)

        return TableData(
            headers=headers,
            rows=data_rows,
            source_sheet=f"table_{index}",
        )

    def _detect_language(self, text: str) -> str:
        """检测文本主要语言"""
        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff' or '\u3400' <= c <= '\u4dbf')
        ratio = chinese_chars / max(len(text), 1)

        if ratio > 0.15:
            return "zh"
        elif ratio > 0.05:
            return "mixed"
        return "en"

    def _extract_metadata(self, path: Path, content: str) -> dict:
        """提取文件元数据"""
        metadata = {
            "file_name": path.name,
            "file_size": path.stat().st_size,
            "char_count": len(content),
            "line_count": content.count("\n") + 1,
        }

        # 提取YAML front matter（如果有）
        if content.startswith("---"):
            end = content.find("---", 3)
            if end != -1:
                front_matter = content[3:end].strip()
                for line in front_matter.split("\n"):
                    if ":" in line:
                        key, _, value = line.partition(":")
                        metadata[f"front_{key.strip()}"] = value.strip()

        return metadata
