"""AstrBot Agentic Refactor (AAR) — 核心编排引擎包。

本包实现 AAR 架构的核心组件：
- PromptManager: Prompt 片段注册表
- AgentManager: Agent 智能体配置管理
- ContextPolicyRegistry: 上下文策略引擎
- PipelineOrchestrator: System Prompt 七阶段装配管道
- PersonaProxy: 旧插件兼容拦截器
"""

from astrbot.core.aar.agent_manager import AgentManager
from astrbot.core.aar.context_policy import ContextPolicyRegistry
from astrbot.core.aar.legacy_adapter import PersonaProxy
from astrbot.core.aar.orchestrator import AssemblyContext, PipelineOrchestrator
from astrbot.core.aar.prompt_manager import PromptManager

__all__ = [
    "AgentManager",
    "AssemblyContext",
    "ContextPolicyRegistry",
    "PersonaProxy",
    "PipelineOrchestrator",
    "PromptManager",
]
