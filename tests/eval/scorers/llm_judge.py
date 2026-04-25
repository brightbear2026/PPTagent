"""
llm_judge.py — LLM-as-judge（内容质量）
防内容退化：规则评分无法检测的废话和事实错误。

使用与 pipeline 不同的 provider 作为 judge，避免同源偏差。
"""

from __future__ import annotations
import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

JUDGE_SYSTEM_PROMPT = """你是一位严格的PPT内容质量评审员。
你的任务是对比原始文档内容和生成的PPT大纲/内容，从以下三个维度打分（每项1-5分）：

1. factual_consistency（事实一致性）：PPT内容是否与原文一致，有无编造或歪曲
   5=完全一致，无编造；3=基本一致，有小偏差；1=存在明显事实错误

2. source_relevance（原文相关性）：PPT内容是否有效提炼了原文核心信息
   5=精准提炼，无遗漏关键信息；3=提炼部分关键信息；1=内容与原文关系不大

3. information_density（信息密度）：内容是否信息密集，无废话
   5=每句话都有实质信息；3=有少量模糊措辞；1=大量废话、套话

请严格以 JSON 格式输出，不要有其他内容：
{"factual_consistency": <1-5>, "source_relevance": <1-5>, "information_density": <1-5>, "brief_comment": "<不超过50字的简短说明>"}"""


def judge_outline(source_text: str, outline: dict, llm_client) -> dict:
    """
    用 LLM 评审 outline 质量。

    Args:
        source_text: 原始文档内容（前2000字）
        outline: outline 阶段输出
        llm_client: judge LLM client（应与 pipeline 使用不同 provider）

    Returns:
        dict with factual_consistency, source_relevance, information_density, brief_comment
    """
    from llm_client.base import ChatMessage

    items = outline.get("items", [])
    content_items = [s for s in items if s.get("slide_type") not in ("title", "agenda", "section_divider")]

    outline_summary = "\n".join(
        f"P{s.get('page_number')}: {s.get('takeaway_message', '')}"
        for s in content_items[:15]
    )

    user_msg = f"""## 原始文档（节选前2000字）
{source_text[:2000]}

## 生成的PPT大纲（核心论点）
{outline_summary}

请评审大纲质量，输出JSON格式评分。"""

    messages = [
        ChatMessage(role="system", content=JUDGE_SYSTEM_PROMPT),
        ChatMessage(role="user", content=user_msg),
    ]

    try:
        response = llm_client.chat(messages=messages, temperature=0.2, max_tokens=200)
        if not response.success:
            raise RuntimeError(f"Judge LLM 调用失败: {response.error}")
        scores = _parse_judge_scores(response.content or "")
        return scores
    except Exception as e:
        logger.warning(f"[llm_judge] outline judge failed: {e}")
        return {"factual_consistency": -1, "source_relevance": -1, "information_density": -1, "brief_comment": f"judge失败: {e}"}


def judge_content(source_text: str, content: dict, llm_client) -> dict:
    """
    用 LLM 评审 content 质量（随机抽样2页评审）。
    """
    from llm_client.base import ChatMessage
    import random

    slides = content.get("slides", [])
    if not slides:
        return {"factual_consistency": -1, "source_relevance": -1, "information_density": -1, "brief_comment": "无内容"}

    # 随机抽样最多2页
    sample = random.sample(slides, min(2, len(slides)))
    content_summary = ""
    for s in sample:
        blocks = [b.get("content", "") for b in s.get("text_blocks", []) if b.get("content", "").strip()]
        content_summary += f"\nP{s.get('page_number')} ({s.get('takeaway_message', '')}):\n" + "\n".join(f"  - {b}" for b in blocks[:5])

    user_msg = f"""## 原始文档（节选前2000字）
{source_text[:2000]}

## 生成的PPT内容（抽样2页）
{content_summary}

请评审内容质量，输出JSON格式评分。"""

    messages = [
        ChatMessage(role="system", content=JUDGE_SYSTEM_PROMPT),
        ChatMessage(role="user", content=user_msg),
    ]

    try:
        response = llm_client.chat(messages=messages, temperature=0.2, max_tokens=200)
        if not response.success:
            raise RuntimeError(f"Judge LLM 调用失败: {response.error}")
        scores = _parse_judge_scores(response.content or "")
        return scores
    except Exception as e:
        logger.warning(f"[llm_judge] content judge failed: {e}")
        return {"factual_consistency": -1, "source_relevance": -1, "information_density": -1, "brief_comment": f"judge失败: {e}"}


def _parse_judge_scores(text: str) -> dict:
    import re
    for pattern in [r'```json\s*(\{[\s\S]*?\})\s*```', r'```\s*(\{[\s\S]*?\})\s*```', r'(\{[\s\S]*?\})']:
        m = re.search(pattern, text, re.DOTALL)
        if m:
            try:
                data = json.loads(m.group(1))
                return {
                    "factual_consistency": float(data.get("factual_consistency", -1)),
                    "source_relevance": float(data.get("source_relevance", -1)),
                    "information_density": float(data.get("information_density", -1)),
                    "brief_comment": str(data.get("brief_comment", "")),
                }
            except Exception:
                continue
    return {"factual_consistency": -1, "source_relevance": -1, "information_density": -1, "brief_comment": "解析失败"}
