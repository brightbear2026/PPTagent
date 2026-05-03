"""Tests for R31 — Table → chart_suggestion direct pass."""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestPrebuiltChartFromTableChunks:
    def test_basic_table_to_chart(self):
        from pipeline.agents.content_agent import ContentAgent
        slide = {
            "page_number": 5,
            "primary_visual": "chart",
            "chunk_ids": ["ch_table1"],
        }
        shared = {
            "chunks": [{
                "id": "ch_table1",
                "type": "table",
                "text": "Sales data",
                "table_data": {
                    "headers": ["季度", "收入", "利润"],
                    "rows": [
                        ["Q1", "100", "20"],
                        ["Q2", "120", "25"],
                        ["Q3", "150", "35"],
                    ],
                },
            }],
        }
        result = ContentAgent._prebuilt_chart_from_table_chunks(slide, shared)
        assert result is not None
        assert result["chart_type"] == "column"
        assert result["categories"] == ["Q1", "Q2", "Q3"]
        assert len(result["series"]) == 2
        assert result["series"][0]["name"] == "收入"
        assert result["series"][0]["values"] == [100.0, 120.0, 150.0]
        assert result["source_table_id"] == "ch_table1"

    def test_not_chart_visual_returns_none(self):
        from pipeline.agents.content_agent import ContentAgent
        slide = {"primary_visual": "text_only", "chunk_ids": ["ch_t1"]}
        shared = {
            "chunks": [{"id": "ch_t1", "type": "table", "table_data": {"headers": ["A"], "rows": []}}],
        }
        assert ContentAgent._prebuilt_chart_from_table_chunks(slide, shared) is None

    def test_no_table_chunks_returns_none(self):
        from pipeline.agents.content_agent import ContentAgent
        slide = {"primary_visual": "chart", "chunk_ids": ["ch_text1"]}
        shared = {
            "chunks": [{"id": "ch_text1", "type": "text", "text": "some text"}],
        }
        assert ContentAgent._prebuilt_chart_from_table_chunks(slide, shared) is None

    def test_empty_chunk_ids_returns_none(self):
        from pipeline.agents.content_agent import ContentAgent
        slide = {"primary_visual": "chart", "chunk_ids": []}
        shared = {"chunks": []}
        assert ContentAgent._prebuilt_chart_from_table_chunks(slide, shared) is None

    def test_chinese_numbers_parsed(self):
        from pipeline.agents.content_agent import ContentAgent
        slide = {"primary_visual": "chart", "chunk_ids": ["ch_t1"]}
        shared = {
            "chunks": [{
                "id": "ch_t1",
                "type": "table",
                "table_data": {
                    "headers": ["指标", "数值"],
                    "rows": [
                        ["用户数", "500万"],
                        ["增长率", "23.5%"],
                    ],
                },
            }],
        }
        result = ContentAgent._prebuilt_chart_from_table_chunks(slide, shared)
        assert result is not None
        assert result["series"][0]["values"][0] == 5000000.0  # 500万
        assert result["series"][0]["values"][1] == 23.5       # 23.5%

    def test_single_column_table_returns_none(self):
        from pipeline.agents.content_agent import ContentAgent
        slide = {"primary_visual": "chart", "chunk_ids": ["ch_t1"]}
        shared = {
            "chunks": [{
                "id": "ch_t1",
                "type": "table",
                "table_data": {
                    "headers": ["名称"],
                    "rows": [["A"], ["B"]],
                },
            }],
        }
        assert ContentAgent._prebuilt_chart_from_table_chunks(slide, shared) is None

    def test_many_categories_uses_line_chart(self):
        from pipeline.agents.content_agent import ContentAgent
        slide = {"primary_visual": "chart", "chunk_ids": ["ch_t1"]}
        rows = [[f"M{i}", str(i * 10)] for i in range(10)]
        shared = {
            "chunks": [{
                "id": "ch_t1",
                "type": "table",
                "table_data": {"headers": ["月份", "值"], "rows": rows},
            }],
        }
        result = ContentAgent._prebuilt_chart_from_table_chunks(slide, shared)
        assert result["chart_type"] == "line"
