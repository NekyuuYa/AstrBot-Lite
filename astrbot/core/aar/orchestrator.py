"""AAR Pipeline Orchestrator — 七阶段 System Prompt 装配管道。

PipelineOrchestrator 全面接管发送给 LLM 前的 Prompt 组装逻辑，按照
七大物理阶段严格顺序拼接 System Prompt，最大化 Prompt Caching 命中率。

装配流程：
1. 根据 Event/Session 初始化 AssemblyContext。
2. 获取对应 Agent，通过 ContextPolicy 处理 raw_messages -> processed_messages。
3. 获取 Agent 引用的所有 Prompts。
4. 遍历 7 大 Stage，解析 Static/Template/Functional 类型。
5. 严格按 Stage 1 -> Stage 7 顺序拼接。
6. 输出最终 system_prompt 字符串。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from astrbot.core.aar.agent_manager import AgentManager
from astrbot.core.aar.context_policy import ContextPolicyRegistry, ContextPolicyResult
from astrbot.core.aar.prompt_manager import PromptManager
from astrbot.core.db.po import AgentConfig, PromptCategory, PromptEntry

logger = logging.getLogger("astrbot.core.aar.orchestrator")


@dataclass
class AssemblyContext:
    """装配上下文，承载一次请求的完整拼接状态。

    Attributes:
        agent: 当前关联的 AgentConfig。
        persona_id: Agent 绑定的 Persona ID（可能为 None）。
        raw_messages: ContextPolicy 处理前的原始消息列表。
        processed_messages: ContextPolicy 处理后的消息列表。
        system_prompt_parts: 按七大阶段分组的碎片文本。
        final_system_prompt: 拼接完成的最终 System Prompt。
        metadata: 附加元数据（如 evicted_count 等）。
    """

    agent: AgentConfig
    persona_id: str | None = None
    raw_messages: list[dict] = field(default_factory=list)
    processed_messages: list[dict] = field(default_factory=list)
    system_prompt_parts: dict[str, list[str]] = field(default_factory=dict)
    final_system_prompt: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """初始化每个阶段的碎片列表。"""
        for stage in PromptCategory.ALL:
            if stage not in self.system_prompt_parts:
                self.system_prompt_parts[stage] = []


class PipelineOrchestrator:
    """AAR 七阶段装配编排器。

    协调 PromptManager、AgentManager 和 ContextPolicyRegistry，
    完成一次完整的 System Prompt 装配。
    """

    def __init__(
        self,
        prompt_manager: PromptManager,
        agent_manager: AgentManager,
        context_policy_registry: ContextPolicyRegistry,
    ) -> None:
        self._prompt_mgr = prompt_manager
        self._agent_mgr = agent_manager
        self._ctx_policy = context_policy_registry

    async def assemble_request(
        self,
        agent_id: str | None = None,
        raw_messages: list[dict] | None = None,
        extra_context: dict[str, Any] | None = None,
    ) -> AssemblyContext:
        """执行完整的七阶段装配流程。

        Args:
            agent_id: 目标 Agent ID。None 使用系统默认 Agent。
            raw_messages: 原始对话消息列表（OpenAI 格式）。
            extra_context: 额外上下文信息，传递给 Functional providers 和 Template 渲染。

        Returns:
            AssemblyContext，包含最终的 system_prompt 和处理后的消息列表。
        """
        extra_context = extra_context or {}

        # Step 1: 解析 Agent
        agent = self._agent_mgr.resolve_agent(agent_id)
        ctx = AssemblyContext(
            agent=agent,
            persona_id=agent.persona_id,
            raw_messages=raw_messages or [],
        )
        logger.debug(
            "Assembling request for agent '%s' (persona=%s)",
            agent.agent_id,
            agent.persona_id,
        )

        # Step 2: 通过 ContextPolicy 处理消息
        policy_config = (agent.config or {}).copy()
        policy_result = await self._ctx_policy.apply_policy(
            policy_id=agent.context_policy,
            messages=ctx.raw_messages,
            config=policy_config,
        )
        ctx.processed_messages = policy_result.messages
        ctx.metadata["evicted_count"] = policy_result.evicted_count
        ctx.metadata["context_policy"] = agent.context_policy

        # Step 3: 获取 Agent 引用的所有 Prompts（按七大阶段+priority 排序）
        prompt_ids = agent.prompts or []
        sorted_prompts = self._prompt_mgr.get_sorted_prompts(
            prompt_ids=prompt_ids if prompt_ids else None,
            active_only=True,
        )

        # Step 4: 遍历 Prompts，解析各类型，填充到 system_prompt_parts
        template_context = {
            "agent": agent,
            "persona_id": agent.persona_id,
            "messages": ctx.processed_messages,
            **extra_context,
        }

        for entry in sorted_prompts:
            text = await self._resolve_entry(entry, template_context)
            if text:
                ctx.system_prompt_parts[entry.category].append(text)

        # Step 5: 严格按 Stage 1 -> Stage 7 顺序拼接
        parts: list[str] = []
        for stage in PromptCategory.ALL:
            stage_fragments = ctx.system_prompt_parts.get(stage, [])
            if stage_fragments:
                parts.append("\n\n".join(stage_fragments))

        ctx.final_system_prompt = "\n\n".join(parts)

        logger.debug(
            "Assembly complete: %d chars, %d stages with content, %d messages after policy",
            len(ctx.final_system_prompt),
            sum(1 for s in PromptCategory.ALL if ctx.system_prompt_parts.get(s)),
            len(ctx.processed_messages),
        )
        return ctx

    async def _resolve_entry(
        self, entry: PromptEntry, template_context: dict[str, Any]
    ) -> str | None:
        """解析单个 PromptEntry，返回文本内容。

        Args:
            entry: Prompt 条目。
            template_context: 模板和 functional 上下文。

        Returns:
            解析后的文本字符串，可能为 None。
        """
        if entry.type == "static":
            return entry.content or ""

        if entry.type == "template":
            return self._render_template(entry.content or "", template_context)

        if entry.type == "functional":
            return await self._prompt_mgr.resolve_functional(
                entry.prompt_id, template_context
            )

        logger.warning("Unknown prompt type '%s' for %s", entry.type, entry.prompt_id)
        return None

    @staticmethod
    def _render_template(template_str: str, context: dict[str, Any]) -> str:
        """渲染 Jinja2 模板。

        Args:
            template_str: Jinja2 模板字符串。
            context: 渲染上下文。

        Returns:
            渲染后的字符串。
        """
        try:
            from jinja2 import BaseLoader, Environment

            env = Environment(loader=BaseLoader(), autoescape=False)
            template = env.from_string(template_str)
            return template.render(**context)
        except ImportError:
            logger.warning(
                "jinja2 not installed, falling back to raw template content."
            )
            return template_str
        except Exception:
            logger.exception("Error rendering Jinja2 template.")
            return template_str
