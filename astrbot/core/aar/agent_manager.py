"""AAR Agent Manager — Agent 智能体配置的 CRUD 管理。

AgentManager 提供：
- upsert_agent(): 创建/更新 Agent 配置
- get_agent() / get_agents(): 查询
- delete_agent(): 删除
- resolve_agent(): 智能查找，若不存在则返回系统默认 Agent
"""

from __future__ import annotations

import logging

from astrbot.core.db import BaseDatabase
from astrbot.core.db.po import AgentConfig

logger = logging.getLogger("astrbot.core.aar.agent_manager")

# 系统兜底 Agent ID
DEFAULT_AGENT_ID = "sys.default"


class AgentManager:
    """AAR Agent 配置管理器。

    维护 agent_id -> AgentConfig 的内存映射（启动时从 DB 加载）。
    """

    def __init__(self, db: BaseDatabase) -> None:
        self._db = db
        self._cache: dict[str, AgentConfig] = {}

    async def initialize(self) -> None:
        """从 DB 加载所有 Agent 到内存缓存，并确保系统默认 Agent 存在。"""
        agents = await self._db.get_agents()
        self._cache = {a.agent_id: a for a in agents}

        # 确保系统默认 Agent 始终存在
        if DEFAULT_AGENT_ID not in self._cache:
            default = await self._db.upsert_agent(
                agent_id=DEFAULT_AGENT_ID,
                name="Default Agent",
                prompts=["sys.safety"],
                context_policy="sys.batch_eviction",
                config={"window_size": 20, "evict_ratio": 0.3},
            )
            self._cache[DEFAULT_AGENT_ID] = default
            logger.info("Created system default agent: %s", DEFAULT_AGENT_ID)

        logger.info("AgentManager initialized with %d agents.", len(self._cache))

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    async def upsert_agent(
        self,
        agent_id: str,
        name: str,
        *,
        persona_id: str | None = None,
        prompts: list[str] | None = None,
        tools: list[str] | None = None,
        skills: list[str] | None = None,
        context_policy: str = "sys.batch_eviction",
        interceptors: list[str] | None = None,
        config: dict | None = None,
        tags: list[str] | None = None,
    ) -> AgentConfig:
        """创建或更新一个 Agent 配置。

        Args:
            agent_id: 唯一标识。
            name: 显示名称。
            persona_id: 关联的 Persona ID。
            prompts: 引用的 prompt_id 列表。
            tools: 白名单工具列表。
            skills: 白名单技能列表。
            context_policy: 上下文策略 ID。
            interceptors: 拦截器 ID 列表。
            config: 动态配置字典。
            tags: 检索标签。

        Returns:
            持久化后的 AgentConfig。
        """
        agent = await self._db.upsert_agent(
            agent_id,
            name,
            persona_id=persona_id,
            prompts=prompts,
            tools=tools,
            skills=skills,
            context_policy=context_policy,
            interceptors=interceptors,
            config=config,
            tags=tags,
        )
        self._cache[agent_id] = agent
        logger.debug("Upserted agent: %s", agent_id)
        return agent

    async def delete_agent(self, agent_id: str) -> None:
        """删除一个 Agent 配置。系统默认 Agent 不可删除。"""
        if agent_id == DEFAULT_AGENT_ID:
            raise ValueError("Cannot delete the system default agent.")
        await self._db.delete_agent(agent_id)
        self._cache.pop(agent_id, None)
        logger.debug("Deleted agent: %s", agent_id)

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_agent(self, agent_id: str) -> AgentConfig | None:
        """按 agent_id 获取 Agent 配置（从缓存）。"""
        return self._cache.get(agent_id)

    def get_agents(self, tag: str | None = None) -> list[AgentConfig]:
        """获取所有 Agent 配置，可按 tag 过滤。"""
        agents = list(self._cache.values())
        if tag is not None:
            agents = [a for a in agents if a.tags and tag in a.tags]
        return agents

    def resolve_agent(self, agent_id: str | None = None) -> AgentConfig:
        """智能解析 Agent：若指定 ID 不存在，优雅回退到系统默认 Agent。

        Args:
            agent_id: 目标 Agent ID。None 直接返回默认。

        Returns:
            AgentConfig 实例（保证不为 None）。
        """
        if agent_id and agent_id in self._cache:
            return self._cache[agent_id]
        if agent_id:
            logger.warning("Agent '%s' not found, falling back to default.", agent_id)
        return self._cache[DEFAULT_AGENT_ID]

    @property
    def default_agent(self) -> AgentConfig:
        """获取系统默认 Agent。"""
        return self._cache[DEFAULT_AGENT_ID]
