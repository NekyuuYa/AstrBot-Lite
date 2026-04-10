"""AAR Legacy Adapter — 旧插件兼容 Persona 代理拦截器。

PersonaProxy 包装原有 Persona (Personality TypedDict) 对象。当旧插件尝试
对 persona["prompt"] 执行 += 拼接操作时，触发拦截：
1. 计算 new_prompt - old_prompt，提取插件注入的增量文本。
2. 通过 inspect 分析调用栈，提取发起拼接的插件包名/文件名。
3. 自动调用 PromptManager.register_prompt() 将增量归档为 Legacy 类型条目。
4. 记录警告日志，告知管理员某旧插件发起了不透明注入。
"""

from __future__ import annotations

import copy
import inspect
import logging
import re
from typing import Any

from astrbot.core.db.po import PromptCategory

logger = logging.getLogger("astrbot.core.aar.legacy_adapter")


def _extract_plugin_name_from_stack() -> str:
    """分析调用栈，提取发起 persona prompt 拼接的插件标识。

    遍历调用栈帧，查找位于 plugins/ 或 star/ 目录下的调用方，
    从文件路径中提取插件名称。

    Returns:
        插件名称字符串，未识别时返回 "unknown"。
    """
    for frame_info in inspect.stack():
        filename = frame_info.filename or ""
        # 常见的插件目录模式
        for pattern in (
            r"[/\\]addons[/\\]plugins[/\\]([^/\\]+)",
            r"[/\\]plugins[/\\]([^/\\]+)",
            r"[/\\]star[/\\]([^/\\]+)",
        ):
            match = re.search(pattern, filename)
            if match:
                return match.group(1)
    return "unknown"


class PersonaProxy(dict):
    """Persona 代理拦截器。

    继承 dict 以完全兼容 Personality TypedDict 的访问模式。
    当检测到 "prompt" 字段被修改时，计算 diff 并归档为 Legacy Prompt。

    Usage:
        original_persona = persona_manager.get_persona_v3(...)
        proxy = PersonaProxy(original_persona, prompt_manager=prompt_mgr)
        # 传递给旧插件：plugin.on_persona(proxy)
        # 旧插件执行 proxy["prompt"] += "额外指令" 时会触发拦截
    """

    def __init__(
        self,
        data: dict[str, Any],
        prompt_manager: Any = None,
    ) -> None:
        """初始化代理。

        Args:
            data: 原始 Personality TypedDict 数据。
            prompt_manager: PromptManager 实例（可选，传入时启用自动归档）。
        """
        super().__init__(data)
        self._original_prompt: str = str(data.get("prompt", ""))
        self._prompt_manager = prompt_manager
        self._intercepted_fragments: list[dict[str, str]] = []

    def __deepcopy__(self, memo: dict[int, Any]) -> PersonaProxy:
        copied = PersonaProxy(
            copy.deepcopy(dict(self), memo), prompt_manager=self._prompt_manager
        )
        copied._original_prompt = self._original_prompt
        memo[id(self)] = copied
        return copied

    def __setitem__(self, key: str, value: Any) -> None:
        """拦截 persona["prompt"] = ... 的赋值操作。"""
        if key == "prompt":
            old_prompt = self.get("prompt", "")
            new_prompt = str(value)
            self._detect_and_archive(old_prompt, new_prompt)
        super().__setitem__(key, value)

    def _detect_and_archive(self, old_prompt: str, new_prompt: str) -> None:
        """检测 prompt 变更并归档为 Legacy Prompt 条目。

        Args:
            old_prompt: 修改前的 prompt 文本。
            new_prompt: 修改后的 prompt 文本。
        """
        if not new_prompt or new_prompt == old_prompt:
            return

        # 计算 diff：移除旧内容后剩余的就是插件注入的增量
        diff = new_prompt
        if old_prompt and new_prompt.startswith(old_prompt):
            diff = new_prompt[len(old_prompt) :]
        elif old_prompt and new_prompt.endswith(old_prompt):
            diff = new_prompt[: len(new_prompt) - len(old_prompt)]

        diff = diff.strip()
        if not diff:
            return

        plugin_name = _extract_plugin_name_from_stack()
        prompt_id = f"legacy.{plugin_name}.auto"

        self._intercepted_fragments.append(
            {
                "plugin": plugin_name,
                "prompt_id": prompt_id,
                "fragment": diff,
            }
        )

        logger.warning(
            "[AAR Legacy Adapter] Plugin '%s' injected %d chars into persona prompt. "
            "Fragment archived as '%s' in Refinement stage. "
            "Consider migrating to PromptManager.register_prompt() API.",
            plugin_name,
            len(diff),
            prompt_id,
        )

        # 如果有 PromptManager，异步归档（fire-and-forget 在调用方处理）
        if self._prompt_manager is not None:
            self._pending_archive = {
                "prompt_id": prompt_id,
                "name": f"Legacy: {plugin_name}",
                "category": PromptCategory.REFINEMENT,
                "priority": 10,
                "type": "static",
                "content": diff,
                "source": f"legacy:{plugin_name}",
            }

    async def flush_archives(self) -> None:
        """将所有待归档的 Legacy Prompt 持久化到 PromptManager。

        应在插件执行完毕后调用。
        """
        if self._prompt_manager is None:
            return

        for fragment in self._intercepted_fragments:
            try:
                await self._prompt_manager.register_prompt(
                    prompt_id=fragment["prompt_id"],
                    name=f"Legacy: {fragment['plugin']}",
                    category=PromptCategory.REFINEMENT,
                    priority=10,
                    type="static",
                    content=fragment["fragment"],
                    source=f"legacy:{fragment['plugin']}",
                    is_readonly=True,
                )
            except Exception:
                logger.exception(
                    "Failed to archive legacy prompt for plugin: %s",
                    fragment["plugin"],
                )

        self._intercepted_fragments.clear()

    @property
    def intercepted_fragments(self) -> list[dict[str, str]]:
        """获取已拦截的片段列表（只读）。"""
        return list(self._intercepted_fragments)

    @property
    def original_prompt(self) -> str:
        """获取未被修改的原始 prompt。"""
        return self._original_prompt


