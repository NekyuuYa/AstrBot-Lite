"""AAR Context Policy — 上下文策略注册器与默认实现。

ContextPolicy 将历史记录截断、总结等逻辑抽象为独立的策略引擎。
默认实现 `sys.batch_eviction` 采用批量弹出策略，保留稳定的前缀，
极大提高大模型 Prompt Caching 命中率。
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("astrbot.core.aar.context_policy")

# Context Policy 函数签名:
# async (messages, config, stats) -> list[dict]
ContextPolicyFn = Callable[
    [list[dict], dict[str, Any], dict[str, Any]],
    Coroutine[Any, Any, list[dict]],
]


@dataclass
class ContextPolicyResult:
    """上下文策略处理结果。

    Attributes:
        messages: 处理后的消息列表。
        evicted_count: 本次弹出的消息数量。
        metadata: 策略产出的附加元数据（如摘要文本）。
    """

    messages: list[dict] = field(default_factory=list)
    evicted_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


class ContextPolicyRegistry:
    """上下文策略注册表。

    职责：
    - 保存 policy_id -> ContextPolicyFn 的映射。
    - 提供 apply_policy() 方法执行策略。
    - 初始化时自动注册默认策略 `sys.batch_eviction`。
    """

    def __init__(self) -> None:
        self._policies: dict[str, ContextPolicyFn] = {}
        # 注册默认策略
        self.register("sys.batch_eviction", batch_eviction_policy)

    def register(self, policy_id: str, fn: ContextPolicyFn) -> None:
        """注册一个上下文策略。

        Args:
            policy_id: 策略唯一标识，如 'sys.batch_eviction'。
            fn: 异步策略函数。
        """
        self._policies[policy_id] = fn
        logger.debug("Registered context policy: %s", policy_id)

    def get_policy(self, policy_id: str) -> ContextPolicyFn | None:
        """获取策略函数。"""
        return self._policies.get(policy_id)

    async def apply_policy(
        self,
        policy_id: str,
        messages: list[dict],
        config: dict[str, Any] | None = None,
        stats: dict[str, Any] | None = None,
    ) -> ContextPolicyResult:
        """执行指定的上下文策略。

        Args:
            policy_id: 要执行的策略 ID。
            messages: 原始消息列表（OpenAI 格式的 list[dict]）。
            config: Agent 的 config 字典中传递的策略参数。
            stats: 运行时统计信息（如 token 用量、上下文窗口大小等）。

        Returns:
            ContextPolicyResult 包含处理后的消息和元数据。
        """
        fn = self._policies.get(policy_id)
        if fn is None:
            logger.warning(
                "Context policy '%s' not found, returning messages as-is.",
                policy_id,
            )
            return ContextPolicyResult(messages=messages)

        try:
            result_messages = await fn(messages, config or {}, stats or {})
            evicted = len(messages) - len(result_messages)
            return ContextPolicyResult(
                messages=result_messages,
                evicted_count=max(evicted, 0),
            )
        except Exception:
            logger.exception(
                "Error executing context policy '%s', returning messages as-is.",
                policy_id,
            )
            return ContextPolicyResult(messages=messages)

    @property
    def available_policies(self) -> list[str]:
        """返回所有已注册策略 ID 列表。"""
        return list(self._policies.keys())


# ======================================================================
# Default policy: sys.batch_eviction
# ======================================================================


async def batch_eviction_policy(
    messages: list[dict],
    config: dict[str, Any],
    stats: dict[str, Any],
) -> list[dict]:
    """批量弹出策略 (sys.batch_eviction)。

    当检测到消息数超过 window_size 上限时，从头部切断 evict_ratio 比例的
    非系统消息，保留 system 消息和近期对话。这使得 system prompt 及近期
    对话保持稳定的前缀，有利于 Prompt Caching 命中。

    Config 参数：
        window_size (int): 触发弹出的消息数阈值，默认 20。
        evict_ratio (float): 超出时弹出的比例，默认 0.3 (30%)。
        preserve_system (bool): 是否始终保留 role=system 的消息，默认 True。

    Stats 参数（可选）：
        max_context_tokens (int): 如果提供，使用 token 计数作为辅助判断。
        current_tokens (int): 当前上下文的 token 数。
    """
    window_size = int(config.get("window_size", 20))
    evict_ratio = float(config.get("evict_ratio", 0.3))
    preserve_system = bool(config.get("preserve_system", True))

    if len(messages) <= window_size:
        return messages

    # 计算需要弹出的消息数量
    overshoot = len(messages) - window_size
    evict_count = max(int(len(messages) * evict_ratio), overshoot)

    if preserve_system:
        # 分离 system 消息和非 system 消息
        system_msgs: list[dict] = []
        non_system_msgs: list[dict] = []
        for msg in messages:
            if msg.get("role") == "system":
                system_msgs.append(msg)
            else:
                non_system_msgs.append(msg)

        # 只对非 system 消息执行弹出（从头部删除）
        evict_count = min(evict_count, len(non_system_msgs))
        surviving_non_system = non_system_msgs[evict_count:]

        # 重新组合：system 消息在前，存活的非 system 消息在后
        result = system_msgs + surviving_non_system
    else:
        result = messages[evict_count:]

    logger.debug(
        "batch_eviction: %d -> %d messages (evicted %d, window=%d, ratio=%.2f)",
        len(messages),
        len(result),
        len(messages) - len(result),
        window_size,
        evict_ratio,
    )
    return result
