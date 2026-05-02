"""R19 regression test: detect_exact_duplicate catches identical text nodes."""
import pytest
from pipeline.layer6_output.html_dup_check import detect_exact_duplicate


def _wrap(body: str) -> str:
    return f'<html><body style="width:1280px;height:720px;">{body}</body></html>'


def test_two_identical_paragraphs_detected():
    text = "这是一段完全相同的八十个字符的文本内容用于测试精确重复检测功能是否正常工作"
    html = _wrap(f'<p>{text}</p><p>{text}</p>')
    result = detect_exact_duplicate(html, min_len=20)
    assert result is not None
    assert "exact duplicate" in result.lower()


def test_different_paragraphs_clean():
    html = _wrap(
        '<p>这是第一段完全不同的文本内容不会触发重复检测</p>'
        '<p>这是第二段完全不同的文本内容也不会触发重复检测</p>'
    )
    assert detect_exact_duplicate(html, min_len=20) is None


def test_short_text_below_min_len_ignored():
    text = "短文本不检测"  # 7 chars < 20
    html = _wrap(f'<p>{text}</p><p>{text}</p>')
    assert detect_exact_duplicate(html, min_len=20) is None


def test_whitespace_normalized():
    text = "这段文字有空格和换行但归一化后相同所以应该被检测到重复"
    html = _wrap(f'<p>{text}</p><p>这 段 文 字 有 空 格 和 换 行 但 归 一 化 后 相 同 所 以 应 该 被 检 测 到 重 复</p>')
    result = detect_exact_duplicate(html, min_len=20)
    assert result is not None


def test_v8_pattern_two_takeaway_slots():
    """Reproduces v8 P4: same takeaway in h2 and first bullet."""
    takeaway = "行业大模型安全风险持续攀升需要构建纵深防御体系以应对新型攻击面"
    html = _wrap(f'''
        <h2 style="font-size:16px;">{takeaway}</h2>
        <p style="font-size:13px;">{takeaway}</p>
        <p style="font-size:13px;">补充论据内容不同不触发</p>
    ''')
    result = detect_exact_duplicate(html, min_len=20)
    assert result is not None
