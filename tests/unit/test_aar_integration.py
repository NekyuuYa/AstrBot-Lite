"""Tests for astrbot.core.aar.integration module."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from astrbot.core.aar.agent_manager import AgentManager
from astrbot.core.aar.context_policy import ContextPolicyRegistry
from astrbot.core.aar.integration import (
    apply_aar_assembly,
    migrate_personas_to_registry,
    seed_system_prompts,
)
from astrbot.core.aar.orchestrator import AssemblyContext
from astrbot.core.aar.prompt_manager import PromptManager
from astrbot.core.db.po import AgentConfig, PromptCategory, PromptEntry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_prompt_mgr() -> PromptManager:
    db = MagicMock()
    db.get_prompt_entries = AsyncMock(return_value=[])
    db.upsert_prompt_entry = AsyncMock(
        side_effect=lambda pid, name, cat, **kw: PromptEntry(
            prompt_id=pid,
            name=name,
            category=cat,
            priority=kw.get("priority", 50),
            type=kw.get("type", "static"),
            content=kw.get("content", ""),
            source=kw.get("source", "system"),
            is_active=kw.get("is_active", True),
        )
    )
    db.delete_prompt_entry = AsyncMock()
    return PromptManager(db)


def _make_agent_mgr(agent_id: str = "sys.default") -> AgentManager:
    mgr = MagicMock(spec=AgentManager)
    agent = AgentConfig(
        agent_id=agent_id,
        name="Default",
        context_policy="sys.batch_eviction",
        prompts=[],
        config={"window_size": 20},
    )
    mgr.resolve_agent.return_value = agent
    return mgr


def _make_persona(persona_id: str, system_prompt: str | None) -> MagicMock:
    p = MagicMock()
    p.persona_id = persona_id
    p.system_prompt = system_prompt
    return p


# ---------------------------------------------------------------------------
# seed_system_prompts()
# ---------------------------------------------------------------------------

class TestSeedSystemPrompts:
    @pytest.mark.asyncio
    async def test_registers_sys_safety(self):
        mgr = _make_prompt_mgr()
        await seed_system_prompts(mgr)
        assert mgr.get_entry("sys.safety") is not None

    @pytest.mark.asyncio
    async def test_sys_safety_is_in_system_base_stage(self):
        mgr = _make_prompt_mgr()
        await seed_system_prompts(mgr)
        entry = mgr.get_entry("sys.safety")
        assert entry.category == PromptCategory.SYSTEM_BASE

    @pytest.mark.asyncio
    async def test_sys_safety_is_active(self):
        mgr = _make_prompt_mgr()
        await seed_system_prompts(mgr)
        assert mgr.get_entry("sys.safety").is_active is True

    @pytest.mark.asyncio
    async def test_registers_sys_output_constraint(self):
        mgr = _make_prompt_mgr()
        await seed_system_prompts(mgr)
        assert mgr.get_entry("sys.output_constraint") is not None

    @pytest.mark.asyncio
    async def test_output_constraint_is_inactive_by_default(self):
        mgr = _make_prompt_mgr()
        await seed_system_prompts(mgr)
        entry = mgr.get_entry("sys.output_constraint")
        assert entry.is_active is False

    @pytest.mark.asyncio
    async def test_output_constraint_is_in_constraint_stage(self):
        mgr = _make_prompt_mgr()
        await seed_system_prompts(mgr)
        entry = mgr.get_entry("sys.output_constraint")
        assert entry.category == PromptCategory.CONSTRAINT

    @pytest.mark.asyncio
    async def test_sys_safety_has_non_empty_content(self):
        mgr = _make_prompt_mgr()
        await seed_system_prompts(mgr)
        entry = mgr.get_entry("sys.safety")
        assert entry.content and len(entry.content) > 0

    @pytest.mark.asyncio
    async def test_safe_to_call_twice(self):
        """Calling seed_system_prompts twice should not raise."""
        mgr = _make_prompt_mgr()
        await seed_system_prompts(mgr)
        await seed_system_prompts(mgr)
        assert mgr.get_entry("sys.safety") is not None


# ---------------------------------------------------------------------------
# migrate_personas_to_registry()
# ---------------------------------------------------------------------------

class TestMigratePersonasToRegistry:
    @pytest.mark.asyncio
    async def test_persona_with_system_prompt_gets_registered(self):
        mgr = _make_prompt_mgr()
        db = MagicMock()
        db.get_personas = AsyncMock(return_value=[
            _make_persona("helpful", "You are helpful."),
        ])

        await migrate_personas_to_registry(mgr, db)

        assert mgr.get_entry("persona.helpful") is not None

    @pytest.mark.asyncio
    async def test_registered_entry_in_identity_stage(self):
        mgr = _make_prompt_mgr()
        db = MagicMock()
        db.get_personas = AsyncMock(return_value=[
            _make_persona("helpful", "You are helpful."),
        ])

        await migrate_personas_to_registry(mgr, db)

        entry = mgr.get_entry("persona.helpful")
        assert entry.category == PromptCategory.IDENTITY

    @pytest.mark.asyncio
    async def test_registered_entry_is_inactive_by_default(self):
        mgr = _make_prompt_mgr()
        db = MagicMock()
        db.get_personas = AsyncMock(return_value=[
            _make_persona("helpful", "You are helpful."),
        ])

        await migrate_personas_to_registry(mgr, db)

        entry = mgr.get_entry("persona.helpful")
        assert entry.is_active is False

    @pytest.mark.asyncio
    async def test_registered_entry_has_correct_content(self):
        mgr = _make_prompt_mgr()
        db = MagicMock()
        db.get_personas = AsyncMock(return_value=[
            _make_persona("helpful", "You are helpful."),
        ])

        await migrate_personas_to_registry(mgr, db)

        entry = mgr.get_entry("persona.helpful")
        assert entry.content == "You are helpful."

    @pytest.mark.asyncio
    async def test_persona_without_system_prompt_skipped(self):
        mgr = _make_prompt_mgr()
        db = MagicMock()
        db.get_personas = AsyncMock(return_value=[
            _make_persona("blank", None),
            _make_persona("empty", ""),
        ])

        await migrate_personas_to_registry(mgr, db)

        assert mgr.get_entry("persona.blank") is None
        assert mgr.get_entry("persona.empty") is None

    @pytest.mark.asyncio
    async def test_idempotent_skips_existing_entries(self):
        mgr = _make_prompt_mgr()
        # Pre-seed an entry for "helpful"
        mgr._cache["persona.helpful"] = PromptEntry(
            prompt_id="persona.helpful",
            name="Persona: helpful",
            category=PromptCategory.IDENTITY,
            priority=80,
            type="static",
            content="Old content",
            source="persona:helpful",
            is_active=False,
        )

        db = MagicMock()
        db.get_personas = AsyncMock(return_value=[
            _make_persona("helpful", "New content"),
        ])

        await migrate_personas_to_registry(mgr, db)

        # Entry must remain unchanged (idempotent)
        assert mgr.get_entry("persona.helpful").content == "Old content"

    @pytest.mark.asyncio
    async def test_multiple_personas_all_migrated(self):
        mgr = _make_prompt_mgr()
        db = MagicMock()
        db.get_personas = AsyncMock(return_value=[
            _make_persona("alice", "Be Alice."),
            _make_persona("bob", "Be Bob."),
            _make_persona("carol", "Be Carol."),
        ])

        await migrate_personas_to_registry(mgr, db)

        assert mgr.get_entry("persona.alice") is not None
        assert mgr.get_entry("persona.bob") is not None
        assert mgr.get_entry("persona.carol") is not None

    @pytest.mark.asyncio
    async def test_empty_persona_list_does_nothing(self):
        mgr = _make_prompt_mgr()
        db = MagicMock()
        db.get_personas = AsyncMock(return_value=[])

        # Should not raise
        await migrate_personas_to_registry(mgr, db)
        assert len(mgr.all_entries) == 0

    @pytest.mark.asyncio
    async def test_register_failure_does_not_abort_remaining(self):
        """If one persona fails to register, others still succeed."""
        mgr = _make_prompt_mgr()
        call_count = 0
        original_register = mgr.register_prompt

        async def sometimes_failing(prompt_id, name, category, **kw):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("DB error")
            return await original_register(prompt_id, name, category, **kw)

        mgr.register_prompt = sometimes_failing

        db = MagicMock()
        db.get_personas = AsyncMock(return_value=[
            _make_persona("fail_persona", "Will fail."),
            _make_persona("ok_persona", "Will succeed."),
        ])

        await migrate_personas_to_registry(mgr, db)

        # Second persona should still be registered
        assert mgr.get_entry("persona.ok_persona") is not None


# ---------------------------------------------------------------------------
# apply_aar_assembly()
# ---------------------------------------------------------------------------

class TestApplyAarAssembly:
    @pytest.mark.asyncio
    async def test_returns_assembly_context(self):
        mgr = _make_prompt_mgr()
        agent_mgr = _make_agent_mgr()
        ctx_policy = ContextPolicyRegistry()

        result = await apply_aar_assembly(mgr, agent_mgr, ctx_policy)

        assert isinstance(result, AssemblyContext)

    @pytest.mark.asyncio
    async def test_delegates_to_orchestrator(self):
        mgr = _make_prompt_mgr()
        agent_mgr = _make_agent_mgr()
        ctx_policy = ContextPolicyRegistry()
        msgs = [{"role": "user", "content": "hi"}]

        result = await apply_aar_assembly(
            mgr, agent_mgr, ctx_policy,
            raw_messages=msgs,
        )

        assert result.raw_messages == msgs

    @pytest.mark.asyncio
    async def test_extra_context_forwarded(self):
        """Extra context should be accessible to functional providers."""
        mgr = _make_prompt_mgr()
        # Register a functional entry
        entry = PromptEntry(
            prompt_id="fn.test",
            name="Test",
            category=PromptCategory.INSTRUCTION,
            priority=50,
            type="functional",
            content=None,
            source="test",
            is_active=True,
        )
        mgr._cache["fn.test"] = entry

        received = []

        async def provider(ctx: dict) -> str:
            received.append(ctx)
            return "fn_result"

        mgr.register_functional_provider("fn.test", provider)

        agent = AgentConfig(
            agent_id="sys.default",
            name="Default",
            context_policy="sys.batch_eviction",
            prompts=["fn.test"],
            config={"window_size": 20},
        )
        agent_mgr = MagicMock(spec=AgentManager)
        agent_mgr.resolve_agent.return_value = agent

        ctx_policy = ContextPolicyRegistry()
        result = await apply_aar_assembly(
            mgr, agent_mgr, ctx_policy,
            extra_context={"special_key": "special_value"},
        )

        assert "fn_result" in result.final_system_prompt
        assert received[0].get("special_key") == "special_value"

    @pytest.mark.asyncio
    async def test_absent_agent_id_uses_default(self):
        mgr = _make_prompt_mgr()
        agent_mgr = _make_agent_mgr("sys.default")
        ctx_policy = ContextPolicyRegistry()

        result = await apply_aar_assembly(mgr, agent_mgr, ctx_policy, agent_id=None)
        assert result.agent.agent_id == "sys.default"