async def flush_all_persona_proxy_archives(
    personas: list[dict[str, Any]],
) -> None:
    """对给定的 persona 列表批量 flush 所有 PersonaProxy 的归档。

    当 personas 列表包含 PersonaProxy 对象时，提取它们并调用 flush_archives()。

    Args:
        personas: personas_v3 列表（可能包含 PersonaProxy 对象）。
    """
    if not personas:
        return

    for persona in personas:
        if isinstance(persona, PersonaProxy):
            try:
                await persona.flush_archives()
            except Exception:
                logger.exception(
                    "Failed to flush archives for persona: %s",
                    persona.get("name", "unknown"),
                )


class RequestSnapshot:
    """请求快照与拦截器。

    在 Pipeline 装配完成后，调用插件钩子前对 req 进行快照。
    钩子运行后，对比 system_prompt、prompt 和 contexts 是否被旧插件非法篡改，
    并将篡改内容隔离至 AAR 注册表，同时发出警告日志。
    """

    def __init__(self, req: Any) -> None:
        self.req = req
        self.orig_system_prompt = req.system_prompt or ""
        self.orig_prompt = req.prompt or ""
        # 简单浅拷贝 list 进行比对
        self.orig_contexts = list(req.contexts) if req.contexts else []

    async def compare_and_archive(self, prompt_manager: Any) -> None:
        """对比修改并执行隔离归档。

        Args:
            prompt_manager: AAR PromptManager 实例。
        """
        new_system_prompt = self.req.system_prompt or ""
        if new_system_prompt != self.orig_system_prompt:
            diff = new_system_prompt
            if self.orig_system_prompt and new_system_prompt.startswith(
                self.orig_system_prompt
            ):
                diff = new_system_prompt[len(self.orig_system_prompt) :]
            elif self.orig_system_prompt and new_system_prompt.endswith(
                self.orig_system_prompt
            ):
                diff = new_system_prompt[
                    : len(new_system_prompt) - len(self.orig_system_prompt)
                ]

            diff = diff.strip()
            if diff:
                plugin_name = _extract_plugin_name_from_stack()
                prompt_id = f"legacy.{plugin_name}.dirty_inject"
                logger.warning(
                    "[AAR Legacy Sandbox] 插件 '%s' 非法修改了 req.system_prompt。 "
                    "已将修改内容 (%d chars) 隔离至 Stage 4.5 (Refinement)。",
                    plugin_name,
                    len(diff),
                )
                if prompt_manager:
                    try:
                        await prompt_manager.register_prompt(
                            prompt_id=prompt_id,
                            name=f"Dirty Inject: {plugin_name}",
                            category=PromptCategory.REFINEMENT,
                            priority=10,
                            type="static",
                            content=diff,
                            source=f"legacy:{plugin_name}",
                        )
                    except Exception:
                        logger.exception("Failed to archive dirty inject.")

            # 恢复为 AAR Pipeline 装配的纯净版（可选：如果强行隔离，则重置 req.system_prompt）
            # self.req.system_prompt = self.orig_system_prompt

        new_prompt = self.req.prompt or ""
        if new_prompt != self.orig_prompt:
            logger.warning(
                "[AAR Legacy Sandbox] 检测到插件可能强制包裹了 req.prompt。 "
                "建议开发者使用 Instruction 阶段的 PromptEntry 进行指令注入。"
            )

        new_contexts = self.req.contexts or []
        if len(new_contexts) != len(self.orig_contexts):
            logger.warning(
                "[AAR Legacy Sandbox] 检测到插件擅自增删了 req.contexts。 "
                "请尽快迁移至 ContextPolicy 进行上下文管理。"
            )
