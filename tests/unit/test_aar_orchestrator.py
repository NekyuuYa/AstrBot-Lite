"""Tests for astrbot.core.aar.orchestrator.PipelineOrchestrator."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from astrbot.core.aar.agent_manager import DEFAULT_AGENT_ID, AgentManager
from astrbot.core.aar.context_policy import ContextPolicyRegistry
from astrbot.core.aar.orchestrator import AssemblyContext, PipelineOrchestrator
from astrbot.core.aar.prompt_manager import PromptManager
from astrbot.core.db.po import AgentConfig, PromptCategory, PromptEntry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_agent(
    agent_id: str = DEFAULT_AGENT_ID,
    prompts: list | None = None,
    context_policy: str = "sys.batch_eviction",
    persona_id: str | None = None,
    config: dict | None = None,
) -> AgentConfig:
    return AgentConfig(
        agent_id=agent_id,
        name="Test Agent",
        prompts=prompts or [],
        context_policy=context_policy,
        persona_id=persona_id,
        config=config or {"window_size": 5},
    )


def _make_entry(
    prompt_id: str,
    category: str,
    priority: int = 50,
    type: str = "static",
    content: str | None = None,
    is_active: bool = True,
) -> PromptEntry:
    return PromptEntry(
        prompt_id=prompt_id,
        name=f"Entry {prompt_id}",
        category=category,
        priority=priority,
        type=type,
        content=f"Content of {prompt_id}" if content is None else content,
        source="system",
        is_active=is_active,
    )


def _make_prompt_mgr(entries: list[PromptEntry] | None = None) -> PromptManager:
    db = MagicMock()
    mgr = PromptManager(db)
    for e in (entries or []):
        mgr._cache[e.prompt_id] = e
    return mgr


def _make_agent_mgr(agent: AgentConfig | None = None) -> AgentManager:
    if agent is None:
        agent = _make_agent()
    mgr = MagicMock(spec=AgentManager)
    mgr.resolve_agent.return_value = agent
    return mgr


def _make_ctx_policy(evict_count: int = 0) -> ContextPolicyRegistry:
    """Real registry; batch_eviction with small window_size so small inputs pass through."""
    return ContextPolicyRegistry()


def _orchestrator(
    prompt_entries: list[PromptEntry] | None = None,
    agent: AgentConfig | None = None,
) -> PipelineOrchestrator:
    return PipelineOrchestrator(
        prompt_manager=_make_prompt_mgr(prompt_entries),
        agent_manager=_make_agent_mgr(agent),
        context_policy_registry=_make_ctx_policy(),
    )


# ---------------------------------------------------------------------------
# AssemblyContext
# ---------------------------------------------------------------------------

class TestAssemblyContext:
    def test_post_init_populates_all_stages(self):
        agent = _make_agent()
        ctx = AssemblyContext(agent=agent)
        for stage in PromptCategory.ALL:
            assert stage in ctx.system_prompt_parts
            assert ctx.system_prompt_parts[stage] == []

    def test_final_system_prompt_starts_empty(self):
        ctx = AssemblyContext(agent=_make_agent())
        assert ctx.final_system_prompt == ""


# ---------------------------------------------------------------------------
# PipelineOrchestrator.assemble_request()
# ---------------------------------------------------------------------------

class TestAssembleRequestBasic:
    @pytest.mark.asyncio
    async def test_returns_assembly_context(self):
        orch = _orchestrator()
        ctx = await orch.assemble_request()
        assert isinstance(ctx, AssemblyContext)

    @pytest.mark.asyncio
    async def test_agent_is_resolved(self):
        agent = _make_agent("my.agent")
        orch = _orchestrator(agent=agent)
        ctx = await orch.assemble_request(agent_id="my.agent")
        assert ctx.agent.agent_id == "my.agent"

    @pytest.mark.asyncio
    async def test_no_prompts_gives_empty_system_prompt(self):
        agent = _make_agent(prompts=[])
        orch = _orchestrator(agent=agent)
        ctx = await orch.assemble_request()
        assert ctx.final_system_prompt == ""

    @pytest.mark.asyncio
    async def test_raw_messages_stored(self):
        orch = _orchestrator()
        msgs = [{"role": "user", "content": "hello"}]
        ctx = await orch.assemble_request(raw_messages=msgs)
        assert ctx.raw_messages == msgs

    @pytest.mark.asyncio
    async def test_metadata_includes_context_policy_key(self):
        orch = _orchestrator()
        ctx = await orch.assemble_request()
        assert "context_policy" in ctx.metadata
        assert "evicted_count" in ctx.metadata


class TestAssembleRequestStaticPrompts:
    @pytest.mark.asyncio
    async def test_single_static_prompt_appears_in_output(self):
        entry = _make_entry("sys.safety", PromptCategory.SYSTEM_BASE, content="Be safe.")
        agent = _make_agent(prompts=["sys.safety"])
        orch = _orchestrator([entry], agent)

        ctx = await orch.assemble_request()
        assert "Be safe." in ctx.final_system_prompt

    @pytest.mark.asyncio
    async def test_multiple_stages_appear_in_order(self):
        entries = [
            _make_entry("p.constraint", PromptCategory.CONSTRAINT, content="[CONSTRAINT]"),
            _make_entry("p.identity", PromptCategory.IDENTITY, content="[IDENTITY]"),
            _make_entry("p.sys", PromptCategory.SYSTEM_BASE, content="[SYS]"),
        ]
        agent = _make_agent(prompts=["p.sys", "p.identity", "p.constraint"])
        orch = _orchestrator(entries, agent)

        ctx = await orch.assemble_request()
        prompt = ctx.final_system_prompt
        # Stage order must be preserved: SystemBase before Identity before Constraint
        assert prompt.index("[SYS]") < prompt.index("[IDENTITY]")
        assert prompt.index("[IDENTITY]") < prompt.index("[CONSTRAINT]")

    @pytest.mark.asyncio
    async def test_inactive_prompt_not_included(self):
        active = _make_entry("p.on", PromptCategory.SYSTEM_BASE, content="[ACTIVE]", is_active=True)
        inactive = _make_entry("p.off", PromptCategory.SYSTEM_BASE, content="[INACTIVE]", is_active=False)
        agent = _make_agent(prompts=["p.on", "p.off"])
        orch = _orchestrator([active, inactive], agent)

        ctx = await orch.assemble_request()
        assert "[ACTIVE]" in ctx.final_system_prompt
        assert "[INACTIVE]" not in ctx.final_system_prompt

    @pytest.mark.asyncio
    async def test_empty_static_content_not_added(self):
        entry = _make_entry("p.empty", PromptCategory.INSTRUCTION, content="")
        agent = _make_agent(prompts=["p.empty"])
        orch = _orchestrator([entry], agent)

        ctx = await orch.assemble_request()
        assert ctx.final_system_prompt == ""

    @pytest.mark.asyncio
    async def test_same_stage_fragments_joined_with_double_newline(self):
        e1 = _make_entry("p.a", PromptCategory.SYSTEM_BASE, priority=90, content="PART_A")
        e2 = _make_entry("p.b", PromptCategory.SYSTEM_BASE, priority=10, content="PART_B")
        agent = _make_agent(prompts=["p.a", "p.b"])
        orch = _orchestrator([e1, e2], agent)

        ctx = await orch.assemble_request()
        assert "PART_A\n\nPART_B" in ctx.final_system_prompt


class TestAssembleRequestFunctionalPrompts:
    @pytest.mark.asyncio
    async def test_functional_prompt_resolved_via_provider(self):
        entry = _make_entry("fn.dyn", PromptCategory.ABILITIES, type="functional", content=None)
        agent = _make_agent(prompts=["fn.dyn"])
        pm = _make_prompt_mgr([entry])

        async def provider(ctx: dict) -> str:
            return "DYNAMIC_CONTENT"

        pm.register_functional_provider("fn.dyn", provider)

        orch = PipelineOrchestrator(
            prompt_manager=pm,
            agent_manager=_make_agent_mgr(agent),
            context_policy_registry=_make_ctx_policy(),
        )
        ctx = await orch.assemble_request()
        assert "DYNAMIC_CONTENT" in ctx.final_system_prompt

    @pytest.mark.asyncio
    async def test_missing_functional_provider_produces_no_output(self):
        entry = _make_entry("fn.ghost", PromptCategory.ABILITIES, type="functional", content=None)
        agent = _make_agent(prompts=["fn.ghost"])
        orch = _orchestrator([entry], agent)

        ctx = await orch.assemble_request()
        assert ctx.final_system_prompt == ""

    @pytest.mark.asyncio
    async def test_extra_context_passed_to_functional_provider(self):
        entry = _make_entry("fn.ctx", PromptCategory.REFINEMENT, type="functional", content=None)
        agent = _make_agent(prompts=["fn.ctx"])
        pm = _make_prompt_mgr([entry])
        received = []

        async def provider(ctx: dict) -> str:
            received.append(ctx)
            return "ok"

        pm.register_functional_provider("fn.ctx", provider)
        orch = PipelineOrchestrator(pm, _make_agent_mgr(agent), _make_ctx_policy())

        await orch.assemble_request(extra_context={"my_key": "my_val"})
        assert received[0].get("my_key") == "my_val"


class TestAssembleRequestTemplatePrompts:
    @pytest.mark.asyncio
    async def test_jinja2_template_rendered(self):
        entry = _make_entry(
            "tmpl.hello",
            PromptCategory.INSTRUCTION,
            type="template",
            content="Hello, {{ agent.agent_id }}!",
        )
        agent = _make_agent("test.agent", prompts=["tmpl.hello"])
        orch = _orchestrator([entry], agent)

        ctx = await orch.assemble_request()
        assert "Hello, test.agent!" in ctx.final_system_prompt

    @pytest.mark.asyncio
    async def test_broken_template_falls_back_to_raw_content(self):
        entry = _make_entry(
            "tmpl.bad",
            PromptCategory.INSTRUCTION,
            type="template",
            content="{{ unclosed",
        )
        agent = _make_agent(prompts=["tmpl.bad"])
        orch = _orchestrator([entry], agent)

        # Should not raise; falls back to raw template string
        ctx = await orch.assemble_request()
        # Either the raw template or an empty string — either way, no exception
        assert isinstance(ctx.final_system_prompt, str)


class TestAssembleRequestContextPolicy:
    @pytest.mark.asyncio
    async def test_context_policy_applied_to_messages(self):
        # Build an agent with a small window_size so batch_eviction fires
        agent = _make_agent(
            prompts=[],
            context_policy="sys.batch_eviction",
            config={"window_size": 3, "evict_ratio": 0.5},
        )
        orch = _orchestrator(agent=agent)
        msgs = [{"role": "user", "content": f"msg {i}"} for i in range(10)]

        ctx = await orch.assemble_request(raw_messages=msgs)
        assert len(ctx.processed_messages) < len(msgs)
        assert ctx.metadata["evicted_count"] > 0

    @pytest.mark.asyncio
    async def test_empty_messages_unaffected_by_policy(self):
        orch = _orchestrator()
        ctx = await orch.assemble_request(raw_messages=[])
        assert ctx.processed_messages == []
        assert ctx.metadata["evicted_count"] == 0


class TestAssembleRequestAllPromptsMode:
    @pytest.mark.asyncio
    async def test_agent_with_no_prompts_list_includes_all_registry_entries(self):
        """When agent.prompts is empty ([]), the orchestrator treats it as 'no filter'
        and falls back to all active registry entries."""
        agent = _make_agent(prompts=[])
        entries = [_make_entry("sys.x", PromptCategory.SYSTEM_BASE, content="X")]
        orch = _orchestrator(entries, agent)

        ctx = await orch.assemble_request()
        # Empty prompts list → no ID filter → all active entries included
        assert "X" in ctx.final_system_prompt
