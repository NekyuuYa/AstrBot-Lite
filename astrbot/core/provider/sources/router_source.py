"""LiteLLM Model Router Provider.

A virtual provider that groups multiple real providers to provide 
High Availability, Load Balancing, and Fallback mechanisms.
"""

import asyncio
import json
from collections.abc import AsyncGenerator
from typing import Literal

import litellm
from litellm import Router

from astrbot import logger
from astrbot.api.provider import Provider
from astrbot.core.provider.entities import LLMResponse
from .litellm_source import ProviderLiteLLM

class ProviderRouter(ProviderLiteLLM):
    """Model Router powered by LiteLLM Router.
    
    It behaves like a normal Provider but internally routes requests to 
    a list of configured models based on health, latency, or order.
    """
    
    def __init__(self, provider_config: dict, provider_settings: dict) -> None:
        # We don't call super().__init__ because we manage multiple models
        Provider.__init__(self, provider_config, provider_settings)
        
        self.router_id = provider_config.get("id")
        self.model_list_configs = provider_config.get("model_list", [])
        self.routing_strategy = provider_config.get("routing_strategy", "simple-shuffle")
        
        # Configure the LiteLLM Router
        # Each item in model_list should be a LiteLLM-compatible model config
        # We derive these from the actual provider configs during initialization
        self.router: Router | None = None
        self._initialized = False

    async def initialize(self) -> None:
        """Late initialization to ensure all referenced providers are ready."""
        if self._initialized:
            return
            
        # The actual model list for LiteLLM
        litellm_model_list = []
        
        # model_list_configs stores IDs of other providers or inline configs
        for item in self.model_list_configs:
            # item format: {"model_name": "...", "litellm_params": {...}}
            litellm_model_list.append(item)
            
        if not litellm_model_list:
            logger.warning(f"Router [{self.router_id}] has no models configured.")
            return

        self.router = Router(
            model_list=litellm_model_list,
            routing_strategy=self.routing_strategy,
            set_verbose=False,
            num_retries=3, # Default retries for fallbacks
            allowed_fails=1, # Number of fails before cooldown
            cooldown_time=60, # Default cooldown 60s
        )
        self._initialized = True
        logger.info(f"Router [{self.router_id}] initialized with {len(litellm_model_list)} models.")

    def _build_litellm_kwargs(self, model: str | None = None) -> dict:
        """Override to remove base model fields since Router handles them."""
        kwargs = self._prepare_extra_params(self.provider_settings)
        # Router handles 'model' via model_name
        return kwargs

    async def text_chat(self, **kwargs) -> LLMResponse:
        if not self.router:
            await self.initialize()
        
        # Use router.acompletion instead of litellm.acompletion
        try:
            # We must pass model_name to let router pick from its list
            # Here kwargs['model'] might be our Router ID, we map it back
            response = await self.router.acompletion(**kwargs)
            return self._parse_response(response, kwargs.get("func_tool"))
        except Exception as e:
            logger.error(f"Router [{self.router_id}] failed: {e}")
            raise

    async def text_chat_stream(self, **kwargs) -> AsyncGenerator[LLMResponse, None]:
        if not self.router:
            await self.initialize()
            
        try:
            stream = await self.router.acompletion(stream=True, **kwargs)
            # Standard stream processing from ProviderLiteLLM...
            # (In practice, we'll reuse the logic from litellm_source.py)
            async for chunk in stream:
                # yield parsed chunks...
                pass
        except Exception as e:
            logger.error(f"Router [{self.router_id}] stream failed: {e}")
            raise
