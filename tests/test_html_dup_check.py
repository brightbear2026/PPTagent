"""Regression tests for prefix-of-superset detector."""
from pipeline.layer6_output.html_dup_check import detect_dup_prefix


class TestDupDetect:

    def test_detects_real_world_slide4(self):
        html = """<html><body>
            <p style="font-size:13.5pt">大模型正从营销、风控、投研等层面重塑金融业务...</p>
            <h1 style="font-size:45.75pt">大模型正从营销、风控</h1>
        </body></html>"""
        assert detect_dup_prefix(html) is not None

    def test_detects_real_world_slide27(self):
        html = """<html><body>
            <p>金融大模型的安全防护不应是事后补救的'创可贴'，而应作为创新的基础底盘嵌入业务全流程</p>
            <h1>金融大模型的安全防护</h1>
        </body></html>"""
        assert detect_dup_prefix(html) is not None

    def test_distinct_text_no_false_positive(self):
        html = """<html><body>
            <h1>主动防御四步法</h1>
            <p>识别、防护、监控、响应四个阶段构建闭环</p>
        </body></html>"""
        assert detect_dup_prefix(html) is None

    def test_short_repeated_label_no_false_positive(self):
        # Repeated chapter labels like "第一章" (3 chars) below min_short
        html = """<html><body>
            <p>第一章</p>
            <p>第一章 开篇导入</p>
        </body></html>"""
        assert detect_dup_prefix(html) is None

    def test_close_lengths_no_false_positive(self):
        # Both texts similar length — not truncation pattern
        html = """<html><body>
            <p>大模型应用安全防护</p>
            <p>大模型应用安全防护体系</p>
        </body></html>"""
        # ratio < 2.0 → should not trigger
        assert detect_dup_prefix(html) is None

    def test_max_short_threshold(self):
        # Real headlines can be up to 30 chars; longer is unlikely truncation
        long_short = "大模型应用" * 7  # 35 chars
        html = f"<p>{long_short}</p><p>{long_short}的详细解释，含很多额外内容...</p>"
        assert detect_dup_prefix(html) is None


class TestFooterInjection:
    def test_inject_section_into_footer(self):
        from pipeline.agents.html_design_agent import HTMLDesignAgent
        html = (
            '<body>'
            '<div style="position:absolute; bottom:0; left:0; width:960px; height:24px; background-color:#003D6E;">'
            '<p style="font-size:9px; color:#FFFFFF; margin:4px 24px;">第 5 页 / 共 20 页</p>'
            '</div>'
            '</body>'
        )
        slide_data = {"section": "第三章 风险全景"}
        result = HTMLDesignAgent._inject_section_footer(html, slide_data, 4, 20)
        assert "风险全景" in result
        assert "P5 / 20" in result
        assert "第 5 页 / 共 20 页" not in result

    def test_no_section_shows_only_page(self):
        from pipeline.agents.html_design_agent import HTMLDesignAgent
        html = (
            '<body>'
            '<div style="position:absolute; bottom:0;">'
            '<p style="font-size:9px; color:#FFFFFF; margin:4px 24px;">第 1 页 / 共 10 页</p>'
            '</div>'
            '</body>'
        )
        slide_data = {"section": ""}
        result = HTMLDesignAgent._inject_section_footer(html, slide_data, 0, 10)
        assert "P1 / 10" in result

    def test_chapter_prefix_stripped(self):
        from pipeline.agents.html_design_agent import HTMLDesignAgent
        html = (
            '<body>'
            '<div style="position:absolute; bottom:0;">'
            '<p style="font-size:9px; color:#FFFFFF; margin:4px 24px;">第 3 页 / 共 10 页</p>'
            '</div>'
            '</body>'
        )
        slide_data = {"section": "第一章 开篇导入"}
        result = HTMLDesignAgent._inject_section_footer(html, slide_data, 2, 10)
        assert "开篇导入" in result
        assert "第一章" not in result
