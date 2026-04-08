"""LiteLLM unified provider adapter.

Acts as the single execution engine for all chat_completion providers.
Uses a "passthrough architecture": any config field not in the standard
exclusion list is automatically forwarded to litellm.acompletion(**kwargs).

Explicit mappings for known AstrBot-internal fields:
    gm_safety_settings    → safety_settings  (list[dict] with HARM_CATEGORY_* strings)
    gm_thinking_config    → thinking          ({"type": "enabled", "budget_tokens": N})
    anth_thinking_config  → thinking
    custom_extra_body     → extra_body
    ollama_disable_thinking → extra_body.think = False (via extra_body merge)
    custom_headers        → headers
    api_version           → api_version       (Azure)
    proxy                 → http_client       (persistent httpx client)
    timeout               → timeout
"""

import asyncio
import base64
import json
import re
from collections.abc import AsyncGenerator
from typing import Literal

import httpx
import litellm
from litellm import ModelResponse

import astrbot.core.message.components as Comp
from astrbot import logger
from astrbot.api.provider import Provider
from astrbot.core.agent.message import ContentPart, ImageURLPart, Message, TextPart
from astrbot.core.agent.tool import ToolSet
from astrbot.core.exceptions import EmptyModelOutputError
from astrbot.core.message.message_event_result import MessageChain
from astrbot.core.provider.entities import LLMResponse, TokenUsage, ToolCallsResult
from astrbot.core.utils.io import download_image_by_url

from ..register import register_provider_adapter

# ---------------------------------------------------------------------------
# Litellm global config
# ---------------------------------------------------------------------------
litellm.suppress_debug_info = True
litellm.set_verbose = False

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Fields that are standard routing/identity fields — NOT forwarded to litellm.
_STANDARD_FIELDS: frozenset[str] = frozenset(
    {
        "id",
        "type",
        "_litellm_original_type",
        "enable",
        "provider_type",
        "provider_source_id",
        # already mapped explicitly
        "model",
        "api_key",
        "api_base",
        "key",           # legacy multi-key list
        "timeout",
        "proxy",
        "api_version",
        "custom_headers",
        "custom_extra_body",
        "ollama_disable_thinking",
        "gm_safety_settings",
        "gm_thinking_config",
        "anth_thinking_config",
        "extra_params",  # user-supplied verbatim override dict
        # old AstrBot routing hint
        "provider",
        # stats/meta that providers used to track internally
        "image_moderation_error_patterns",
    }
)

# Maps AstrBot's short gm_safety_settings keys to Gemini's HARM_CATEGORY_* string
_GEMINI_CATEGORY_MAP: dict[str, str] = {
    "harassment": "HARM_CATEGORY_HARASSMENT",
    "hate_speech": "HARM_CATEGORY_HATE_SPEECH",
    "sexually_explicit": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
    "dangerous_content": "HARM_CATEGORY_DANGEROUS_CONTENT",
}
_GEMINI_VALID_THRESHOLDS: frozenset[str] = frozenset(
    {"BLOCK_NONE", "BLOCK_ONLY_HIGH", "BLOCK_MEDIUM_AND_ABOVE", "BLOCK_LOW_AND_ABOVE"}
)

# Maps legacy AstrBot provider type → LiteLLM model prefix.
# Used when the configured model string has no "/" (old format, e.g. "gpt-4o").
_TYPE_MODEL_PREFIX: dict[str, str] = {
    "openai_chat_completion": "openai",
    "googlegenai_chat_completion": "gemini",
    "anthropic_chat_completion": "anthropic",
    "groq_chat_completion": "groq",
    "xai_chat_completion": "xai",
    "openrouter_chat_completion": "openrouter",
    "zhipu_chat_completion": "zhipuai",
    "aihubmix_chat_completion": "openai",
    "kimi_code_chat_completion": "openai",
    "litellm_chat_completion": None,  # already has prefix
}

# LiteLLM exception type strings used for error detection without hard imports
_RATE_LIMIT_TYPES = ("RateLimitError",)
_CONTEXT_EXCEEDED_TYPES = ("ContextWindowExceededError",)
_AUTH_ERROR_TYPES = ("AuthenticationError",)


