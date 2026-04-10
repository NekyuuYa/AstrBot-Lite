"""AAR Prompt REST API — Prompt 注册表条目的查询与管理端点。

提供以下路由：
- GET    /api/prompts              — 获取所有 Prompt 列表（支持过滤）
- GET    /api/prompts/<prompt_id>  — 获取单个 Prompt
- POST   /api/prompts              — 创建/更新 Prompt
- PUT    /api/prompts/<prompt_id>  — 更新 Prompt
- DELETE /api/prompts/<prompt_id>  — 删除 Prompt
"""

from __future__ import annotations

import logging

from quart import request

from astrbot.core.aar.prompt_manager import PromptManager
from astrbot.core.db.po import PromptCategory
from astrbot.dashboard.routes.route import Response, Route, RouteContext

logger = logging.getLogger("astrbot.dashboard.routes.prompt")


class PromptRoute(Route):
    """AAR Prompt Registry CRUD REST API 路由。"""

    def __init__(
        self,
        context: RouteContext,
        prompt_manager: PromptManager,
    ) -> None:
        super().__init__(context)
        self._prompt_mgr = prompt_manager

        self.routes = [
            ("/prompts", [("GET", self.list_prompts), ("POST", self.create_prompt)]),
            (
                "/prompts/<prompt_id>",
                [
                    ("GET", self.get_prompt),
                    ("PUT", self.update_prompt),
                    ("DELETE", self.delete_prompt),
                ],
            ),
            ("/prompts/stages", ("GET", self.list_stages)),
        ]
        self.register_routes()

    async def list_prompts(self) -> dict:
        """GET /api/prompts — 获取所有 Prompt 列表。

        Query params:
            category: 按阶段过滤
            source: 按来源过滤
            active_only: 是否仅返回激活的条目（默认 true）
        """
        category = request.args.get("category")
        source = request.args.get("source")
        active_only = request.args.get("active_only", "true").lower() != "false"

        if category:
            entries = self._prompt_mgr.get_entries_by_category(
                category, active_only=active_only
            )
        else:
            entries = self._prompt_mgr.get_sorted_prompts(active_only=active_only)

        if source:
            entries = [e for e in entries if e.source == source]

        data = [_prompt_to_dict(e) for e in entries]
        return Response().ok(data).__dict__

    async def get_prompt(self, prompt_id: str) -> dict:
        """GET /api/prompts/<prompt_id> — 获取单个 Prompt。"""
        entry = self._prompt_mgr.get_entry(prompt_id)
        if not entry:
            return Response().error(f"Prompt '{prompt_id}' not found.").__dict__
        return Response().ok(_prompt_to_dict(entry)).__dict__

    async def create_prompt(self) -> dict:
        """POST /api/prompts — 创建或更新 Prompt。"""
        body = await request.get_json()
        if not body:
            return Response().error("Request body is required.").__dict__

        prompt_id = body.get("prompt_id")
        name = body.get("name")
        category = body.get("category")

        if not prompt_id or not name or not category:
            return (
                Response()
                .error("'prompt_id', 'name', and 'category' are required.")
                .__dict__
            )

        if category not in PromptCategory.ALL:
            return (
                Response()
                .error(
                    f"Invalid category '{category}'. Must be one of: {PromptCategory.ALL}"
                )
                .__dict__
            )

        entry = await self._prompt_mgr.register_prompt(
            prompt_id=prompt_id,
            name=name,
            category=category,
            priority=body.get("priority", 50),
            type=body.get("type", "static"),
            content=body.get("content"),
            source=body.get("source", "user"),
            is_active=body.get("is_active", True),
        )
        return Response().ok(_prompt_to_dict(entry), "Prompt saved.").__dict__

    async def update_prompt(self, prompt_id: str) -> dict:
        """PUT /api/prompts/<prompt_id> — 更新 Prompt。"""
        body = await request.get_json()
        if not body:
            return Response().error("Request body is required.").__dict__

        existing = self._prompt_mgr.get_entry(prompt_id)
        if not existing:
            return Response().error(f"Prompt '{prompt_id}' not found.").__dict__

        category = body.get("category", existing.category)
        if category not in PromptCategory.ALL:
            return (
                Response()
                .error(
                    f"Invalid category '{category}'. Must be one of: {PromptCategory.ALL}"
                )
                .__dict__
            )

        entry = await self._prompt_mgr.register_prompt(
            prompt_id=prompt_id,
            name=body.get("name", existing.name),
            category=category,
            priority=body.get("priority", existing.priority),
            type=body.get("type", existing.type),
            content=body.get("content", existing.content),
            source=body.get("source", existing.source),
            is_active=body.get("is_active", existing.is_active),
        )
        return Response().ok(_prompt_to_dict(entry), "Prompt updated.").__dict__

    async def delete_prompt(self, prompt_id: str) -> dict:
        """DELETE /api/prompts/<prompt_id> — 删除 Prompt。"""
        existing = self._prompt_mgr.get_entry(prompt_id)
        if not existing:
            return Response().error(f"Prompt '{prompt_id}' not found.").__dict__

        await self._prompt_mgr.unregister_prompt(prompt_id)
        return Response().ok(message="Prompt deleted.").__dict__

    async def list_stages(self) -> dict:
        """GET /api/prompts/stages — 获取七大阶段枚举描述。"""
        stages = [
            {
                "id": PromptCategory.SYSTEM_BASE,
                "order": 1,
                "name": "System Base",
                "description": "全局最底层协议（首因效应最强点）",
            },
            {
                "id": PromptCategory.IDENTITY,
                "order": 2,
                "name": "Identity",
                "description": "确立'我是谁'——Persona 身份设定",
            },
            {
                "id": PromptCategory.CONTEXT,
                "order": 3,
                "name": "Context",
                "description": "确立'我们在聊什么'——历史记录",
            },
            {
                "id": PromptCategory.ABILITIES,
                "order": 4,
                "name": "Abilities",
                "description": "确立'我能做什么'——Tools/Skills",
            },
            {
                "id": PromptCategory.INSTRUCTION,
                "order": 5,
                "name": "Instructions",
                "description": "确立'我现在要做什么'——任务指令",
            },
            {
                "id": PromptCategory.CONSTRAINT,
                "order": 6,
                "name": "Constraints",
                "description": "否定性或强制性约束（近因效应最强点）",
            },
            {
                "id": PromptCategory.REFINEMENT,
                "order": 7,
                "name": "Refinement",
                "description": "最后的修饰——Interceptors/Legacy",
            },
        ]
        return Response().ok(stages).__dict__


def _prompt_to_dict(entry) -> dict:
    """将 PromptEntry SQLModel 转换为 JSON 可序列化的字典。"""
    return {
        "prompt_id": entry.prompt_id,
        "name": entry.name,
        "category": entry.category,
        "priority": entry.priority,
        "type": entry.type,
        "content": entry.content,
        "source": entry.source,
        "is_active": entry.is_active,
        "created_at": str(entry.created_at) if entry.created_at else None,
        "updated_at": str(entry.updated_at) if entry.updated_at else None,
    }
