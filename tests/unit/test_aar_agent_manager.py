"""Tests for astrbot.core.aar.agent_manager.AgentManager."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from astrbot.core.aar.agent_manager import DEFAULT_AGENT_ID, AgentManager
from astrbot.core.db.po import AgentConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_agent(
    agent_id: str = DEFAULT_AGENT_ID,
    name: str = "Default Agent",
    context_policy: str = "sys.batch_eviction",
    persona_id: str | None = None,
    prompts: list | None = None,
    tools: list | None = None,
    tags: list | None = None,
) -> AgentConfig:
    return AgentConfig(
        agent_id=agent_id,
        name=name,
        context_policy=context_policy,
        persona_id=persona_id,
        prompts=prompts,
        tools=tools,
        tags=tags,
    )


def _make_db(agents: list[AgentConfig] | None = None) -> MagicMock:
    db = MagicMock()
    db.get_agents = AsyncMock(return_value=agents or [])
    db.upsert_agent = AsyncMock(side_effect=lambda agent_id, name, **kw: _make_agent(
        agent_id=agent_id,
        name=name,
        context_policy=kw.get("context_policy", "sys.batch_eviction"),
        persona_id=kw.get("persona_id"),
        prompts=kw.get("prompts"),
        tools=kw.get("tools"),
        tags=kw.get("tags"),
    ))
    db.delete_agent = AsyncMock()
    return db


# ---------------------------------------------------------------------------
# initialize()
# ---------------------------------------------------------------------------

class TestInitialize:
    @pytest.mark.asyncio
    async def test_loads_existing_agents_from_db(self):
        existing = _make_agent("my.agent", name="My Agent")
        db = _make_db([
            _make_agent(DEFAULT_AGENT_ID),  # default already present
            existing,
        ])
        mgr = AgentManager(db)
        await mgr.initialize()

        assert mgr.get_agent("my.agent") is not None
        assert mgr.get_agent(DEFAULT_AGENT_ID) is not None

    @pytest.mark.asyncio
    async def test_creates_default_agent_when_missing(self):
        db = _make_db([])  # no agents in DB
        mgr = AgentManager(db)
        await mgr.initialize()

        assert mgr.get_agent(DEFAULT_AGENT_ID) is not None
        db.upsert_agent.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_does_not_recreate_default_agent_when_present(self):
        db = _make_db([_make_agent(DEFAULT_AGENT_ID)])
        mgr = AgentManager(db)
        await mgr.initialize()

        # upsert_agent should NOT have been called (default already exists)
        db.upsert_agent.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_cache_populated_correctly(self):
        agents = [
            _make_agent(DEFAULT_AGENT_ID),
            _make_agent("a.second", name="Second"),
        ]
        db = _make_db(agents)
        mgr = AgentManager(db)
        await mgr.initialize()

        all_ = mgr.get_agents()
        assert len(all_) == 2


# ---------------------------------------------------------------------------
# upsert_agent()
# ---------------------------------------------------------------------------

class TestUpsertAgent:
    @pytest.mark.asyncio
    async def test_adds_new_agent_to_cache(self):
        db = _make_db([_make_agent(DEFAULT_AGENT_ID)])
        mgr = AgentManager(db)
        await mgr.initialize()

        agent = await mgr.upsert_agent("svc.agent", "Service Agent")

        assert agent.agent_id == "svc.agent"
        assert mgr.get_agent("svc.agent") is agent

    @pytest.mark.asyncio
    async def test_updates_existing_agent_in_cache(self):
        existing = _make_agent("svc.agent", name="Old Name")
        db = _make_db([_make_agent(DEFAULT_AGENT_ID), existing])
        mgr = AgentManager(db)
        await mgr.initialize()

        db.upsert_agent = AsyncMock(return_value=_make_agent("svc.agent", name="New Name"))
        updated = await mgr.upsert_agent("svc.agent", "New Name")

        assert mgr.get_agent("svc.agent").name == "New Name"
        assert updated.name == "New Name"

    @pytest.mark.asyncio
    async def test_persists_optional_fields(self):
        db = _make_db([_make_agent(DEFAULT_AGENT_ID)])
        mgr = AgentManager(db)
        await mgr.initialize()

        await mgr.upsert_agent(
            "rich.agent",
            "Rich",
            persona_id="my.persona",
            tools=["tool_a"],
            tags=["prod"],
        )

        db.upsert_agent.assert_awaited_with(
            "rich.agent",
            "Rich",
            persona_id="my.persona",
            prompts=None,
            tools=["tool_a"],
            skills=None,
            context_policy="sys.batch_eviction",
            interceptors=None,
            config=None,
            tags=["prod"],
        )


# ---------------------------------------------------------------------------
# delete_agent()
# ---------------------------------------------------------------------------

class TestDeleteAgent:
    @pytest.mark.asyncio
    async def test_delete_removes_from_cache(self):
        target = _make_agent("bye.agent", name="Bye")
        db = _make_db([_make_agent(DEFAULT_AGENT_ID), target])
        mgr = AgentManager(db)
        await mgr.initialize()

        await mgr.delete_agent("bye.agent")

        assert mgr.get_agent("bye.agent") is None
        db.delete_agent.assert_awaited_once_with("bye.agent")

    @pytest.mark.asyncio
    async def test_delete_default_agent_raises(self):
        db = _make_db([_make_agent(DEFAULT_AGENT_ID)])
        mgr = AgentManager(db)
        await mgr.initialize()

        with pytest.raises(ValueError, match="Cannot delete the system default agent"):
            await mgr.delete_agent(DEFAULT_AGENT_ID)

        db.delete_agent.assert_not_awaited()


# ---------------------------------------------------------------------------
# get_agents() with tag filter
# ---------------------------------------------------------------------------

class TestGetAgents:
    @pytest.mark.asyncio
    async def test_get_all_without_filter(self):
        agents = [
            _make_agent(DEFAULT_AGENT_ID),
            _make_agent("a.prod", tags=["prod"]),
            _make_agent("a.dev", tags=["dev"]),
        ]
        db = _make_db(agents)
        mgr = AgentManager(db)
        await mgr.initialize()

        all_ = mgr.get_agents()
        assert len(all_) == 3

    @pytest.mark.asyncio
    async def test_get_filtered_by_tag(self):
        agents = [
            _make_agent(DEFAULT_AGENT_ID),
            _make_agent("a.prod", tags=["prod"]),
            _make_agent("a.dev", tags=["dev"]),
        ]
        db = _make_db(agents)
        mgr = AgentManager(db)
        await mgr.initialize()

        prod = mgr.get_agents(tag="prod")
        assert len(prod) == 1
        assert prod[0].agent_id == "a.prod"

    @pytest.mark.asyncio
    async def test_get_tag_no_match_returns_empty(self):
        db = _make_db([_make_agent(DEFAULT_AGENT_ID)])
        mgr = AgentManager(db)
        await mgr.initialize()

        assert mgr.get_agents(tag="nonexistent") == []


# ---------------------------------------------------------------------------
# resolve_agent()
# ---------------------------------------------------------------------------

class TestResolveAgent:
    @pytest.mark.asyncio
    async def test_resolve_existing_id_returns_that_agent(self):
        target = _make_agent("svc.agent", name="Svc")
        db = _make_db([_make_agent(DEFAULT_AGENT_ID), target])
        mgr = AgentManager(db)
        await mgr.initialize()

        resolved = mgr.resolve_agent("svc.agent")
        assert resolved.agent_id == "svc.agent"

    @pytest.mark.asyncio
    async def test_resolve_missing_id_falls_back_to_default(self):
        db = _make_db([_make_agent(DEFAULT_AGENT_ID)])
        mgr = AgentManager(db)
        await mgr.initialize()

        resolved = mgr.resolve_agent("ghost.agent")
        assert resolved.agent_id == DEFAULT_AGENT_ID

    @pytest.mark.asyncio
    async def test_resolve_none_returns_default(self):
        db = _make_db([_make_agent(DEFAULT_AGENT_ID)])
        mgr = AgentManager(db)
        await mgr.initialize()

        resolved = mgr.resolve_agent(None)
        assert resolved.agent_id == DEFAULT_AGENT_ID

    @pytest.mark.asyncio
    async def test_default_agent_property(self):
        db = _make_db([_make_agent(DEFAULT_AGENT_ID, name="The Default")])
        mgr = AgentManager(db)
        await mgr.initialize()

        assert mgr.default_agent.agent_id == DEFAULT_AGENT_ID