@register_provider_adapter(
    "litellm_chat_completion",
    "LiteLLM 统一接口适配器（支持 OpenAI, Anthropic, Gemini, Azure, Ollama 等 100+ 服务商）",
    default_config_tmpl={
        "id": "my-model",
        "type": "litellm_chat_completion",
        "enable": True,
        "model": "openai/gpt-4o",
        "api_key": "",
        "api_base": "",
        "extra_params": {},
    },
)
class ProviderLiteLLM(Provider):
    """Unified provider adapter powered by the LiteLLM SDK.

    Handles legacy AstrBot provider configs (openai_chat_completion,
    googlegenai_chat_completion, anthropic_chat_completion, etc.) transparently
    via config normalization, while also supporting the new litellm_chat_completion
    format natively.

    Config fields (all optional unless noted):
        model          - LiteLLM model string: "<provider>/<model_name>"
                         If no "/" found, a prefix is added from _TYPE_MODEL_PREFIX
                         based on the config `type`.
        api_key        - API key (single string).  Also accepts legacy `key` list.
        api_base       - Base URL override.
        timeout        - Request timeout in seconds (default: 180).
        proxy          - HTTP/HTTPS proxy URL.
        api_version    - Azure OpenAI API version.
        custom_headers - Dict of extra HTTP headers.
        custom_extra_body       - Dict forwarded as extra_body.
        ollama_disable_thinking - Bool; sets extra_body.think=False.
        gm_safety_settings      - {"harassment": "BLOCK_NONE", ...}
        gm_thinking_config      - {"budget": N}  (Gemini 2.5+)
        anth_thinking_config    - {"type": "enabled", "budget_tokens": N}
        extra_params   - Dict of verbatim kwargs for litellm.acompletion()
                         (highest priority, overrides everything else).
        <any other field> - Passed through to litellm.acompletion() verbatim.
    """

    def __init__(self, provider_config: dict, provider_settings: dict) -> None:
        super().__init__(provider_config, provider_settings)

        # When redirected from a legacy type, _litellm_original_type carries the
        # original adapter name (e.g. "openai_chat_completion") so we can derive
        # the correct LiteLLM model prefix.
        original_type = (
            provider_config.get("_litellm_original_type")
            or provider_config.get("type", "litellm_chat_completion")
        )

        # ── API key: prefer explicit api_key, fall back to legacy key[] list ──
        api_key = provider_config.get("api_key", "") or ""
        if not api_key:
            key_list = provider_config.get("key", [])
            if isinstance(key_list, list) and key_list:
                api_key = key_list[0] or ""
            elif isinstance(key_list, str):
                api_key = key_list or ""
        self.api_key: str = api_key

        self.api_base: str | None = provider_config.get("api_base", "") or None
        self.timeout: int = int(provider_config.get("timeout", 180))
        self.proxy: str | None = provider_config.get("proxy", "") or None
        self.image_moderation_error_patterns: list[str] = (
            provider_config.get("image_moderation_error_patterns", []) or []
        )

        # ── Model string: add LiteLLM provider prefix if missing ──────────────
        raw_model = provider_config.get("model", "openai/gpt-4o") or "openai/gpt-4o"
        if "/" not in raw_model:
            # Azure: api_version presence signals Azure regardless of type
            if provider_config.get("api_version"):
                prefix = "azure"
            else:
                prefix = _TYPE_MODEL_PREFIX.get(original_type, "openai")
            raw_model = f"{prefix}/{raw_model}" if prefix else raw_model
        self.model_name: str = raw_model
        self.set_model(self.model_name)

        # ── Build mapped params from passthrough + explicit mappings ──────────
        self._mapped_params: dict = self._prepare_extra_params(provider_config)

        # ── User-supplied verbatim overrides (highest priority) ───────────────
        self.user_extra_params: dict = provider_config.get("extra_params", {}) or {}

        # ── Persistent httpx client for proxy ─────────────────────────────────
        self._http_client: httpx.AsyncClient | None = self._build_http_client()

    # ------------------------------------------------------------------ #
    # Config normalisation helpers                                         #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _prepare_extra_params(config: dict) -> dict:
        """Build the extra kwargs dict to pass to litellm.acompletion().

        Strategy (applied in order, later entries can overwrite earlier):
        1. Collect all config fields NOT in _STANDARD_FIELDS passthrough.
        2. Apply explicit AstrBot→LiteLLM field mappings.

        The caller's `extra_params` dict is NOT merged here — that is applied
        last in `_build_litellm_kwargs()` at highest priority.
        """
        params: dict = {}

        # ── 1. Passthrough: collect non-standard fields verbatim ──────────────
        for key, value in config.items():
            if key not in _STANDARD_FIELDS and value not in (None, "", [], {}):
                params[key] = value

        # ── 2. Explicit mappings ───────────────────────────────────────────────

        # Azure api_version
        if api_version := config.get("api_version"):
            params["api_version"] = api_version

        # HTTP headers
        headers = config.get("custom_headers", {})
        if isinstance(headers, dict) and headers:
            params["headers"] = {str(k): str(v) for k, v in headers.items()}

        # extra_body: start from custom_extra_body, layer Ollama override
        extra_body: dict = {}
        ceb = config.get("custom_extra_body", {})
        if isinstance(ceb, dict):
            extra_body.update(ceb)
        if config.get("ollama_disable_thinking"):
            # Ollama: reasoning_effort=none reliably maps to think=false
            extra_body.pop("reasoning", None)
            extra_body.pop("think", None)
            extra_body["reasoning_effort"] = "none"
        if extra_body:
            params["extra_body"] = extra_body

        # Gemini safety settings: map to list[dict] with HARM_CATEGORY_* strings
        gm_safety = config.get("gm_safety_settings", {})
        if isinstance(gm_safety, dict) and gm_safety:
            mapped = []
            for key, threshold in gm_safety.items():
                category = _GEMINI_CATEGORY_MAP.get(key)
                if category and threshold in _GEMINI_VALID_THRESHOLDS:
                    mapped.append({"category": category, "threshold": threshold})
                else:
                    logger.warning(
                        f"LiteLLM: ignoring unknown safety setting {key!r}={threshold!r}"
                    )
            if mapped:
                params["safety_settings"] = mapped

        # Thinking config: prefer Anthropic, fall back to Gemini
        anth = config.get("anth_thinking_config", {})
        if isinstance(anth, dict) and anth.get("type") in ("enabled", "disabled"):
            thinking: dict = {"type": anth["type"]}
            if "budget_tokens" in anth:
                thinking["budget_tokens"] = int(anth["budget_tokens"])
            params["thinking"] = thinking
        elif (gm_think := config.get("gm_thinking_config", {})) and isinstance(
            gm_think, dict
        ):
            budget = gm_think.get("budget")
            if budget is not None:
                params["thinking"] = {
                    "type": "enabled",
                    "budget_tokens": int(budget),
                }

        return params

    def _build_http_client(self) -> httpx.AsyncClient | None:
        if not self.proxy:
            return None
        try:
            transport = httpx.AsyncHTTPTransport(proxy=self.proxy)
            return httpx.AsyncClient(transport=transport, timeout=float(self.timeout))
        except Exception as exc:
            logger.warning(f"LiteLLM: failed to create proxy http client: {exc}")
            return None

    # ------------------------------------------------------------------ #
    # Required Provider interface                                          #
    # ------------------------------------------------------------------ #

    def get_current_key(self) -> str:
        return self.api_key

    def set_key(self, key: str) -> None:
        self.api_key = key

    async def get_models(self) -> list[str]:
        """Return available models.

        For OpenAI-compatible endpoints with an api_base set, attempt to list
        models from the endpoint.  Falls back to returning the configured model.
        """
        if self.api_base:
            try:
                async with httpx.AsyncClient(
                    timeout=10.0,
                    transport=(
                        httpx.AsyncHTTPTransport(proxy=self.proxy)
                        if self.proxy
                        else None
                    ),
                ) as client:
                    resp = await client.get(
                        self.api_base.rstrip("/") + "/models",
                        headers={"Authorization": f"Bearer {self.api_key}"},
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        ids = [m["id"] for m in data.get("data", []) if "id" in m]
                        if ids:
                            return sorted(ids)
            except Exception:
                pass  # fall through to default
        return [self.model_name]

    # ------------------------------------------------------------------ #
    # Internal helpers                                                     #
    # ------------------------------------------------------------------ #

    def _build_litellm_kwargs(self, model: str | None = None) -> dict:
        """Build the complete kwargs dict for litellm.acompletion().

        Priority (lowest → highest):
            1. _mapped_params  (auto-collected + explicitly mapped from config)
            2. base fields     (model, api_key, api_base, timeout, http_client)
            3. user_extra_params (verbatim user override dict — highest priority)
        """
        kwargs: dict = {}

        # 1. Mapped params (passthrough + explicit mappings)
        kwargs.update(self._mapped_params)

        # 2. Core routing fields (always override mapped params)
        kwargs["model"] = model or self.model_name
        kwargs["timeout"] = self.timeout
        if self.api_key:
            kwargs["api_key"] = self.api_key
        if self.api_base:
            kwargs["api_base"] = self.api_base
        if self._http_client is not None:
            kwargs["http_client"] = self._http_client

        # 3. User verbatim overrides (highest priority)
        if self.user_extra_params:
            kwargs.update(self.user_extra_params)

        return kwargs

    def _extract_usage(self, usage) -> TokenUsage:
        if usage is None:
            return TokenUsage()
        ptd = getattr(usage, "prompt_tokens_details", None)
        cached = getattr(ptd, "cached_tokens", 0) if ptd else 0
        cached = cached if isinstance(cached, int) else 0
        prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
        completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
        return TokenUsage(
            input_other=prompt_tokens - cached,
            input_cached=cached,
            output=completion_tokens,
        )

    def _compute_cost(self, response: ModelResponse) -> float | None:
        try:
            cost = litellm.completion_cost(completion_response=response)
            return float(cost) if cost is not None else None
        except Exception:
            return None

    @staticmethod
    def _classify_error(e: Exception) -> str:
        """Return a short error class tag for retry decisions."""
        type_name = type(e).__name__
        msg = str(e).lower()
        if type_name in _RATE_LIMIT_TYPES or "429" in str(e):
            return "rate_limit"
        if type_name in _CONTEXT_EXCEEDED_TYPES or "maximum context length" in msg:
            return "context_exceeded"
        if type_name in _AUTH_ERROR_TYPES or "authentication" in msg:
            return "auth_error"
        if "function calling is not enabled" in msg or (
            "tool" in msg and "support" in msg
        ):
            return "no_tools"
        if "the model is not a vlm" in msg or "not support vision" in msg:
            return "no_vision"
        return "other"

    def _is_image_moderation_error(self, e: Exception) -> bool:
        if not self.image_moderation_error_patterns:
            return False
        msg = str(e).lower()
        return any(p.lower() in msg for p in self.image_moderation_error_patterns if p)

    async def _encode_image(self, image_ref: str) -> str | None:
        if image_ref.startswith("base64://"):
            return image_ref.replace("base64://", "data:image/jpeg;base64,")
        try:
            if image_ref.startswith("http"):
                local_path = await download_image_by_url(image_ref)
            elif image_ref.startswith("file:///"):
                local_path = image_ref.replace("file:///", "")
            else:
                local_path = image_ref
            with open(local_path, "rb") as f:
                data = base64.b64encode(f.read()).decode()
            return f"data:image/jpeg;base64,{data}"
        except Exception as exc:
            logger.warning(f"LiteLLM: failed to encode image {image_ref}: {exc}")
            return None

    def _parse_response(
        self, completion: ModelResponse, tools: ToolSet | None
    ) -> LLMResponse:
        llm_response = LLMResponse("assistant")

        if not completion.choices:
            raise EmptyModelOutputError(
                f"LiteLLM completion has no choices. id={completion.id}"
            )
        choice = completion.choices[0]

        if choice.message.content is not None:
            text = str(choice.message.content).strip()
            think_pattern = re.compile(r"<think>(.*?)</think>", re.DOTALL)
            matches = think_pattern.findall(text)
            if matches:
                llm_response.reasoning_content = "\n".join(m.strip() for m in matches)
                text = think_pattern.sub("", text).strip()
            text = re.sub(r"</think>\s*$", "", text).strip()
            if text:
                llm_response.result_chain = MessageChain().message(text)

        if choice.message.tool_calls and tools is not None:
            args_ls, func_name_ls, tool_call_ids = [], [], []
            for tc in choice.message.tool_calls:
                for tool in tools.func_list:
                    if tc.type == "function" and tool.name == tc.function.name:
                        raw_args = tc.function.arguments
                        args = (
                            json.loads(raw_args)
                            if isinstance(raw_args, str)
                            else raw_args
                        )
                        args_ls.append(args)
                        func_name_ls.append(tc.function.name)
                        tool_call_ids.append(tc.id)
                        break
            if args_ls:
                llm_response.role = "tool"
                llm_response.tools_call_args = args_ls
                llm_response.tools_call_name = func_name_ls
                llm_response.tools_call_ids = tool_call_ids

        has_text = bool((llm_response.completion_text or "").strip())
        has_reasoning = bool((llm_response.reasoning_content or "").strip())
        if not has_text and not has_reasoning and not llm_response.tools_call_args:
            raise EmptyModelOutputError(
                f"LiteLLM completion has no usable output. id={completion.id}"
            )

        llm_response.raw_completion = completion
        llm_response.id = completion.id
        if completion.usage:
            llm_response.usage = self._extract_usage(completion.usage)
        llm_response.cost_usd = self._compute_cost(completion)
        return llm_response

    async def _build_messages(
        self,
        prompt: str | None,
        image_urls: list[str] | None,
        contexts: list[dict] | list[Message] | None,
        system_prompt: str | None,
        tool_calls_result: ToolCallsResult | list[ToolCallsResult] | None,
        extra_user_content_parts: list[ContentPart] | None,
    ) -> list[dict]:
        messages: list[dict] = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        if contexts:
            for msg in self._ensure_message_to_dicts(contexts):
                clean = {k: v for k, v in msg.items() if k != "_no_save"}
                messages.append(clean)

        if tool_calls_result:
            tcr_list = (
                [tool_calls_result]
                if isinstance(tool_calls_result, ToolCallsResult)
                else tool_calls_result
            )
            for tcr in tcr_list:
                messages.extend(tcr.to_openai_messages())

        if prompt is not None or image_urls or extra_user_content_parts:
            content_parts: list[dict] = []

            if prompt and prompt.strip():
                content_parts.append({"type": "text", "text": prompt})
            elif image_urls:
                content_parts.append({"type": "text", "text": "[图片]"})
            elif extra_user_content_parts:
                content_parts.append({"type": "text", "text": " "})

            if extra_user_content_parts:
                for part in extra_user_content_parts:
                    if isinstance(part, TextPart):
                        content_parts.append({"type": "text", "text": part.text})
                    elif isinstance(part, ImageURLPart):
                        encoded = await self._encode_image(part.image_url.url)
                        if encoded:
                            content_parts.append(
                                {"type": "image_url", "image_url": {"url": encoded}}
                            )
                    else:
                        content_parts.append(part.model_dump())

            if image_urls:
                for img in image_urls:
                    encoded = await self._encode_image(img)
                    if encoded:
                        content_parts.append(
                            {"type": "image_url", "image_url": {"url": encoded}}
                        )

            if (
                len(content_parts) == 1
                and content_parts[0]["type"] == "text"
                and not image_urls
                and not extra_user_content_parts
            ):
                messages.append({"role": "user", "content": content_parts[0]["text"]})
            elif content_parts:
                messages.append({"role": "user", "content": content_parts})

        return messages

    @staticmethod
    def _strip_images_from_messages(messages: list[dict]) -> list[dict]:
        """Return a copy of messages with image_url content parts removed."""
        cleaned = []
        for msg in messages:
            content = msg.get("content")
            if isinstance(content, list):
                new_content = [
                    p for p in content
                    if not (isinstance(p, dict) and p.get("type") == "image_url")
                ]
                if not new_content:
                    new_content = [{"type": "text", "text": "[图片]"}]
                cleaned.append({**msg, "content": new_content})
            else:
                cleaned.append(msg)
        return cleaned

    # ------------------------------------------------------------------ #
    # Public Provider interface                                            #
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
        messages = await self._build_messages(
            prompt, image_urls, contexts, system_prompt,
            tool_calls_result, extra_user_content_parts,
        )
        call_kwargs = self._build_litellm_kwargs(model)
        call_kwargs["messages"] = messages

        if func_tool and not func_tool.empty():
            call_kwargs["tools"] = func_tool.get_func_desc_openai_style()
            call_kwargs["tool_choice"] = tool_choice

        max_retries = 5
        image_fallback_used = False
        current_func_tool = func_tool
        last_exc: Exception | None = None

        for attempt in range(max_retries):
            try:
                completion: ModelResponse = await litellm.acompletion(**call_kwargs)
                return self._parse_response(completion, current_func_tool)
            except Exception as e:
                last_exc = e
                tag = self._classify_error(e)
                model_id = call_kwargs.get("model", self.model_name)

                if tag == "rate_limit":
                    logger.warning(
                        f"LiteLLM [{model_id}]: rate limited, retry {attempt+1}/{max_retries}"
                    )
                    await asyncio.sleep(min(2 ** attempt, 30))
                    continue

                if tag == "context_exceeded":
                    logger.warning(
                        f"LiteLLM [{model_id}]: context length exceeded, popping oldest message"
                    )
                    # Pop oldest non-system message
                    msgs = call_kwargs["messages"]
                    for i, m in enumerate(msgs):
                        if m.get("role") != "system":
                            msgs.pop(i)
                            break
                    continue

                if tag == "no_tools" and current_func_tool:
                    logger.info(
                        f"LiteLLM [{model_id}]: tools not supported, disabling tool_call"
                    )
                    call_kwargs.pop("tools", None)
                    call_kwargs.pop("tool_choice", None)
                    current_func_tool = None
                    continue

                if (tag == "no_vision" or self._is_image_moderation_error(e)):
                    if not image_fallback_used and image_urls:
                        logger.warning(
                            f"LiteLLM [{model_id}]: vision error, retrying without images"
                        )
                        call_kwargs["messages"] = self._strip_images_from_messages(
                            call_kwargs["messages"]
                        )
                        image_fallback_used = True
                        continue

                if tag == "auth_error":
                    raise Exception(
                        f"LiteLLM [{model_id}] 鉴权失败，请检查 API Key: {e}"
                    ) from e

                logger.error(f"LiteLLM [{model_id}] call failed: {e}")
                raise

        if last_exc is not None:
            raise last_exc
        raise Exception(f"LiteLLM [{self.model_name}] 请求失败（已重试 {max_retries} 次）")

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
        messages = await self._build_messages(
            prompt, image_urls, contexts, system_prompt, tool_calls_result, None,
        )
        call_kwargs = self._build_litellm_kwargs(model)
        call_kwargs["messages"] = messages
        call_kwargs["stream"] = True
        call_kwargs["stream_options"] = {"include_usage": True}

        if func_tool and not func_tool.empty():
            call_kwargs["tools"] = func_tool.get_func_desc_openai_style()
            call_kwargs["tool_choice"] = tool_choice

        model_id = call_kwargs.get("model", self.model_name)
        max_retries = 3
        last_exc: Exception | None = None

        for attempt in range(max_retries):
            try:
                stream = await litellm.acompletion(**call_kwargs)
                break
            except Exception as e:
                last_exc = e
                tag = self._classify_error(e)
                if tag == "rate_limit":
                    logger.warning(
                        f"LiteLLM [{model_id}] stream: rate limited, retry {attempt+1}"
                    )
                    await asyncio.sleep(min(2 ** attempt, 30))
                    continue
                if tag == "auth_error":
                    raise Exception(
                        f"LiteLLM [{model_id}] 鉴权失败，请检查 API Key: {e}"
                    ) from e
                logger.error(f"LiteLLM [{model_id}] stream call failed: {e}")
                raise
        else:
            if last_exc is not None:
                raise last_exc
            raise Exception(f"LiteLLM [{model_id}] stream 请求失败")

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
                        accumulated_tool_calls[idx] = {"id": "", "name": "", "arguments": ""}
                    if tc_delta.id:
                        accumulated_tool_calls[idx]["id"] = tc_delta.id
                    if tc_delta.function:
                        if tc_delta.function.name:
                            accumulated_tool_calls[idx]["name"] += tc_delta.function.name
                        if tc_delta.function.arguments:
                            accumulated_tool_calls[idx]["arguments"] += tc_delta.function.arguments

            if chunk.usage:
                final_usage = self._extract_usage(chunk.usage)

        final_resp = LLMResponse("assistant", is_chunk=False)
        final_resp.id = final_response_id

        if accumulated_content:
            final_resp.result_chain = MessageChain().message(accumulated_content)

        if accumulated_tool_calls and func_tool:
            args_ls, func_name_ls, tool_call_ids = [], [], []
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
                f"LiteLLM [{model_id}] stream produced no usable output."
            )

        yield final_resp

    async def terminate(self) -> None:
        if self._http_client is not None:
            await self._http_client.aclose()
