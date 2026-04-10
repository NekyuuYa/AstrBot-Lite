"""Tests for astrbot.core.aar.context_policy."""

import pytest

from astrbot.core.aar.context_policy import (
    ContextPolicyRegistry,
    ContextPolicyResult,
    batch_eviction_policy,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _msgs(n: int, include_system: bool = False) -> list[dict]:
    """Build a list of n user/assistant messages, optionally with a system prefix."""
    result = []
    if include_system:
        result.append({"role": "system", "content": "system prompt"})
    for i in range(n):
        role = "user" if i % 2 == 0 else "assistant"
        result.append({"role": role, "content": f"msg {i}"})
    return result


# ---------------------------------------------------------------------------
# ContextPolicyRegistry
# ---------------------------------------------------------------------------

class TestContextPolicyRegistry:
    def test_default_policy_registered_on_init(self):
        reg = ContextPolicyRegistry()
        assert "sys.batch_eviction" in reg.available_policies

    def test_register_custom_policy(self):
        reg = ContextPolicyRegistry()

        async def my_policy(msgs, cfg, stats):
            return msgs

        reg.register("custom.policy", my_policy)
        assert "custom.policy" in reg.available_policies

    def test_get_policy_returns_registered_fn(self):
        reg = ContextPolicyRegistry()

        async def fn(msgs, cfg, stats):
            return msgs

        reg.register("p.test", fn)
        assert reg.get_policy("p.test") is fn

    def test_get_policy_unknown_returns_none(self):
        reg = ContextPolicyRegistry()
        assert reg.get_policy("no.such.policy") is None

    @pytest.mark.asyncio
    async def test_apply_policy_unknown_returns_messages_unchanged(self):
        reg = ContextPolicyRegistry()
        msgs = _msgs(5)
        result = await reg.apply_policy("no.such.policy", msgs)

        assert isinstance(result, ContextPolicyResult)
        assert result.messages == msgs
        assert result.evicted_count == 0

    @pytest.mark.asyncio
    async def test_apply_policy_with_exception_returns_messages_unchanged(self):
        reg = ContextPolicyRegistry()

        async def bad_fn(msgs, cfg, stats):
            raise RuntimeError("boom")

        reg.register("bad.policy", bad_fn)
        msgs = _msgs(5)
        result = await reg.apply_policy("bad.policy", msgs)

        assert result.messages == msgs
        assert result.evicted_count == 0

    @pytest.mark.asyncio
    async def test_apply_policy_counts_evicted(self):
        reg = ContextPolicyRegistry()
        msgs = _msgs(30)  # exceeds default window of 20
        result = await reg.apply_policy("sys.batch_eviction", msgs)

        assert result.evicted_count > 0
        assert result.evicted_count == 30 - len(result.messages)

    @pytest.mark.asyncio
    async def test_available_policies_lists_all(self):
        reg = ContextPolicyRegistry()
        reg.register("extra.one", lambda m, c, s: m)
        assert "sys.batch_eviction" in reg.available_policies
        assert "extra.one" in reg.available_policies


# ---------------------------------------------------------------------------
# batch_eviction_policy — unit tests for the raw function
# ---------------------------------------------------------------------------

class TestBatchEvictionPolicy:
    @pytest.mark.asyncio
    async def test_no_eviction_when_under_window(self):
        msgs = _msgs(10)
        result = await batch_eviction_policy(msgs, {"window_size": 20}, {})
        assert result == msgs

    @pytest.mark.asyncio
    async def test_no_eviction_at_exact_window(self):
        msgs = _msgs(20)
        result = await batch_eviction_policy(msgs, {"window_size": 20}, {})
        assert result == msgs

    @pytest.mark.asyncio
    async def test_evicts_when_over_window(self):
        msgs = _msgs(30)
        result = await batch_eviction_policy(msgs, {"window_size": 20, "evict_ratio": 0.3}, {})
        assert len(result) < 30

    @pytest.mark.asyncio
    async def test_preserve_system_keeps_system_message(self):
        msgs = _msgs(25, include_system=True)
        result = await batch_eviction_policy(
            msgs,
            {"window_size": 20, "evict_ratio": 0.5, "preserve_system": True},
            {},
        )
        system_msgs = [m for m in result if m["role"] == "system"]
        assert len(system_msgs) == 1
        assert system_msgs[0]["content"] == "system prompt"

    @pytest.mark.asyncio
    async def test_no_preserve_system_may_evict_system(self):
        # With preserve_system=False, we just slice from the head — system can be gone
        msgs = _msgs(30, include_system=True)
        result = await batch_eviction_policy(
            msgs,
            {"window_size": 5, "evict_ratio": 0.9, "preserve_system": False},
            {},
        )
        # Result is shorter — system message might or might not survive depending on slice
        assert len(result) < len(msgs)

    @pytest.mark.asyncio
    async def test_evicts_from_head_of_non_system_messages(self):
        """Evicted messages should be the oldest non-system messages."""
        msgs = _msgs(25, include_system=True)
        # The first non-system message has content "msg 0"
        result = await batch_eviction_policy(
            msgs,
            {"window_size": 20, "evict_ratio": 0.5, "preserve_system": True},
            {},
        )
        # System message survives
        assert result[0]["role"] == "system"
        # Oldest non-system messages are gone; newest survive
        non_system_remaining = [m for m in result if m["role"] != "system"]
        non_system_original = [m for m in msgs if m["role"] != "system"]
        # Remaining should be a suffix of the original non-system list
        suffix_len = len(non_system_remaining)
        assert non_system_remaining == non_system_original[-suffix_len:]

    @pytest.mark.asyncio
    async def test_custom_window_size(self):
        msgs = _msgs(10)
        result = await batch_eviction_policy(msgs, {"window_size": 5, "evict_ratio": 0.5}, {})
        assert len(result) < 10

    @pytest.mark.asyncio
    async def test_default_config_values(self):
        """Calling with empty config should use defaults (window=20, ratio=0.3)."""
        msgs = _msgs(30)
        result = await batch_eviction_policy(msgs, {}, {})
        assert len(result) < 30

    @pytest.mark.asyncio
    async def test_empty_message_list_returns_empty(self):
        result = await batch_eviction_policy([], {}, {})
        assert result == []
