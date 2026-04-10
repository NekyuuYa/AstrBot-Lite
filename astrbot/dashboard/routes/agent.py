"""AAR Agent REST API — Agent 智能体配置的增删改查端点。

提供以下路由：
- GET    /api/agents          — 获取所有 Agent 列表
- GET    /api/agents/<id>     — 获取单个 Agent
- POST   /api/agents          — 创建 Agent
- PUT    /api/agents/<id>     — 更新 Agent
- DELETE /api/agents/<id>     — 删除 Agent
"""

from __future__ import annotations

import logging
from dataclasses import asdict

from quart import request

from astrbot.core.aar.agent_manager import AgentManager
from astrbot.dashboard.routes.route import Response, Route, RouteContext

logger = logging.getLogger("astrbot.dashboard.routes.agent")


class AgentRoute(Route):
    """AAR Agent CRUD REST API 路由。"""

    def __init__(
        self,
        context: RouteContext,
        agent_manager: AgentManager,
    ) -> None:
        super().__init__(context)
        self._agent_mgr = agent_manager

        self.routes = [
            ("/agents", [("GET", self.list_agents), ("POST", self.create_agent)]),
            (
                "/agents/<agent_id>",
                [
                    ("GET", self.get_agent),
                    ("PUT", self.update_agent),
                    ("DELETE", self.delete_agent),
                ],
            ),
        ]
        self.register_routes()

    async def list_agents(self) -> dict:
        """GET /api/agents — 获取所有 Agent 列表。"""
        tag = request.args.get("tag")
        agents = self._agent_mgr.get_agents(tag=tag)
        data = [_agent_to_dict(a) for a in agents]
        return Response().ok(data).__dict__

    async def get_agent(self, agent_id: str) -> dict:
        """GET /api/agents/<agent_id> — 获取单个 Agent。"""
        agent = self._agent_mgr.get_agent(agent_id)
        if not agent:
            return Response().error(f"Agent '{agent_id}' not found.").__dict__
        return Response().ok(_agent_to_dict(agent)).__dict__

    async def create_agent(self) -> dict:
        """POST /api/agents — 创建 Agent。"""
        body = await request.get_json()
        if not body:
            return Response().error("Request body is required.").__dict__

        agent_id = body.get("agent_id")
        name = body.get("name")
        if not agent_id or not name:
            return Response().error("'agent_id' and 'name' are required.").__dict__

        existing = self._agent_mgr.get_agent(agent_id)
        if existing:
            return Response().error(f"Agent '{agent_id}' already exists.").__dict__

        agent = await self._agent_mgr.upsert_agent(
            agent_id=agent_id,
            name=name,
            persona_id=body.get("persona_id"),
            prompts=body.get("prompts"),
            tools=body.get("tools"),
            skills=body.get("skills"),
            context_policy=body.get("context_policy", "sys.batch_eviction"),
            interceptors=body.get("interceptors"),
            config=body.get("config"),
            tags=body.get("tags"),
        )
        return Response().ok(_agent_to_dict(agent), "Agent created.").__dict__

    async def update_agent(self, agent_id: str) -> dict:
        """PUT /api/agents/<agent_id> — 更新 Agent。"""
        body = await request.get_json()
        if not body:
            return Response().error("Request body is required.").__dict__

        existing = self._agent_mgr.get_agent(agent_id)
        if not existing:
            return Response().error(f"Agent '{agent_id}' not found.").__dict__

        agent = await self._agent_mgr.upsert_agent(
            agent_id=agent_id,
            name=body.get("name", existing.name),
            persona_id=body.get("persona_id", existing.persona_id),
            prompts=body.get("prompts", existing.prompts),
            tools=body.get("tools", existing.tools),
            skills=body.get("skills", existing.skills),
            context_policy=body.get("context_policy", existing.context_policy),
            interceptors=body.get("interceptors", existing.interceptors),
            config=body.get("config", existing.config),
            tags=body.get("tags", existing.tags),
        )
        return Response().ok(_agent_to_dict(agent), "Agent updated.").__dict__

    async def delete_agent(self, agent_id: str) -> dict:
        """DELETE /api/agents/<agent_id> — 删除 Agent。"""
        try:
            await self._agent_mgr.delete_agent(agent_id)
        except ValueError as exc:
            return Response().error(str(exc)).__dict__
        return Response().ok(message="Agent deleted.").__dict__


def _agent_to_dict(agent) -> dict:
    """将 AgentConfig SQLModel 转换为 JSON 可序列化的字典。"""
    return {
        "agent_id": agent.agent_id,
        "name": agent.name,
        "persona_id": agent.persona_id,
        "prompts": agent.prompts,
        "tools": agent.tools,
        "skills": agent.skills,
        "context_policy": agent.context_policy,
        "interceptors": agent.interceptors,
        "config": agent.config,
        "tags": agent.tags,
        "created_at": str(agent.created_at) if agent.created_at else None,
        "updated_at": str(agent.updated_at) if agent.updated_at else None,
    }
