"""AAR Prompt Manager — 集中管理所有 Prompt 片段的注册表。

PromptManager 维护一个内存缓存 + DB 持久层，提供：
- register_prompt(): 注册/更新一个 Prompt 条目
- unregister_prompt(): 移除一个 Prompt 条目
- get_sorted_prompts(): 按七大阶段排序返回指定 prompt_id 集合的条目列表
- register_functional_provider(): 注册 functional 类型的回调
- resolve_functional(): 执行并获取 functional 类型 prompt 的输出
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Coroutine
from typing import Any

from astrbot.core.db import BaseDatabase
from astrbot.core.db.po import PromptCategory, PromptEntry

logger = logging.getLogger("astrbot.core.aar.prompt_manager")

# 阶段名 -> 排序权重，值越小排越前（即 Stage 1 物理位置在最前面）
_CATEGORY_ORDER: dict[str, int] = {
    stage: idx for idx, stage in enumerate(PromptCategory.ALL)
}

# Functional provider 回调签名: async (context: dict[str, Any]) -> str
FunctionalProvider = Callable[[dict[str, Any]], Coroutine[Any, Any, str]]


class PromptManager:
    """AAR Prompt 注册表管理器。

    职责：
    1. 维护 prompt_id -> PromptEntry 的内存映射（启动时从 DB 加载）。
    2. 维护 prompt_id -> FunctionalProvider 的回调映射表。
    3. 提供 get_sorted_prompts() 方法，严格按七大阶段 + priority 排序。
    """

    def __init__(self, db: BaseDatabase) -> None:
        self._db = db
        self._cache: dict[str, PromptEntry] = {}
        self._functional_providers: dict[str, FunctionalProvider] = {}

    async def initialize(self) -> None:
        """从 DB 加载所有 Prompt 条目到内存缓存。"""
        entries = await self._db.get_prompt_entries(active_only=False)
        self._cache = {e.prompt_id: e for e in entries}
        logger.info(
            "PromptManager initialized with %d entries from DB.", len(self._cache)
        )

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    async def register_prompt(
        self,
        prompt_id: str,
        name: str,
        category: str,
        *,
        priority: int = 50,
        type: str = "static",
        content: str | None = None,
        source: str = "system",
        is_active: bool = True,
        is_readonly: bool = False,
    ) -> PromptEntry:
        """注册或更新一个 Prompt 条目（同时写入 DB 和内存缓存）。

        Args:
            prompt_id: 唯一字符串标识，如 'sys.safety'。
            name: 易读的展示名称。
            category: 七大阶段之一，参见 PromptCategory。
            priority: 同 category 内排序权重（越大越靠前），默认 50。
            type: 'static' | 'template' | 'functional'。
            content: 静态正文或 Jinja2 模板。functional 类型可为 None。
            source: 来源标识，如 'system', 'plugin:xxx', 'user'。
            is_active: 是否启用。
            is_readonly: 是否只读（如 True 则禁止 WebUI 编辑），常用于系统和 legacy prompt。

        Returns:
            持久化后的 PromptEntry。
        """
        if category not in _CATEGORY_ORDER:
            raise ValueError(
                f"Invalid category '{category}'. Must be one of {PromptCategory.ALL}"
            )
        entry = await self._db.upsert_prompt_entry(
            prompt_id,
            name,
            category,
            priority=priority,
            type=type,
            content=content,
            source=source,
            is_active=is_active,
            is_readonly=is_readonly,
        )
        self._cache[prompt_id] = entry
        logger.debug("Registered prompt: %s (category=%s, source=%s)", prompt_id, category, source)
        return entry

    async def unregister_prompt(self, prompt_id: str) -> None:
        """移除一个 Prompt 条目。"""
        await self._db.delete_prompt_entry(prompt_id)
        self._cache.pop(prompt_id, None)
        self._functional_providers.pop(prompt_id, None)
        logger.debug("Unregistered prompt: %s", prompt_id)

    def register_functional_provider(
        self, prompt_id: str, provider: FunctionalProvider
    ) -> None:
        """注册 functional 类型 Prompt 的异步回调函数。

        Args:
            prompt_id: 对应 PromptEntry 的 prompt_id。
            provider: 异步函数，签名 async (context: dict) -> str。
        """
        self._functional_providers[prompt_id] = provider
        logger.debug("Registered functional provider for: %s", prompt_id)

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_sorted_prompts(
        self,
        prompt_ids: list[str] | None = None,
        active_only: bool = True,
    ) -> list[PromptEntry]:
        """取出指定 ID 的 Prompt 实体，按七大阶段 + priority 排序。

        排序规则：
        - 第一排序键：category 在七大阶段中的物理顺序（Stage 1 -> Stage 7）。
        - 第二排序键：priority 降序（数字越大越靠前）。

        Args:
            prompt_ids: 要获取的 prompt_id 列表。None 表示获取所有。
            active_only: 是否仅返回 is_active=True 的条目。

        Returns:
            排序后的 PromptEntry 列表。
        """
        if prompt_ids is not None:
            entries = [
                self._cache[pid] for pid in prompt_ids if pid in self._cache
            ]
        else:
            entries = list(self._cache.values())

        if active_only:
            entries = [e for e in entries if e.is_active]

        entries.sort(
            key=lambda e: (
                _CATEGORY_ORDER.get(e.category, 999),
                -e.priority,
            )
        )
        return entries

    def get_entry(self, prompt_id: str) -> PromptEntry | None:
        """按 ID 获取单个 Prompt 条目。"""
        return self._cache.get(prompt_id)

    def get_entries_by_category(
        self, category: str, active_only: bool = True
    ) -> list[PromptEntry]:
        """获取某一阶段的全部条目。"""
        entries = [e for e in self._cache.values() if e.category == category]
        if active_only:
            entries = [e for e in entries if e.is_active]
        entries.sort(key=lambda e: -e.priority)
        return entries

    # ------------------------------------------------------------------
    # Functional resolution
    # ------------------------------------------------------------------

    async def resolve_functional(
        self, prompt_id: str, context: dict[str, Any] | None = None
    ) -> str | None:
        """执行 functional 类型 Prompt 的回调并返回结果。

        Args:
            prompt_id: 要执行的 functional prompt 的 ID。
            context: 传递给回调的上下文字典。

        Returns:
            回调返回的字符串，或 None（如果未注册回调）。
        """
        provider = self._functional_providers.get(prompt_id)
        if provider is None:
            logger.warning(
                "No functional provider registered for prompt: %s", prompt_id
            )
            return None
        try:
            return await provider(context or {})
        except Exception:
            logger.exception(
                "Error executing functional provider for prompt: %s", prompt_id
            )
            return None

    @property
    def all_entries(self) -> dict[str, PromptEntry]:
        """获取全部内存缓存条目（只读视图）。"""
        return dict(self._cache)
