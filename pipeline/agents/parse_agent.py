"""
ParseAgent — CodeAgent，无 LLM，纯代码解析输入文件。
包装现有 InputRouter 逻辑，输出标准化的 RawContent dict。
"""

from __future__ import annotations

from typing import Any, Dict

from .base import CodeAgent


class ParseAgent(CodeAgent):
    """解析输入文件/文本，返回序列化的 RawContent"""

    def run(self, context: Dict[str, Any]) -> Dict:
        from pipeline.layer1_input import InputRouter

        report = context.get("report_progress", lambda p, m: None)
        task = context["task"]

        report(6, "正在识别文件格式...")
        router = InputRouter()

        report(8, "正在解析文档结构...")
        if task.get("file_path"):
            raw_content = router.parse_file(task["file_path"])
        else:
            raw_content = router.parse_text(task.get("content", ""))

        report(13, "正在构建内容索引...")
        return {
            "source_type": raw_content.source_type,
            "text_length": len(raw_content.raw_text),
            "table_count": len(raw_content.tables),
            "image_count": len(raw_content.images),
            "detected_language": raw_content.detected_language,
            "raw_text_preview": raw_content.raw_text[:500],
            "tables": [
                {
                    "sheet": t.source_sheet,
                    "headers": t.headers,
                    "row_count": len(t.rows),
                }
                for t in raw_content.tables
            ],
            "_raw_text": raw_content.raw_text,
            "_tables": [
                {"headers": t.headers, "rows": t.rows, "source_sheet": t.source_sheet}
                for t in raw_content.tables
            ],
            "_images": [
                {"file_path": img.file_path, "description": img.description}
                for img in raw_content.images
            ],
            "_metadata": raw_content.metadata,
            "is_structured": raw_content.is_structured,
            "source_pages": [
                {"page_number": sp.page_number, "title": sp.title, "content": sp.content}
                for sp in raw_content.source_pages
            ],
            "structured_sections": [
                s.to_dict() for s in raw_content.structured_sections
            ],
        }
