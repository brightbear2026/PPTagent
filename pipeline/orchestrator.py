"""
Pipeline Orchestrator — Agent架构编排器
替代旧的 PipelineController，串行运行 6 个 Agent。

parse(silent) → analyze(silent) → outline[checkpoint1] → content[checkpoint2]
  → design(silent) → render(silent)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import traceback
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from storage import get_store, PIPELINE_STAGES

from api.logging_config import get_logger
logger = get_logger(__name__)

# 检查点：在这两个 agent 完成后暂停，等待用户确认
CHECKPOINT_AGENTS = {"outline", "content"}

# 阶段进度映射 (start%, end%, display_name)
STAGE_PROGRESS = {
    "parse":    (5,  15,  "输入解析"),
    "analyze":  (15, 30,  "策略分析"),
    "outline":  (30, 50,  "大纲生成"),
    "content":  (50, 70,  "内容填充"),
    "design":   (70, 85,  "视觉设计"),
    "render":   (85, 100, "PPT渲染"),
}


class Orchestrator:
    """
    串行 Agent 编排器。

    每个阶段：
    1. 从 TaskStore 加载前置 context
    2. 创建对应 Agent 并运行
    3. 保存输出到 TaskStore
    4. 如是 checkpoint 则暂停；否则继续下一阶段
    """

    def __init__(self):
        self.store = get_store()

    # ------------------------------------------------------------------
    # 公开接口（与旧 PipelineController 签名兼容）
    # ------------------------------------------------------------------

    async def run_full(self, task_id: str):
        """从第一个 pending 阶段执行到下一个检查点或完成"""
        self.store.update_task(task_id, status="processing")

        for stage in PIPELINE_STAGES:
            task = self.store.get_task(task_id)
            if not task or task["status"] == "cancelled":
                return

            stage_info = self.store.get_stage(task_id, stage)
            if stage_info and stage_info["status"] == "completed":
                continue

            success = await self._execute_stage(task_id, stage)
            if not success:
                return

            if stage in CHECKPOINT_AGENTS:
                _, _, step_name = STAGE_PROGRESS[stage]
                self.store.update_task(task_id,
                    status="checkpoint",
                    current_stage=stage,
                    current_step=step_name,
                    message=f"检查点: 请确认{step_name}结果")
                return

        self.store.update_task(task_id,
            status="completed",
            progress=100,
            current_step="完成",
            message="PPT生成完成！")

    async def resume_from(self, task_id: str, from_stage: str):
        """用户确认检查点后，从指定阶段继续执行"""
        self.store.reset_stages_from(task_id, from_stage)
        self.store.update_task(task_id, status="processing")

        from_idx = PIPELINE_STAGES.index(from_stage)
        for stage in PIPELINE_STAGES[from_idx:]:
            task = self.store.get_task(task_id)
            if not task or task["status"] == "cancelled":
                return

            success = await self._execute_stage(task_id, stage)
            if not success:
                return

            if stage in CHECKPOINT_AGENTS:
                _, _, step_name = STAGE_PROGRESS[stage]
                self.store.update_task(task_id,
                    status="checkpoint",
                    current_stage=stage,
                    current_step=step_name,
                    message=f"检查点: 请确认{step_name}结果")
                return

        self.store.update_task(task_id,
            status="completed",
            progress=100,
            current_step="完成",
            message="PPT生成完成！")

    async def confirm_checkpoint(self, task_id: str):
        """用户点击「确认」后继续执行剩余阶段"""
        task = self.store.get_task(task_id)
        if not task or task["status"] != "checkpoint":
            return

        current = task.get("current_stage", "")
        if not current or current not in PIPELINE_STAGES:
            return

        current_idx = PIPELINE_STAGES.index(current)
        next_stages = PIPELINE_STAGES[current_idx + 1:]

        if not next_stages:
            self.store.update_task(task_id, status="completed", progress=100)
            return

        self.store.update_task(task_id, status="processing")

        for stage in next_stages:
            task = self.store.get_task(task_id)
            if not task or task["status"] == "cancelled":
                return

            success = await self._execute_stage(task_id, stage)
            if not success:
                return

            if stage in CHECKPOINT_AGENTS:
                _, _, step_name = STAGE_PROGRESS[stage]
                self.store.update_task(task_id,
                    status="checkpoint",
                    current_stage=stage,
                    current_step=step_name,
                    message=f"检查点: 请确认{step_name}结果")
                return

        self.store.update_task(task_id,
            status="completed",
            progress=100,
            current_step="完成",
            message="PPT生成完成！")

    async def rerun_page(self, task_id: str, page_number: int, user_feedback: str = ""):
        """单页重跑：只重新生成指定页的内容。"""
        from pipeline.agents.content_agent import ContentAgent

        task = self.store.get_task(task_id)
        if not task:
            return

        raw = self.store.get_stage_result(task_id, "parse") or {}
        analysis = self.store.get_stage_result(task_id, "analyze") or {}
        outline = self.store.get_stage_result(task_id, "outline") or {}
        content = self.store.get_stage_result(task_id, "content") or {}

        if not all([raw, analysis, outline, content]):
            raise RuntimeError("缺少前置阶段结果，无法重跑单页")

        context = {
            "task": task,
            "task_id": task_id,
            "raw_content": raw,
            "analysis": analysis,
            "outline": outline,
            "content": content,
        }

        llm = self._get_llm("content")
        agent = ContentAgent(llm)

        # 只生成目标页
        outline_slides = outline.get("items", outline.get("slides", []))
        target = next((s for s in outline_slides if s["page_number"] == page_number), None)
        if not target:
            raise RuntimeError(f"大纲中找不到第{page_number}页")

        # Find previous slide for narrative continuity
        prev_slide = None
        for idx, item in enumerate(outline_slides):
            if item.get("page_number") == page_number and idx > 0:
                prev_slide = outline_slides[idx - 1]
                break

        # 临时替换大纲只含该页，重跑填充
        single_context = dict(context)
        single_context["outline"] = {"items": [target]}
        single_context["_user_feedback"] = user_feedback

        new_slides = await asyncio.to_thread(
            self._rerun_single_slide, agent, target, single_context, user_feedback, prev_slide
        )

        # 合并到 content result
        existing_slides = content.get("slides", [])
        merged = {s["page_number"]: s for s in existing_slides}
        for s in (new_slides or []):
            merged[s["page_number"]] = s

        updated_content = {"slides": sorted(merged.values(), key=lambda x: x["page_number"])}
        self.store.save_stage_result(task_id, "content", updated_content)

    @staticmethod
    def _rerun_single_slide(agent, target_slide: dict, context: dict, user_feedback: str, prev_slide=None) -> list:
        """在线程中执行单页重跑，传入 user_feedback。"""
        shared = agent._build_shared_context(context)
        result = agent._generate_one_slide(target_slide, prev_slide, shared, user_feedback=user_feedback)
        if result is None:
            result = agent._make_placeholder(target_slide)
        # Normalize to content result format (mirrors _build_content_result logic for one slide)
        raw_blocks = result.get("text_blocks", [])
        text_blocks = []
        for b in raw_blocks:
            if isinstance(b, dict):
                text_blocks.append({
                    "content": b.get("text", b.get("content", "")),
                    "level": b.get("level", 0),
                    "is_bold": b.get("type") == "heading",
                })
        pn = result.get("page_number", target_slide.get("page_number"))
        takeaway = result.get("takeaway_message") or target_slide.get("takeaway_message", "")
        entry = {
            "page_number": pn,
            "slide_type": target_slide.get("slide_type", "content"),
            "takeaway_message": takeaway,
            "primary_visual": target_slide.get("primary_visual", "text"),
            "text_blocks": text_blocks,
            "chart_suggestion": result.get("chart_suggestion"),
            "diagram_spec": result.get("diagram_spec"),
            "visual_block": result.get("visual_block"),
            "source_note": result.get("visual_hint", ""),
            "layout_hint": target_slide.get("layout_hint", ""),
            "revision_notes": result.get("revision_notes"),
        }
        if result.get("is_failed"):
            entry["is_failed"] = True
            entry["error_message"] = result.get("error_message", result.get("error", ""))
        return [entry]

    # ------------------------------------------------------------------
    # 阶段执行
    # ------------------------------------------------------------------

    async def _execute_stage(self, task_id: str, stage: str) -> bool:
        """执行单个 pipeline 阶段，返回是否成功"""
        import time as _time
        from api.exceptions import (
            LLMRateLimitError, LLMSchemaError, LLMTimeoutError,
            LLMAuthError, RenderError, PipelineError,
        )
        _logger = get_logger("pptagent.pipeline")

        progress_start, progress_end, step_name = STAGE_PROGRESS.get(stage, (0, 0, stage))
        _stage_start = _time.monotonic()

        self.store.update_stage(task_id, stage,
            status="running",
            started_at=self._now())
        self.store.update_task(task_id,
            current_step=step_name,
            current_stage=stage,
            progress=progress_start,
            message=f"正在执行: {step_name}...")

        try:
            task = self.store.get_task(task_id)
            result, agent = await asyncio.to_thread(self._run_agent, task_id, stage, task)

            # Inject token usage from agent into result for cost tracking
            if agent and hasattr(agent, "_token_usage") and isinstance(result, dict):
                result["_token_usage"] = agent._token_usage

            self.store.save_stage_result(task_id, stage, result)
            self.store.update_stage(task_id, stage,
                status="completed",
                completed_at=self._now())
            self.store.update_task(task_id,
                progress=progress_end,
                message=self._build_stage_message(stage, result))

            self._sync_task_fields(task_id, stage, result)
            self._emit_field_metrics(stage, result)

            _duration = _time.monotonic() - _stage_start
            _logger.info("stage_completed stage=%s task=%s duration=%.2fs", stage, task_id, _duration)
            return True

        except (LLMAuthError, LLMRateLimitError) as e:
            # Auth errors: user must fix API key. Rate limit: retries already exhausted.
            _duration = _time.monotonic() - _stage_start
            _logger.error("stage_failed stage=%s task=%s error_type=%s duration=%.2fs",
                          stage, task_id, type(e).__name__, _duration)
            user_msg = f"{step_name}失败: {e}" if isinstance(e, LLMAuthError) else f"{step_name}失败: LLM 调用过于频繁，请稍后重试"
            self.store.update_stage(task_id, stage, status="failed", error=str(e), completed_at=self._now())
            self.store.update_task(task_id, status="failed", error=str(e), message=user_msg)
            return False

        except (LLMSchemaError, LLMTimeoutError) as e:
            # Schema errors: LLM output unparseable. Timeout: request took too long.
            _duration = _time.monotonic() - _stage_start
            _logger.error("stage_failed stage=%s task=%s error_type=%s duration=%.2fs",
                          stage, task_id, type(e).__name__, _duration)
            self.store.update_stage(task_id, stage, status="failed", error=str(e), completed_at=self._now())
            self.store.update_task(task_id, status="failed", error=str(e),
                                   message=f"{step_name}失败: {'输出格式异常，请重试' if isinstance(e, LLMSchemaError) else 'LLM 响应超时，请重试'}")
            return False

        except RenderError as e:
            _duration = _time.monotonic() - _stage_start
            _logger.error("stage_failed stage=%s task=%s error_type=RenderError duration=%.2fs",
                          stage, task_id, _duration)
            self.store.update_stage(task_id, stage, status="failed", error=str(e), completed_at=self._now())
            self.store.update_task(task_id, status="failed", error=str(e),
                                   message=f"{step_name}失败: 渲染错误，请检查 HTML 输出")
            return False

        except Exception as e:
            _duration = _time.monotonic() - _stage_start
            _error_type = type(e).__name__
            _logger.error("stage_failed stage=%s task=%s error_type=%s duration=%.2fs error=%s",
                          stage, task_id, _error_type, _duration, str(e)[:200])
            traceback.print_exc()
            self.store.update_stage(task_id, stage,
                status="failed",
                error=str(e),
                completed_at=self._now())
            self.store.update_task(task_id,
                status="failed",
                error=str(e),
                message=f"{step_name}失败: {e}")
            return False

    def _run_agent(self, task_id: str, stage: str, task: Dict) -> tuple:
        """
        在线程中运行对应的 Agent（避免阻塞 asyncio 事件循环）。
        返回 (result, agent) 元组。
        """
        context = self._build_context(task_id, stage, task)

        # Inject progress callback so agents can emit fine-grained sub-steps.
        def _report(progress: int, message: str) -> None:
            try:
                self.store.update_task(task_id, progress=progress, message=message)
            except Exception:
                pass

        context["report_progress"] = _report

        if stage == "parse":
            from pipeline.agents.parse_agent import ParseAgent
            agent = ParseAgent()
            return agent.run(context), agent

        elif stage == "analyze":
            from pipeline.agents.analyze_agent import AnalyzeAgent
            llm = self._get_llm(stage)
            agent = AnalyzeAgent(llm)
            return agent.run(context), agent

        elif stage == "outline":
            from pipeline.agents.plan_agent import PlanAgent
            llm = self._get_llm(stage)
            agent = PlanAgent(llm)
            return agent.run(context), agent

        elif stage == "content":
            from pipeline.agents.content_agent import ContentAgent
            llm = self._get_llm(stage)
            agent = ContentAgent(llm)
            return agent.run(context), agent

        elif stage == "design":
            render_mode = os.environ.get("RENDER_MODE", "html")
            if render_mode == "html":
                from pipeline.layer6_output.node_bridge import is_node_available
                if is_node_available():
                    from pipeline.agents.html_design_agent import HTMLDesignAgent
                    try:
                        llm = self._get_llm(stage)
                    except ValueError:
                        llm = None
                    agent = HTMLDesignAgent(llm)
                    return agent.run(context), agent
            # Fallback to legacy render path
            from pipeline.agents.design_agent import DesignAgent
            try:
                llm = self._get_llm(stage)
            except ValueError:
                llm = None
            agent = DesignAgent(llm)
            return agent.run(context), agent

        elif stage == "render":
            # When using HTML rendering, design stage handles both design+render.
            # This stage becomes a no-op pass-through.
            design_result = context.get("design") or self.store.get_stage_result(task_id, "design")
            if design_result and design_result.get("output_file"):
                return design_result, None
            # Legacy path
            from pipeline.agents.render_agent import RenderAgent
            agent = RenderAgent()
            return agent.run(context), agent

        else:
            raise ValueError(f"未知阶段: {stage}")

    def _build_context(self, task_id: str, stage: str, task: Dict) -> Dict:
        """根据阶段加载所需的前置结果，组成 context dict"""
        ctx: Dict[str, Any] = {"task": task, "task_id": task_id}

        def _load(s: str) -> Optional[Dict]:
            return self.store.get_stage_result(task_id, s)

        if stage in ("analyze", "outline", "content", "design"):
            raw = _load("parse")
            if raw:
                ctx["raw_content"] = raw

        if stage in ("outline", "content", "design"):
            analysis = _load("analyze")
            if analysis:
                ctx["analysis"] = analysis

        if stage in ("content", "design"):
            outline = _load("outline")
            if outline:
                ctx["outline"] = outline

        if stage == "design":
            content = _load("content")
            if content:
                ctx["content"] = content

        if stage == "render":
            design = _load("design")
            if design:
                ctx["design"] = design

        return ctx

    def _get_llm(self, stage: str = "analyze"):
        """
        获取 LLM 客户端。
        优先读取 pipeline_model_config 中的阶段配置；
        如果该阶段配置了 zhipu provider，使用 GLMClient（支持 tool_use）；
        否则降级为 openai_compat。
        """
        try:
            from models.model_config import PipelineModelConfig
            from llm_client.factory import get_client
            from llm_client import GLMClient
            from storage.encryption import decrypt_api_key

            config_json = self.store.get_setting("default", "pipeline_model_config")
            if config_json:
                config = PipelineModelConfig.model_validate_json(config_json)
                stage_config = config.get_stage_config(stage)

                api_key = stage_config.api_key
                if not api_key:
                    encrypted = self.store.get_api_key("default", stage_config.provider)
                    if encrypted:
                        api_key = decrypt_api_key(encrypted)

                if api_key:
                    # content 阶段并发批次输出量大，给更长超时
                    stage_timeout = 240 if stage == "content" else 120

                    # 智谱 provider 使用原生 GLMClient（支持 tool_use）
                    if stage_config.provider == "zhipu":
                        return GLMClient(
                            api_key=api_key,
                            model=stage_config.model or "glm-5.1",
                        )
                    return get_client(
                        provider=stage_config.provider,
                        api_key=api_key,
                        model=stage_config.model,
                        base_url=stage_config.base_url,
                        timeout=stage_timeout,
                    )

                raise ValueError(
                    f"阶段 '{stage}' 未配置API Key。请在系统设置中配置 {stage_config.provider} 的API Key。"
                )

            raise ValueError("未配置LLM模型。请在系统设置中配置模型和API Key。")

        except ValueError:
            raise
        except Exception as e:
            raise ValueError(f"获取LLM客户端失败: {e}")

    # ------------------------------------------------------------------
    # 工具方法
    # ------------------------------------------------------------------

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _build_stage_message(stage: str, result: Dict) -> str:
        """从 stage 结果构建用户可读的状态消息"""
        if stage == "parse":
            n_sections = len(result.get("sections", []))
            n_tables = len(result.get("tables", []))
            return f"解析完成：{n_sections}个章节，{n_tables}个表格"
        elif stage == "analyze":
            themes = result.get("strategy", {}).get("core_themes", [])
            return f"策略分析完成：识别到{len(themes)}个核心主题"
        elif stage == "outline":
            slides = result.get("items", result.get("slides", []))
            return f"大纲生成完成：共{len(slides)}页"
        elif stage == "content":
            slides = result.get("slides", [])
            return f"内容填充完成：共{len(slides)}页"
        elif stage == "design":
            slides = result.get("slides", [])
            skipped = result.get("skipped_pages", [])
            msg = f"视觉设计完成：共{len(slides)}页"
            if skipped:
                msg += f"（{len(skipped)}页内容生成失败已跳过，最终PPT将少这些页）"
            return msg
        elif stage == "render":
            output_file = result.get("output_file", "")
            return f"PPT生成完成：{output_file}"
        return f"{stage} 完成"

    @staticmethod
    def _emit_field_metrics(stage: str, result: Dict) -> None:
        """Log structured field-presence-rate metrics after each LLM stage.

        These JSON log lines can be scraped by any log aggregator (Loki, ELK, CloudWatch)
        and turned into dashboards / alerts on field completeness regressions.
        """
        metrics: Dict[str, Any] = {"type": "field_presence_rate", "stage": stage}

        if stage == "outline":
            items = result.get("items", result.get("slides", []))
            total = len(items)
            if total:
                metrics["total_slides"] = total
                metrics["supporting_hint_rate"] = round(
                    sum(1 for i in items if i.get("supporting_hint")) / total, 3)
                metrics["data_source_rate"] = round(
                    sum(1 for i in items if i.get("data_source")) / total, 3)
                metrics["narrative_arc_rate"] = round(
                    sum(1 for i in items if i.get("narrative_arc")) / total, 3)

        elif stage == "content":
            slides = result.get("slides", [])
            total = len(slides)
            if total:
                metrics["total_slides"] = total
                metrics["text_blocks_rate"] = round(
                    sum(1 for s in slides if s.get("text_blocks")) / total, 3)
                metrics["chart_rate"] = round(
                    sum(1 for s in slides if s.get("chart_suggestion")) / total, 3)
                metrics["diagram_rate"] = round(
                    sum(1 for s in slides if s.get("diagram_spec")) / total, 3)
                metrics["failed_rate"] = round(
                    sum(1 for s in slides if s.get("is_failed")) / total, 3)

        elif stage == "design":
            slides = result.get("slides", result.get("pres_spec", {}).get("slides", []))
            total = len(slides)
            if total:
                metrics["total_slides"] = total
                metrics["chart_rate"] = round(
                    sum(1 for s in slides if s.get("charts")) / total, 3)
                metrics["diagram_rate"] = round(
                    sum(1 for s in slides if s.get("diagrams")) / total, 3)
                metrics["skipped_rate"] = round(
                    len(result.get("skipped_pages", [])) / total, 3)

        if len(metrics) > 2:  # at least one domain-specific field was added
            logger.info("METRICS %s", json.dumps(metrics, ensure_ascii=False))

    def _sync_task_fields(self, task_id: str, stage: str, result: Dict) -> None:
        """将关键字段同步到 tasks 表，方便前端直接读取"""
        if stage == "outline":
            items = result.get("items", result.get("slides", []))
            self.store.update_task(task_id, slides=json.dumps(items, ensure_ascii=False))
        elif stage == "design":
            skipped = result.get("skipped_pages", [])
            if skipped:
                logger.warning(
                    f"[Design] {len(skipped)}页被跳过: "
                    f"{[p['page_number'] for p in skipped]}"
                )
        elif stage == "render":
            output_file = result.get("output_file", "")
            if output_file:
                self.store.update_task(task_id, output_file=output_file)
