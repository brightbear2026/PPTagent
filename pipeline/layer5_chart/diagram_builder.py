"""
DiagramSpec构建器 - 使用LLM提取节点关系
"""
import json
import re
from typing import Optional
from models import (SlideSpec, DiagramSpec, DiagramNode, DiagramEdge,
                    DiagramNodeShape, ConnectorStyle)
from llm_client.glm_client import GLMClient


class DiagramBuilder:
    """从流程/架构类内容提取nodes和edges"""

    def __init__(self, llm_client: GLMClient):
        self.llm = llm_client

    def build_from_slide(self, slide: SlideSpec,
                         diagram_type: str = "flowchart") -> Optional[DiagramSpec]:
        """从slide内容构建DiagramSpec"""
        nodes_edges = self._extract_nodes_and_edges(slide)
        if not nodes_edges or not nodes_edges.get("nodes"):
            return None

        nodes = []
        for i, n in enumerate(nodes_edges["nodes"]):
            nodes.append(DiagramNode(
                node_id=n.get("id", f"n{i}"),
                label=n.get("label", ""),
                shape=DiagramNodeShape.ROUNDED_RECT,
            ))

        edges = []
        for e in nodes_edges.get("edges", []):
            edges.append(DiagramEdge(
                from_id=e.get("from", ""),
                to_id=e.get("to", ""),
                label=e.get("label", ""),
                style=ConnectorStyle.ELBOW,
            ))

        return DiagramSpec(
            diagram_type=diagram_type,
            nodes=nodes,
            edges=edges,
            layout_direction="TB",
            title=slide.takeaway_message,
        )

    def _extract_nodes_and_edges(self, slide: SlideSpec) -> Optional[dict]:
        text_content = "\n".join(f"- {b.content}" for b in slide.text_blocks)

        prompt = f"""你是一个架构图专家。请从以下PPT页面内容中提取适合制作流程图/架构图的节点和连接关系。

## 页面标题
{slide.takeaway_message}

## 页面文本内容
{text_content}

## 要求
1. 提取关键的实体/步骤/组件作为节点（nodes）
2. 提取节点之间的流向/依赖关系作为连接（edges）
3. 节点数量控制在3-8个
4. 每个节点需要有唯一id和显示标签

## 输出格式（纯JSON）
{{
  "nodes": [
    {{"id": "n1", "label": "步骤/组件名"}},
    {{"id": "n2", "label": "步骤/组件名"}}
  ],
  "edges": [
    {{"from": "n1", "to": "n2", "label": "关系描述"}}
  ]
}}

请直接输出JSON。"""

        try:
            response = self.llm.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=1000,
            )
            return self._parse_json(response)
        except Exception as e:
            print(f"⚠️ LLM提取架构图数据失败: {e}")
            return self._fallback_parse(text_content)

    def _parse_json(self, text: str) -> Optional[dict]:
        text = text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
            text = text.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r'\{[\s\S]+\}', text)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass
            return None

    def _fallback_parse(self, text: str) -> Optional[dict]:
        """降级：将每个top-level文本块作为一个节点，顺序连接"""
        nodes = []
        for i, line in enumerate(text.split("\n")):
            line = line.strip().lstrip("- ")
            if line and len(line) > 2:
                nodes.append({"id": f"n{i}", "label": line[:20]})

        if len(nodes) < 2:
            return None

        edges = []
        for i in range(len(nodes) - 1):
            edges.append({"from": nodes[i]["id"], "to": nodes[i+1]["id"], "label": ""})

        return {"nodes": nodes, "edges": edges}
