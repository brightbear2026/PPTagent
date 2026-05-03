"""Tests for R26 — ContentAgent chunks text mandatory injection."""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestResolveChunksSource:
    def test_bound_chunks_resolved(self):
        from pipeline.agents.content_agent import ContentAgent
        slide = {"chunk_ids": ["c1", "c2"]}
        shared = {
            "chunks": [
                {"id": "c1", "type": "text", "text": "这是第一个chunk的内容。", "section": "第一章"},
                {"id": "c2", "type": "table", "text": "表格摘要", "section": "第一章"},
                {"id": "c3", "type": "text", "text": "不相关的chunk"},
            ],
        }
        result = ContentAgent._resolve_chunks_source(slide, shared)
        assert "第一个chunk" in result
        assert "[text chunk c1" in result
        assert "[table chunk c2" in result
        assert "不相关的chunk" not in result
        assert "第一章" in result

    def test_empty_chunk_ids_returns_empty(self):
        from pipeline.agents.content_agent import ContentAgent
        result = ContentAgent._resolve_chunks_source({"chunk_ids": []}, {"chunks": []})
        assert result == ""

    def test_no_matching_chunks_returns_empty(self):
        from pipeline.agents.content_agent import ContentAgent
        slide = {"chunk_ids": ["c99"]}
        shared = {"chunks": [{"id": "c1", "text": "text"}]}
        assert ContentAgent._resolve_chunks_source(slide, shared) == ""

    def test_chunks_source_in_material_text(self):
        """Verify that _resolve_chunks_source output would be injected into prompt."""
        from pipeline.agents.content_agent import ContentAgent
        slide = {"chunk_ids": ["c1"], "primary_visual": "text_only"}
        shared = {
            "chunks": [{"id": "c1", "type": "text", "text": "源文档原文段落。", "section": "Ch1"}],
            "tables": [],
            "source_pages": [],
        }
        source = ContentAgent._resolve_chunks_source(slide, shared)
        assert "源文档原文段落" in source
        assert "必须来自上述原文" not in source  # instruction is in _build_slide_messages
