"""
ReAct Agent 核心基类
实现 Think→Act→Observe 循环，支持原生 tool_use。
"""

from __future__ import annotations

import json
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from llm_client.base import (
    ChatMessage,
    ChatResponse,
    ToolCall,
    ToolDefinition,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompt 版本化工具
# ---------------------------------------------------------------------------

_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


def load_prompt(agent_name: str, version: str = "v1") -> str:
    """从 pipeline/prompts/{agent_name}.{version}.md 读取系统 prompt。"""
    path = _PROMPTS_DIR / f"{agent_name}.{version}.md"
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    raise FileNotFoundError(f"Prompt file not found: {path}")


# ---------------------------------------------------------------------------
# Tool：将 Python 函数包装为 Agent 可调用工具
# ---------------------------------------------------------------------------

@dataclass
class Tool:
    """将 Python 函数暴露给 LLM 的工具包装器"""
    name: str
    description: str
    parameters: dict        # JSON Schema for function arguments
    fn: Callable[..., str]  # 必须返回字符串（tool 结果）

    def to_tool_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name=self.name,
            description=self.description,
            parameters=self.parameters,
        )

    def execute(self, **kwargs) -> str:
        """执行工具并返回字符串结果"""
        try:
            result = self.fn(**kwargs)
            return str(result)
        except Exception as e:
            return f"[工具执行错误] {self.name}: {e}"


# ---------------------------------------------------------------------------
# ValidationResult
# ---------------------------------------------------------------------------

@dataclass
class ValidationResult:
    valid: bool
    errors: List[str] = field(default_factory=list)

    def __bool__(self) -> bool:
        return self.valid

    def summary(self) -> str:
        if self.valid:
            return "验证通过"
        return "验证失败：\n" + "\n".join(f"  - {e}" for e in self.errors)


# ---------------------------------------------------------------------------
# ReActAgent：所有 LLM 驱动的 Agent 基类
# ---------------------------------------------------------------------------

class ReActAgent(ABC):
    """
    ReAct 工具调用循环 Agent。

    子类必须实现：
    - system_prompt() -> str
    - tools() -> list[Tool]
    - build_initial_messages(context) -> list[ChatMessage]
    - extract_output(messages) -> Any
    - validate(output) -> ValidationResult
    """

    max_iterations: int = 10
    max_validation_retries: int = 3

    def __init__(self, llm_client):
        """
        Args:
            llm_client: 任何实现了 LLMClient.chat() 的客户端
        """
        self.llm = llm_client
        self._iteration_count = 0

    @property
    @abstractmethod
    def system_prompt(self) -> str:
        """返回系统 prompt"""
        ...

    @property
    @abstractmethod
    def tools(self) -> List[Tool]:
        """返回该 Agent 使用的工具列表"""
        ...

    @abstractmethod
    def build_initial_messages(self, context: Dict[str, Any]) -> List[ChatMessage]:
        """根据输入 context 构建初始 messages"""
        ...

    @abstractmethod
    def extract_output(self, messages: List[ChatMessage]) -> Any:
        """从对话历史中提取最终结构化输出"""
        ...

    @abstractmethod
    def validate(self, output: Any) -> ValidationResult:
        """验证提取到的输出是否符合约束"""
        ...

    def run(self, context: Dict[str, Any]) -> Any:
        """
        运行 ReAct 循环：
        1. 构建初始 messages（system + user）
        2. 调用 LLM（携带 tools）
        3. tool_calls → 执行工具 → 把结果追加到 messages → 继续循环
        4. finish_reason=stop → 提取输出 → 验证
        5. 验证失败 → 把错误反馈给 LLM → 自我修正（最多 max_validation_retries 次）
        6. 返回最终输出
        """
        tool_defs = [t.to_tool_definition() for t in self.tools]
        tool_map: Dict[str, Tool] = {t.name: t for t in self.tools}

        messages: List[ChatMessage] = [
            ChatMessage(role="system", content=self.system_prompt),
            *self.build_initial_messages(context),
        ]

        self._iteration_count = 0
        validation_attempts = 0

        while self._iteration_count < self.max_iterations:
            self._iteration_count += 1
            logger.info(f"[{self.__class__.__name__}] 迭代 {self._iteration_count}/{self.max_iterations}")

            t0 = time.time()
            response: ChatResponse = self.llm.chat(
                messages=messages,
                tools=tool_defs if tool_defs else None,
                temperature=getattr(self, "temperature", 0.7),
                max_tokens=getattr(self, "max_tokens", 4096),
            )
            elapsed = time.time() - t0
            logger.info(f"[{self.__class__.__name__}] LLM耗时 {elapsed:.1f}s | finish={response.finish_reason} | tokens={response.total_tokens}")

            if not response.success:
                raise RuntimeError(f"LLM调用失败: {response.error}")

            # --- tool_calls 分支 ---
            if response.has_tool_calls:
                # 把 assistant 的回复（含 tool_calls）追加到历史
                messages.append(ChatMessage(
                    role="assistant",
                    content=response.content,
                    tool_calls=response.tool_calls,
                ))

                # 逐个执行工具，结果追加为 tool 消息
                for tc in (response.tool_calls or []):
                    tool_result = self._execute_tool(tc, tool_map)
                    messages.append(ChatMessage(
                        role="tool",
                        content=tool_result,
                        tool_call_id=tc.call_id,
                        name=tc.function_name,
                    ))
                continue  # 继续下一轮循环

            # --- stop 分支：LLM 完成输出 ---
            messages.append(ChatMessage(
                role="assistant",
                content=response.content,
            ))

            # finish_reason=length 表示输出被截断，JSON 可能不完整
            if response.finish_reason in ("length", "max_tokens"):
                if validation_attempts < self.max_validation_retries:
                    validation_attempts += 1
                    logger.warning(
                        f"[{self.__class__.__name__}] LLM输出被截断(finish_reason={response.finish_reason})，"
                        f"第{validation_attempts}次重试，请输出更短的结果"
                    )
                    messages.append(ChatMessage(
                        role="user",
                        content="你的输出被截断了，请重新输出完整的JSON结果。注意：减少每页文字量，确保输出完整的JSON数组。",
                    ))
                    continue
                else:
                    logger.warning(
                        f"[{self.__class__.__name__}] 输出截断，已达最大重试次数，尝试用截断结果继续"
                    )

            # 提取 + 验证
            if validation_attempts >= self.max_validation_retries:
                logger.warning(
                    f"[{self.__class__.__name__}] 达到最大验证重试次数，使用最后输出"
                )
                break

            try:
                output = self.extract_output(messages)
            except Exception as e:
                validation_attempts += 1
                feedback = f"输出解析失败：{e}\n请重新输出符合格式要求的结果。"
                messages.append(ChatMessage(role="user", content=feedback))
                continue

            result = self.validate(output)
            if result.valid:
                logger.info(f"[{self.__class__.__name__}] 验证通过，共 {self._iteration_count} 次迭代")
                return output

            # 验证失败 → 反馈给 LLM 自修正
            validation_attempts += 1
            logger.debug(f"[{self.__class__.__name__}] 验证失败（第{validation_attempts}次）: {result.summary()}")
            messages.append(ChatMessage(
                role="user",
                content=f"输出不符合要求，请修正：\n{result.summary()}\n\n请重新输出完整结果。",
            ))

        # 超出迭代限制，尝试返回最后输出
        try:
            return self.extract_output(messages)
        except Exception as e:
            raise RuntimeError(f"[{self.__class__.__name__}] ReAct循环超出{self.max_iterations}次迭代，无法提取输出: {e}")

    def _execute_tool(self, tc: ToolCall, tool_map: Dict[str, Tool]) -> str:
        """解析 tool call 参数并执行对应工具"""
        tool = tool_map.get(tc.function_name)
        if not tool:
            return f"[错误] 未知工具: {tc.function_name}"

        try:
            kwargs = json.loads(tc.arguments) if tc.arguments else {}
        except json.JSONDecodeError as e:
            return f"[错误] 工具参数JSON解析失败: {e}"

        logger.info(f"[{self.__class__.__name__}] 调用工具: {tc.function_name}")
        result = tool.execute(**kwargs)
        return result


