"""Tests for astrbot.core.aar.prompt_manager.PromptManager."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from astrbot.core.aar.prompt_manager import PromptManager
from astrbot.core.db.po import PromptCategory, PromptEntry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_entry(
    prompt_id: str,
    category: str = PromptCategory.SYSTEM_BASE,
    priority: int = 50,
    is_active: bool = True,
    type: str = "static",
    content: str | None = "hello",
) -> PromptEntry:
    return PromptEntry(
        prompt_id=prompt_id,
        name=f"Entry {prompt_id}",
        category=category,
        priority=priority,
        type=type,
        content=content,
        source="system",
        is_active=is_active,
    )


def _make_db(entries: list[PromptEntry] | None = None) -> MagicMock:
    db = MagicMock()
    db.get_prompt_entries = AsyncMock(return_value=entries or [])
    db.upsert_prompt_entry = AsyncMock(side_effect=lambda pid, name, cat, **kw: _make_entry(
        pid, category=cat,
        priority=kw.get("priority", 50),
        is_active=kw.get("is_active", True),
        type=kw.get("type", "static"),
        content=kw.get("content"),
    ))
    db.delete_prompt_entry = AsyncMock()
    return db


# ---------------------------------------------------------------------------
# initialize()
# ---------------------------------------------------------------------------

class TestInitialize:
    @pytest.mark.asyncio
    async def test_loads_all_entries_from_db(self):
        entries = [
            _make_entry("sys.safety", PromptCategory.SYSTEM_BASE),
            _make_entry("p.persona", PromptCategory.IDENTITY),
        ]
        db = _make_db(entries)
        mgr = PromptManager(db)
        await mgr.initialize()

        assert mgr.get_entry("sys.safety") is not None
        assert mgr.get_entry("p.persona") is not None
        db.get_prompt_entries.assert_called_once_with(active_only=False)

    @pytest.mark.asyncio
    async def test_empty_db_gives_empty_cache(self):
        db = _make_db([])
        mgr = PromptManager(db)
        await mgr.initialize()
        assert mgr.all_entries == {}


# ---------------------------------------------------------------------------
# register_prompt()
# ---------------------------------------------------------------------------

class TestRegisterPrompt:
    @pytest.mark.asyncio
    async def test_valid_category_writes_to_cache_and_db(self):
        db = _make_db()
        mgr = PromptManager(db)

        entry = await mgr.register_prompt(
            "sys.safety", "Safety", PromptCategory.SYSTEM_BASE,
            priority=100, content="be safe",
        )

        assert entry.prompt_id == "sys.safety"
        assert mgr.get_entry("sys.safety") is entry
        db.upsert_prompt_entry.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_invalid_category_raises_value_error(self):
        db = _make_db()
        mgr = PromptManager(db)

        with pytest.raises(ValueError, match="Invalid category"):
            await mgr.register_prompt("x", "X", "NotAStage")

    @pytest.mark.asyncio
    async def test_overwrites_existing_cache_entry(self):
        old = _make_entry("sys.safety", content="old content")
        db = _make_db([old])
        mgr = PromptManager(db)
        await mgr.initialize()

        db.upsert_prompt_entry = AsyncMock(
            return_value=_make_entry("sys.safety", content="new content")
        )
        await mgr.register_prompt("sys.safety", "S", PromptCategory.SYSTEM_BASE, content="new content")

        assert mgr.get_entry("sys.safety").content == "new content"

    @pytest.mark.asyncio
    async def test_all_valid_categories_accepted(self):
        db = _make_db()
        mgr = PromptManager(db)

        for i, cat in enumerate(PromptCategory.ALL):
            await mgr.register_prompt(f"p.{i}", f"P{i}", cat)

        assert len(mgr.all_entries) == len(PromptCategory.ALL)


# ---------------------------------------------------------------------------
# unregister_prompt()
# ---------------------------------------------------------------------------

class TestUnregisterPrompt:
    @pytest.mark.asyncio
    async def test_removes_from_cache_and_db(self):
        entry = _make_entry("sys.safety")
        db = _make_db([entry])
        mgr = PromptManager(db)
        await mgr.initialize()

        await mgr.unregister_prompt("sys.safety")

        assert mgr.get_entry("sys.safety") is None
        db.delete_prompt_entry.assert_awaited_once_with("sys.safety")

    @pytest.mark.asyncio
    async def test_unregister_also_removes_functional_provider(self):
        entry = _make_entry("fn.x", type="functional")
        db = _make_db([entry])
        mgr = PromptManager(db)
        await mgr.initialize()
        mgr.register_functional_provider("fn.x", AsyncMock(return_value="result"))

        await mgr.unregister_prompt("fn.x")

        # functional provider removed
        result = await mgr.resolve_functional("fn.x", {})
        assert result is None

    @pytest.mark.asyncio
    async def test_unregister_nonexistent_id_is_silent(self):
        db = _make_db()
        mgr = PromptManager(db)

        # Should not raise
        await mgr.unregister_prompt("does.not.exist")
        db.delete_prompt_entry.assert_awaited_once_with("does.not.exist")


# ---------------------------------------------------------------------------
# get_sorted_prompts()
# ---------------------------------------------------------------------------

class TestGetSortedPrompts:
    @pytest.mark.asyncio
    async def test_sorts_by_stage_order_first(self):
        db = _make_db()
        mgr = PromptManager(db)
        # Register out of natural order
        await mgr.register_prompt("p.constraint", "C", PromptCategory.CONSTRAINT)
        await mgr.register_prompt("p.sys", "S", PromptCategory.SYSTEM_BASE)
        await mgr.register_prompt("p.identity", "I", PromptCategory.IDENTITY)

        sorted_ = mgr.get_sorted_prompts()
        categories = [e.category for e in sorted_]

        assert categories.index(PromptCategory.SYSTEM_BASE) < categories.index(PromptCategory.IDENTITY)
        assert categories.index(PromptCategory.IDENTITY) < categories.index(PromptCategory.CONSTRAINT)

    @pytest.mark.asyncio
    async def test_sorts_by_priority_descending_within_stage(self):
        db = _make_db()
        mgr = PromptManager(db)
        db.upsert_prompt_entry = AsyncMock(side_effect=lambda pid, name, cat, **kw: _make_entry(
            pid, category=cat, priority=kw.get("priority", 50)
        ))

        await mgr.register_prompt("p.lo", "Lo", PromptCategory.IDENTITY, priority=10)
        await mgr.register_prompt("p.hi", "Hi", PromptCategory.IDENTITY, priority=90)
        await mgr.register_prompt("p.mid", "Mid", PromptCategory.IDENTITY, priority=50)

        sorted_ = mgr.get_sorted_prompts()
        identity_entries = [e for e in sorted_ if e.category == PromptCategory.IDENTITY]
        priorities = [e.priority for e in identity_entries]
        assert priorities == sorted(priorities, reverse=True)

    @pytest.mark.asyncio
    async def test_active_only_filters_inactive(self):
        db = _make_db()
        mgr = PromptManager(db)
        active_entry = _make_entry("p.active", is_active=True)
        inactive_entry = _make_entry("p.inactive", is_active=False)
        # Manually populate cache
        mgr._cache["p.active"] = active_entry
        mgr._cache["p.inactive"] = inactive_entry

        active = mgr.get_sorted_prompts(active_only=True)
        all_ = mgr.get_sorted_prompts(active_only=False)

        assert all(e.is_active for e in active)
        assert len(all_) == 2

    @pytest.mark.asyncio
    async def test_filters_by_provided_ids(self):
        db = _make_db()
        mgr = PromptManager(db)
        mgr._cache["p.a"] = _make_entry("p.a")
        mgr._cache["p.b"] = _make_entry("p.b")
        mgr._cache["p.c"] = _make_entry("p.c")

        result = mgr.get_sorted_prompts(prompt_ids=["p.a", "p.c"])
        ids = {e.prompt_id for e in result}
        assert ids == {"p.a", "p.c"}

    @pytest.mark.asyncio
    async def test_missing_ids_silently_skipped(self):
        db = _make_db()
        mgr = PromptManager(db)
        mgr._cache["p.a"] = _make_entry("p.a")

        result = mgr.get_sorted_prompts(prompt_ids=["p.a", "p.does_not_exist"])
        assert len(result) == 1


# ---------------------------------------------------------------------------
# get_entries_by_category()
# ---------------------------------------------------------------------------

class TestGetEntriesByCategory:
    def test_returns_only_matching_category(self):
        mgr = PromptManager(MagicMock())
        mgr._cache["p.sys"] = _make_entry("p.sys", PromptCategory.SYSTEM_BASE)
        mgr._cache["p.id"] = _make_entry("p.id", PromptCategory.IDENTITY)

        result = mgr.get_entries_by_category(PromptCategory.SYSTEM_BASE)
        assert all(e.category == PromptCategory.SYSTEM_BASE for e in result)
        assert len(result) == 1

    def test_active_only_true_excludes_inactive(self):
        mgr = PromptManager(MagicMock())
        mgr._cache["p.on"] = _make_entry("p.on", PromptCategory.IDENTITY, is_active=True)
        mgr._cache["p.off"] = _make_entry("p.off", PromptCategory.IDENTITY, is_active=False)

        active = mgr.get_entries_by_category(PromptCategory.IDENTITY, active_only=True)
        assert len(active) == 1
        assert active[0].prompt_id == "p.on"

    def test_sorted_by_priority_descending(self):
        mgr = PromptManager(MagicMock())
        mgr._cache["p.lo"] = _make_entry("p.lo", PromptCategory.INSTRUCTION, priority=10)
        mgr._cache["p.hi"] = _make_entry("p.hi", PromptCategory.INSTRUCTION, priority=80)

        result = mgr.get_entries_by_category(PromptCategory.INSTRUCTION)
        assert result[0].priority >= result[1].priority


# ---------------------------------------------------------------------------
# Functional provider
# ---------------------------------------------------------------------------

class TestFunctionalProvider:
    def test_register_and_resolve_invokes_callback(self):
        mgr = PromptManager(MagicMock())

        async def my_provider(ctx: dict) -> str:
            return f"dynamic:{ctx.get('key', 'none')}"

        mgr.register_functional_provider("fn.test", my_provider)
        # Provider is registered — tested via resolve_functional below

    @pytest.mark.asyncio
    async def test_resolve_functional_calls_provider_with_context(self):
        mgr = PromptManager(MagicMock())
        called_with: list[dict] = []

        async def provider(ctx: dict) -> str:
            called_with.append(ctx)
            return "result"

        mgr.register_functional_provider("fn.x", provider)
        result = await mgr.resolve_functional("fn.x", {"k": "v"})

        assert result == "result"
        assert called_with[0] == {"k": "v"}

    @pytest.mark.asyncio
    async def test_resolve_functional_missing_returns_none(self):
        mgr = PromptManager(MagicMock())
        result = await mgr.resolve_functional("fn.ghost")
        assert result is None

    @pytest.mark.asyncio
    async def test_resolve_functional_exception_returns_none(self):
        mgr = PromptManager(MagicMock())

        async def bad_provider(ctx: dict) -> str:
            raise RuntimeError("boom")

        mgr.register_functional_provider("fn.bad", bad_provider)
        result = await mgr.resolve_functional("fn.bad", {})
        assert result is None

    @pytest.mark.asyncio
    async def test_resolve_functional_empty_context_gets_empty_dict(self):
        mgr = PromptManager(MagicMock())
        received: list = []

        async def provider(ctx: dict) -> str:
            received.append(ctx)
            return "ok"

        mgr.register_functional_provider("fn.ctx", provider)
        await mgr.resolve_functional("fn.ctx")  # no context passed
        assert received[0] == {}
