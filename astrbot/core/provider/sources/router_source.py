"""LiteLLM Model Router Provider.

A virtual provider that groups multiple LiteLLM-backed providers into a single
high-availability unit with automatic fallback, load balancing, and smart
per-model cooldown policies:

    - 429 RateLimitError      → short cooldown (5 min)   managed by litellm.Router
    - 403 usage-limit         → long  cooldown (24 hr)   managed by _long_cooldowns

Routers are loaded *after* all ordinary providers so that their dependencies
(the member provider instances) are guaranteed to exist in inst_map.
"""

from __future__ import annotations

import json
import time
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING, Literal

import litellm
from litellm import Router

import astrbot.core.message.components as Comp
from astrbot import logger
from astrbot.api.provider import Provider
from astrbot.core.agent.message import ContentPart, Message
from astrbot.core.agent.tool import ToolSet
from astrbot.core.exceptions import EmptyModelOutputError
from astrbot.core.message.message_event_result import MessageChain
from astrbot.core.provider.entities import LLMResponse, TokenUsage, ToolCallsResult

from ..register import register_provider_adapter
from .litellm_source import ProviderLiteLLM

if TYPE_CHECKING:
    from astrbot.core.provider.manager import ProviderManager


@register_provider_adapter(
    "model_router",
    "模型路由器：将多个 LiteLLM 提供商组合为单一高可用虚拟提供商，支持自动故障转移、负载均衡和智能冷却策略",
    default_config_tmpl={
        "id": "my-router",
        "type": "model_router",
        "enable": True,
        "model_list": [],
        "routing_strategy": "simple-shuffle",
    },
)
class ProviderRouter(ProviderLiteLLM):
    """LiteLLM Router-backed virtual provider.

    Inherits from ``ProviderLiteLLM`` to reuse message building and response
    parsing helpers.  The heavy ``ProviderLiteLLM.__init__`` is intentionally
    skipped — only the base ``Provider.__init__`` is called.
    """

    def __init__(self, provider_config: dict, provider_settings: dict) -> None:
        # Skip ProviderLiteLLM.__init__ — we manage our own set of models.
        Provider.__init__(self, provider_config, provider_settings)

        self.router_id: str = provider_config.get("id", "router")
        self.model_list_ids: list[str] = provider_config.get("model_list", [])
        self.routing_strategy: str = provider_config.get(
            "routing_strategy", "simple-shuffle"
        )

        self.router: Router | None = None
        self._initialized: bool = False

        # Injected by ProviderManager after instantiation (see set_manager()).
        self._manager: ProviderManager | None = None

        # Long-term cooldowns: provider_id → unix expiry timestamp.
        # Survives router rebuilds so 403-blocked models stay off for 24 h.
        self._long_cooldowns: dict[str, float] = {}

        # Populated by _build_router(); used to map litellm model string → provider_id.
        self._resolved_model_list: list[dict] = []
        self._model_to_provider_id: dict[str, str] = {}

    # ------------------------------------------------------------------ #
    # Manager injection                                                    #
    # ------------------------------------------------------------------ #

    def set_manager(self, manager: ProviderManager) -> None:
        """Called by ProviderManager immediately after instantiation."""
        self._manager = manager

    # ------------------------------------------------------------------ #
    # Initialisation & router construction                                 #
    # ------------------------------------------------------------------ #

    async def initialize(self) -> None:
        """Late initialisation — all member providers must already be loaded."""
        if self._initialized:
            return
        await self._build_router()
        self._initialized = True

    async def _build_router(self) -> None:
        if self._manager is None:
            raise RuntimeError(
                f"Router [{self.router_id}]: ProviderManager not injected. "
                "Ensure set_manager() is called before initialize()."
            )

        now = time.time()
        self._resolved_model_list = []
        self._model_to_provider_id = {}

        for provider_id in self.model_list_ids:
            inst = self._manager.inst_map.get(provider_id)
            if not isinstance(inst, ProviderLiteLLM):
                logger.warning(
                    f"Router [{self.router_id}]: member provider {provider_id!r} "
                    "not found or is not a LiteLLM-compatible provider — skipping."
                )
                continue

            litellm_params: dict = {
                "model": inst.model_name,
                # Keep a stable unique key per deployment for cooldown tracking.
                "model_id": provider_id,
            }
            if inst.api_key:
                litellm_params["api_key"] = inst.api_key
            if inst.api_base:
                litellm_params["api_base"] = inst.api_base
            if inst.user_extra_params:
                litellm_params.update(inst.user_extra_params)

            self._resolved_model_list.append(
                {
                    # All deployments share the same model_name (the router id)
                    # so that router.acompletion(model=router_id) picks among them.
                    "model_name": self.router_id,
                    "litellm_params": litellm_params,
                }
            )
            self._model_to_provider_id[inst.model_name] = provider_id

        if not self._resolved_model_list:
            logger.warning(f"Router [{self.router_id}]: no valid member providers resolved.")
            return

        # Exclude 403-cooled deployments; fall back to all if everything is cooled.
        active = [
            m
            for m in self._resolved_model_list
            if now >= self._long_cooldowns.get(m["litellm_params"]["model_id"], 0)
        ]
        if not active:
            logger.warning(
                f"Router [{self.router_id}]: all models are on long-term cooldown; "
                "using all to avoid complete outage."
            )
            active = self._resolved_model_list

        self.router = Router(
            model_list=active,
            routing_strategy=self.routing_strategy,
            # Let the Router exhaust every active deployment before giving up.
            num_retries=len(active),
            # After 1 failure, put a deployment on 5-minute (429) cooldown.
            allowed_fails=1,
            cooldown_time=300,
            set_verbose=False,
        )
        logger.info(
            f"Router [{self.router_id}]: ready with "
            f"{len(active)}/{len(self._resolved_model_list)} models "
            f"(strategy={self.routing_strategy})."
        )

    async def _rebuild_router(self) -> None:
        """Discard and recreate the litellm.Router (e.g. after a 403 cooldown)."""
        self._initialized = False
        self.router = None
        await self._build_router()
        self._initialized = True

    # ------------------------------------------------------------------ #
    # Error helpers                                                        #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _is_403_usage_limit(exc: Exception) -> bool:
        msg = str(exc).lower()
        return "403" in str(exc) and any(
            kw in msg for kw in ("usage", "limit", "quota", "exhausted", "exceeded")
        )

    def _handle_403_usage_limit(self, exc: Exception) -> bool:
        """Apply a 24-hour cooldown to the identified failing provider.

        Returns True if a provider was successfully identified and cooled down.
        """
        failed_litellm_model: str | None = getattr(exc, "model", None)
        provider_id: str | None = (
            self._model_to_provider_id.get(failed_litellm_model)
            if failed_litellm_model
            else None
        )
        if provider_id:
            expiry = time.time() + 86400  # 24 hours
            self._long_cooldowns[provider_id] = expiry
            logger.warning(
                f"Router [{self.router_id}]: 403 usage-limit on [{provider_id}] "
                f"(model={failed_litellm_model}); setting 24-hour cooldown."
            )
            return True
        return False

    # ------------------------------------------------------------------ #
    # Provider interface — identity / model list                          #
    # ------------------------------------------------------------------ #

    def get_current_key(self) -> str:
        return ""

    def set_key(self, key: str) -> None:
        pass

    async def get_models(self) -> list[str]:
        return [self.router_id]

    # ------------------------------------------------------------------ #
    # text_chat                                                            #
    # ------------------------------------------------------------------ #

    async def text_chat(
        self,
        prompt: str | None = None,
        session_id: str | None = None,
        image_urls: list[str] | None = None,
        func_tool: ToolSet | None = None,
        contexts: list[Message] | list[dict] | None = None,
        system_prompt: str | None = None,
        tool_calls_result: ToolCallsResult | list[ToolCallsResult] | None = None,
        model: str | None = None,
        extra_user_content_parts: list[ContentPart] | None = None,
        tool_choice: Literal["auto", "required"] = "auto",
        **kwargs,
    ) -> LLMResponse:
        if not self._initialized or not self.router:
            await self.initialize()
        if not self.router:
            raise RuntimeError(
                f"Router [{self.router_id}]: no valid providers available."
            )

        messages = await self._build_messages(
            prompt,
            image_urls,
            contexts,
            system_prompt,
            tool_calls_result,
            extra_user_content_parts,
        )
        call_kwargs: dict = {
            "model": self.router_id,
            "messages": messages,
        }
        if func_tool and not func_tool.empty():
            call_kwargs["tools"] = func_tool.get_func_desc_openai_style()
            call_kwargs["tool_choice"] = tool_choice

        # At most one outer retry per resolved provider (plus one extra pass).
        max_attempts = len(self._resolved_model_list) + 1
        last_exc: Exception | None = None

        for attempt in range(max_attempts):
            try:
                completion = await self.router.acompletion(**call_kwargs)
                return self._parse_response(completion, func_tool)
            except Exception as exc:
                last_exc = exc
                if self._is_403_usage_limit(exc):
                    if self._handle_403_usage_limit(exc):
                        await self._rebuild_router()
                        if not self.router:
                            break
                        continue
                # Any other error (including unidentified 403): propagate.
                logger.error(
                    f"Router [{self.router_id}] text_chat failed "
                    f"(attempt {attempt + 1}/{max_attempts}): {exc}"
                )
                raise

        if last_exc is not None:
            raise last_exc
        raise RuntimeError(f"Router [{self.router_id}]: all providers exhausted.")

    # ------------------------------------------------------------------ #
    # text_chat_stream                                                     #
    # ------------------------------------------------------------------ #

    async def text_chat_stream(
        self,
        prompt: str | None = None,
        session_id: str | None = None,
        image_urls: list[str] | None = None,
        func_tool: ToolSet | None = None,
        contexts: list[Message] | list[dict] | None = None,
        system_prompt: str | None = None,
        tool_calls_result: ToolCallsResult | list[ToolCallsResult] | None = None,
        model: str | None = None,
        tool_choice: Literal["auto", "required"] = "auto",
        **kwargs,
    ) -> AsyncGenerator[LLMResponse, None]:
        if not self._initialized or not self.router:
            await self.initialize()
        if not self.router:
            raise RuntimeError(
                f"Router [{self.router_id}]: no valid providers available."
            )

        messages = await self._build_messages(
            prompt, image_urls, contexts, system_prompt, tool_calls_result, None
        )
        call_kwargs: dict = {
            "model": self.router_id,
            "messages": messages,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if func_tool and not func_tool.empty():
            call_kwargs["tools"] = func_tool.get_func_desc_openai_style()
            call_kwargs["tool_choice"] = tool_choice

        max_attempts = len(self._resolved_model_list) + 1
        last_exc: Exception | None = None
        stream = None

        for attempt in range(max_attempts):
            try:
                stream = await self.router.acompletion(**call_kwargs)
                break
            except Exception as exc:
                last_exc = exc
                if self._is_403_usage_limit(exc):
                    if self._handle_403_usage_limit(exc):
                        await self._rebuild_router()
                        if not self.router:
                            break
                        continue
                logger.error(
                    f"Router [{self.router_id}] stream start failed "
                    f"(attempt {attempt + 1}/{max_attempts}): {exc}"
                )
                raise

        if stream is None:
            if last_exc is not None:
                raise last_exc
            raise RuntimeError(f"Router [{self.router_id}]: all providers exhausted.")

        # ── Stream accumulation (mirrors ProviderLiteLLM.text_chat_stream) ── #
        accumulated_content = ""
        accumulated_tool_calls: dict[int, dict] = {}
        final_usage: TokenUsage | None = None
        final_response_id: str | None = None
        chunk_resp = LLMResponse("assistant", is_chunk=True)

        async for chunk in stream:
            choice = chunk.choices[0] if chunk.choices else None
            delta = choice.delta if choice else None
            final_response_id = chunk.id

            if delta and delta.content:
                chunk_resp.id = chunk.id
                chunk_resp.result_chain = MessageChain(
                    chain=[Comp.Plain(delta.content)]
                )
                accumulated_content += delta.content
                yield chunk_resp

            if delta and delta.tool_calls:
                for tc_delta in delta.tool_calls:
                    idx = getattr(tc_delta, "index", None) or 0
                    if idx not in accumulated_tool_calls:
                        accumulated_tool_calls[idx] = {
                            "id": "",
                            "name": "",
                            "arguments": "",
                        }
                    if tc_delta.id:
                        accumulated_tool_calls[idx]["id"] = tc_delta.id
                    if tc_delta.function:
                        if tc_delta.function.name:
                            accumulated_tool_calls[idx]["name"] += tc_delta.function.name
                        if tc_delta.function.arguments:
                            accumulated_tool_calls[idx]["arguments"] += (
                                tc_delta.function.arguments
                            )

            if chunk.usage:
                final_usage = self._extract_usage(chunk.usage)

        final_resp = LLMResponse("assistant", is_chunk=False)
        final_resp.id = final_response_id

        if accumulated_content:
            final_resp.result_chain = MessageChain().message(accumulated_content)

        if accumulated_tool_calls and func_tool:
            args_ls: list = []
            func_name_ls: list = []
            tool_call_ids: list = []
            for tc_info in accumulated_tool_calls.values():
                name = tc_info["name"]
                for tool in func_tool.func_list:
                    if tool.name == name:
                        try:
                            args_ls.append(json.loads(tc_info["arguments"] or "{}"))
                        except json.JSONDecodeError:
                            args_ls.append({})
                        func_name_ls.append(name)
                        tool_call_ids.append(tc_info["id"])
                        break
            if args_ls:
                final_resp.role = "tool"
                final_resp.tools_call_args = args_ls
                final_resp.tools_call_name = func_name_ls
                final_resp.tools_call_ids = tool_call_ids

        final_resp.usage = final_usage

        if not accumulated_content and not final_resp.tools_call_args:
            raise EmptyModelOutputError(
                f"Router [{self.router_id}] stream produced no usable output."
            )

        yield final_resp

    async def terminate(self) -> None:
        pass  # No persistent resources to release.
