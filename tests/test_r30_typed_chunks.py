"""Tests for R30 — Typed chunks: text/table/image + heading_path."""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestChunkTypedBasic:
    def test_text_chunks_produced(self):
        from pipeline.agents.analyze_agent import AnalyzeAgent
        blocks = [
            {"type": "heading", "text": "第一章", "heading_path": ["第一章"]},
            {"type": "paragraph", "text": "段落一。", "heading_path": ["第一章"]},
            {"type": "paragraph", "text": "段落二。", "heading_path": ["第一章"]},
        ]
        chunks = AnalyzeAgent._chunk_typed(blocks, [], [])
        assert len(chunks) == 1
        assert chunks[0]["type"] == "text"
        assert "段落一" in chunks[0]["text"]

    def test_heading_path_propagated(self):
        from pipeline.agents.analyze_agent import AnalyzeAgent
        blocks = [
            {"type": "heading", "text": "Ch1", "heading_path": ["Ch1"]},
            {"type": "heading", "text": "1.1 Sub", "heading_path": ["Ch1", "1.1 Sub"]},
            {"type": "paragraph", "text": "Content here.", "heading_path": ["Ch1", "1.1 Sub"]},
        ]
        chunks = AnalyzeAgent._chunk_typed(blocks, [], [])
        assert chunks[0]["heading_path"] == ["Ch1", "1.1 Sub"]

    def test_table_chunk_produced(self):
        from pipeline.agents.analyze_agent import AnalyzeAgent
        blocks = [
            {"type": "heading", "text": "Ch1", "heading_path": ["Ch1"]},
            {"type": "table", "text": "表格: A | B", "table_idx": 0, "heading_path": ["Ch1"]},
        ]
        tables = [{"headers": ["A", "B"], "rows": [["1", "2"]]}]
        chunks = AnalyzeAgent._chunk_typed(blocks, tables, [])
        assert len(chunks) == 1
        assert chunks[0]["type"] == "table"
        assert chunks[0]["table_data"] is not None
        assert chunks[0]["table_data"]["headers"] == ["A", "B"]

    def test_image_chunk_produced(self):
        from pipeline.agents.analyze_agent import AnalyzeAgent
        blocks = [
            {"type": "heading", "text": "Ch1", "heading_path": ["Ch1"]},
            {"type": "image", "text": "架构图", "image_idx": 0, "heading_path": ["Ch1"]},
        ]
        images = [{"file_path": "/tmp/img.png", "description": "架构图"}]
        chunks = AnalyzeAgent._chunk_typed(blocks, [], images)
        assert len(chunks) == 1
        assert chunks[0]["type"] == "image"
        assert chunks[0]["image_path"] == "/tmp/img.png"
        assert chunks[0]["image_caption"] == "架构图"

    def test_mixed_types(self):
        from pipeline.agents.analyze_agent import AnalyzeAgent
        blocks = [
            {"type": "heading", "text": "Ch1", "heading_path": ["Ch1"]},
            {"type": "paragraph", "text": "正文段落。", "heading_path": ["Ch1"]},
            {"type": "table", "text": "表格: X", "table_idx": 0, "heading_path": ["Ch1"]},
            {"type": "paragraph", "text": "更多正文。", "heading_path": ["Ch1"]},
            {"type": "image", "text": "图片", "image_idx": 0, "heading_path": ["Ch1"]},
        ]
        tables = [{"headers": ["X"], "rows": []}]
        images = [{"file_path": "/tmp/img.png", "description": ""}]
        chunks = AnalyzeAgent._chunk_typed(blocks, tables, images)
        types = [c["type"] for c in chunks]
        assert "text" in types
        assert "table" in types
        assert "image" in types

    def test_text_splits_at_heading_boundary(self):
        from pipeline.agents.analyze_agent import AnalyzeAgent
        blocks = [
            {"type": "heading", "text": "Ch1", "heading_path": ["Ch1"]},
            {"type": "paragraph", "text": "段落A。", "heading_path": ["Ch1"]},
            {"type": "heading", "text": "Ch2", "heading_path": ["Ch2"]},
            {"type": "paragraph", "text": "段落B。", "heading_path": ["Ch2"]},
        ]
        chunks = AnalyzeAgent._chunk_typed(blocks, [], [])
        assert len(chunks) == 2
        assert chunks[0]["heading_path"] == ["Ch1"]
        assert chunks[1]["heading_path"] == ["Ch2"]


class TestChunkTypedEdgeCases:
    def test_empty_blocks(self):
        from pipeline.agents.analyze_agent import AnalyzeAgent
        chunks = AnalyzeAgent._chunk_typed([], [], [])
        assert chunks == []

    def test_table_idx_out_of_range(self):
        from pipeline.agents.analyze_agent import AnalyzeAgent
        blocks = [
            {"type": "table", "text": "表格", "table_idx": 99, "heading_path": []},
        ]
        chunks = AnalyzeAgent._chunk_typed(blocks, [], [])
        assert len(chunks) == 1
        assert chunks[0]["table_data"] is None

    def test_legacy_chunk_still_works(self):
        """Verify old _chunk_document path still functions."""
        from pipeline.agents.analyze_agent import AnalyzeAgent
        pages = [
            {"title": "Ch1", "content": "A" * 100},
            {"title": "Ch2", "content": "B" * 100},
        ]
        chunks = AnalyzeAgent._chunk_document(pages)
        assert len(chunks) == 2
        assert all("type" not in c for c in chunks)  # legacy has no type field
