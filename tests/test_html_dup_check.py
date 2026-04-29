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
