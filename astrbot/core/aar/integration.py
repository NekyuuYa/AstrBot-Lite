"""AAR Integration Bridge — 连接 AAR 编排系统与现有 main_agent 流水线。

本模块提供 `apply_aar_assembly()` 函数，在不破坏现有逻辑的前提下，
通过"旁路建设"策略让 AAR 的七阶段装配引擎逐步接管 System Prompt 构建。

使用方式：
    在 `_decorate_llm_request()` 中，如果检测到 AAR 已启用，
    调用本模块替代原有的硬编码拼接逻辑。
"""

from __future__ import annotations

import logging
from typing import Any

from astrbot.core.aar.agent_manager import AgentManager
from astrbot.core.aar.context_policy import ContextPolicyRegistry
from astrbot.core.aar.orchestrator import AssemblyContext, PipelineOrchestrator
from astrbot.core.aar.prompt_manager import PromptManager
from astrbot.core.db import BaseDatabase
from astrbot.core.db.po import PromptCategory

logger = logging.getLogger("astrbot.core.aar.integration")


async def seed_system_prompts(prompt_mgr: PromptManager) -> None:
    """注册系统内置的 Prompt 片段。

    在系统启动时调用，确保核心 Prompt 条目存在于注册表中。
    插件和用户后续可以覆盖或扩充这些条目。
    """
    # Stage 1: System Base — 安全底线
    await prompt_mgr.register_prompt(
        prompt_id="sys.safety",
        name="Safety Guidelines",
        category=PromptCategory.SYSTEM_BASE,
        priority=100,
        type="static",
        content=(
            "You are a helpful and honest AI assistant. "
            "You must refuse to generate harmful, illegal, or unethical content. "
            "Always prioritize user safety."
        ),
        source="system",
        is_readonly=True,
    )

    # Stage 6: Constraint — 默认输出约束
    await prompt_mgr.register_prompt(
        prompt_id="sys.output_constraint",
        name="Default Output Constraints",
        category=PromptCategory.CONSTRAINT,
        priority=50,
        type="static",
        content="",
        source="system",
        is_active=False,  # 默认不激活，用户可在 WebUI 启用并编辑内容
        is_readonly=True,
    )

    logger.info("System prompts seeded.")


async def apply_aar_assembly(
    prompt_mgr: PromptManager,
    agent_mgr: AgentManager,
    ctx_policy: ContextPolicyRegistry,
    agent_id: str | None = None,
    raw_messages: list[dict] | None = None,
    extra_context: dict[str, Any] | None = None,
) -> AssemblyContext:
    """执行 AAR 七阶段装配，返回完整的 AssemblyContext。

    这是 AAR 系统的主入口。调用方可以从返回的 context 中获取：
    - ctx.final_system_prompt: 替代原有 req.system_prompt
    - ctx.processed_messages: 替代原有 req.contexts
    - ctx.agent: 当前 Agent 配置信息

    Args:
        prompt_mgr: Prompt 注册表管理器。
        agent_mgr: Agent 配置管理器。
        ctx_policy: 上下文策略注册表。
        agent_id: 目标 Agent ID，None 使用默认。
        raw_messages: 原始对话消息。
        extra_context: 额外上下文信息。

    Returns:
        AssemblyContext，包含完整的装配结果。
    """
    orchestrator = PipelineOrchestrator(prompt_mgr, agent_mgr, ctx_policy)
    return await orchestrator.assemble_request(
        agent_id=agent_id,
        raw_messages=raw_messages,
        extra_context=extra_context,
    )


async def migrate_personas_to_registry(
    prompt_mgr: PromptManager,
    db: BaseDatabase,
) -> None:
    """将数据库中现有的 Persona system_prompt 迁移到 PromptRegistry。

    在系统启动时调用，将每个 Persona 的文本内容以 Identity 阶段的
    PromptEntry 形式归档。若该条目已存在，则跳过（幂等操作）。

    Args:
        prompt_mgr: Prompt 注册表管理器。
        db: 数据库实例，用于读取 Persona 表。
    """
    personas = await db.get_personas()
    if not personas:
        return

    migrated = 0
    for persona in personas:
        if not persona.system_prompt:
            continue

        prompt_id = f"persona.{persona.persona_id}"

        # 幂等：若已存在则跳过
        if prompt_mgr.get_entry(prompt_id) is not None:
            continue

        try:
            await prompt_mgr.register_prompt(
                prompt_id=prompt_id,
                name=f"Persona: {persona.persona_id}",
                category=PromptCategory.IDENTITY,
                priority=80,
                type="static",
                content=persona.system_prompt,
                source=f"persona:{persona.persona_id}",
                is_active=False,  # 默认不激活，保留历史记录；用户可通过 WebUI 按需启用
            )
            migrated += 1
        except Exception:
            logger.exception(
                "Failed to migrate persona '%s' to prompt registry.",
                persona.persona_id,
            )

    if migrated:
        logger.info(
            "Migrated %d persona(s) to PromptRegistry as Identity-stage entries.",
            migrated,
        )
