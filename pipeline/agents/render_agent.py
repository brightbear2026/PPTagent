"""
DEPRECATED: Legacy render agent. Only used when RENDER_MODE != "html".
See html2pptx.js + ChartRenderer for the primary rendering path.

RenderAgent — CodeAgent，无 LLM，纯代码渲染。
包装现有 PPTBuilder 逻辑，输出 .pptx 文件路径。
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from .base import CodeAgent

logger = logging.getLogger(__name__)


class RenderAgent(CodeAgent):
    """PPT渲染 Agent"""

    def run(self, context: Dict[str, Any]) -> Dict:
        from pipeline.layer6_output import PPTBuilder
        from models.slide_spec import PresentationSpec

        design = context.get("design", {})
        if not design:
            raise RuntimeError("缺少design阶段结果，无法渲染PPT")

        pres_spec = PresentationSpec.from_dict(design["pres_spec"])

        builder = PPTBuilder()
        output_path = builder.build(pres_spec)

        return {
            "output_file": output_path,
            "slide_count": design.get("slide_count", 0),
            "chart_count": design.get("chart_count", 0),
            "diagram_count": design.get("diagram_count", 0),
            "file_name": output_path.split("/")[-1] if output_path else None,
        }