# ---------------------------------------------------------------------------
# CodeAgent：不需要 LLM 的确定性代码 Agent（Parse/Render 阶段）
# ---------------------------------------------------------------------------

class CodeAgent(ABC):
    """
    纯代码执行 Agent，不调用 LLM。
    用于 Parse（输入解析）和 Render（PPT生成）阶段。
    """

    @abstractmethod
    def run(self, context: Dict[str, Any]) -> Any:
        """执行确定性逻辑，返回阶段输出"""
        ...


# ---------------------------------------------------------------------------
# StructuredLLMAgent：直接 LLM 调用 + 结构化输出基类
# 用于 AnalyzeAgent / ContentAgent 等不需要工具循环的 LLM Agent
# ---------------------------------------------------------------------------

class StructuredLLMAgent(CodeAgent):
    """
    一次性 LLM 调用 Agent。不使用 ReAct 工具循环。

    提供：
    - self.llm：LLM 客户端
    - _call_llm(messages)：带日志和错误检测的单次 LLM 调用，返回文本
    - run_structured(messages, schema)：调用 LLM + Pydantic 校验 + 1 次 fix retry
    """

    temperature: float = 0.7
    max_tokens: int = 4096

    def __init__(self, llm_client):
        self.llm = llm_client

    def _call_llm(self, messages: List[ChatMessage], **kwargs) -> str:
        """调用 LLM，返回文本内容。失败时抛出 RuntimeError。"""
        t0 = time.time()
        response: ChatResponse = self.llm.chat(
            messages=messages,
            tools=None,
            temperature=kwargs.get("temperature", getattr(self, "temperature", 0.7)),
            max_tokens=kwargs.get("max_tokens", getattr(self, "max_tokens", 4096)),
        )
        elapsed = time.time() - t0
        logger.info(
            "[%s] LLM耗时 %.1fs | finish=%s | tokens=%s",
            self.__class__.__name__, elapsed,
            response.finish_reason, response.total_tokens,
        )
        if not response.success:
            raise RuntimeError(f"LLM调用失败: {response.error}")
        return response.content or ""

    def run_structured(self, messages: List[ChatMessage], output_schema, fix_hint: str = ""):
        """
        调用 LLM，Pydantic 校验输出，失败时给一次 fix retry。

        Args:
            messages: 完整消息列表（含 system）
            output_schema: Pydantic BaseModel 子类
            fix_hint: 校验失败时追加的修复提示

        Returns:
            output_schema 实例
        """
        from pydantic import ValidationError

        raw = self._call_llm(messages)
        try:
            return output_schema.model_validate_json(raw)
        except (ValidationError, Exception) as e:
            logger.warning("[%s] Pydantic 校验失败，尝试 fix retry: %s", self.__class__.__name__, e)
            fix_msgs = list(messages) + [
                ChatMessage(role="assistant", content=raw),
                ChatMessage(
                    role="user",
                    content=f"输出格式错误：{e}\n{fix_hint}\n请修正并重新输出合法 JSON。",
                ),
            ]
            raw2 = self._call_llm(fix_msgs)
            return output_schema.model_validate_json(raw2)  # 再失败则 raise
