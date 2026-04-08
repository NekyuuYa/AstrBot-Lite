# AstrBot-Lite 消息处理全链路分析

本文档详细描述了 AstrBot-Lite 从接收到消息到发出回复的完整调用链条，涵盖了内置 Agent 逻辑、插件点位、Prompt 构建及工具调用过程。

---

## 1. 消息接收与管道进入 (Message Reception)

1.  **平台适配器 (Platform Adapter)**: 如 `AiocqhttpAdapter` 或 `TelegramAdapter` 接收到原始消息。
2.  **事件封装**: 适配器将消息封装为 `AstrMessageEvent` 对象。
3.  **管道调度**: 适配器调用 `PipelineScheduler.execute(event)`，启动异步处理管道。

## 2. 管道阶段执行 (Pipeline Stages)

`PipelineScheduler` 按照 `STAGES_ORDER` 依次执行以下阶段（洋葱模型）：

1.  **WakingCheckStage**: 检查是否被 @ 或触发唤醒词。
2.  **WhitelistCheckStage**: 检查白名单过滤。
3.  **SessionStatusCheckStage**: 检查会话是否被禁用。
4.  **RateLimitStage**: 频率限制检查。
5.  **PreProcessStage**: **[插件点位]** 允许插件在主逻辑前预处理消息。
6.  **ProcessStage**: 核心处理阶段（见下文）。
7.  **ResultDecorateStage**: 对结果进行装饰（如 T2I、语音转换）。
8.  **RespondStage**: 最终通过平台适配器发出消息。

---

## 3. 核心处理阶段 (ProcessStage)

`ProcessStage` 包含两个关键子阶段：

### 3.1 StarRequestSubStage (插件处理)
*   执行已激活的插件 Handler（通过 `event_handler` 注册的函数）。
*   插件如果返回 `ProviderRequest`，会触发内置 Agent 进行 LLM 调用。

### 3.2 AgentRequestSubStage (内置 Agent 处理)
这是机器人“大脑”的核心逻辑，主要流程如下：

#### A. 构建 Agent 环境 (build_main_agent)
1.  **选择 Provider**: 根据配置选择当前会话使用的 LLM 提供商。
2.  **加载历史**: 从数据库读取会话历史记录 (`json.loads(conversation.history)`)。
3.  **人格注入 (Persona)**: 
    *   解析当前选择的人格 (Persona)。
    *   将人格的 `prompt` 附加到 `system_prompt`。
    *   将人格预设的开场白 (`_begin_dialogs`) 插入到历史记录顶部。
4.  **能力注入 (Skills & Tools)**:
    *   **Skills**: 加载所有激活的技能，并构建技能描述 Prompt。
    *   **Tools**: 汇总来自人格的工具、插件注册的函数工具以及系统工具（知识库检索、沙盒、定时任务等）。
5.  **请求修饰**: 添加系统提醒（用户 ID、群名、当前时间等）和 Prompt 前缀。

#### B. 执行迭代循环 (run_agent)
使用 `AgentRunner` (基于 `ToolLoopAgentRunner`) 进行思考-行动循环：

1.  **准备上下文**: 合并 System Prompt、历史记录和当前 User Prompt。
2.  **调用 LLM (LiteLLM)**: 将上下文和工具定义发送给 LiteLLM。
3.  **接收响应**:
    *   **Delta (流式)**: 如果开启流式，实时 yield 文本片段。
    *   **Tool Call (工具调用)**: 如果 LLM 决定调用工具：
        *   `_handle_function_tools` 执行具体的 Python 函数。
        *   将工具返回结果包装成 `tool` 角色消息加入上下文。
        *   再次请求 LLM 进行思考，直到 LLM 给出最终回复或达到 `max_step`。
    *   **Final Result**: 获得最终回复文本。

---

## 4. 插件点位与 Hook

在上述流程中，插件可以通过以下方式介入：

1.  **OnPreMessageEvent**: 在 `PreProcessStage` 触发，可修改 `event.message_str`。
2.  **OnLLMRequestEvent**: 在发送给 LLM 之前触发，可修改 `ProviderRequest`（包括 Prompt、工具等）。
3.  **OnWaitingLLMRequestEvent**: 在等待 LLM 响应时触发。
4.  **函数工具 (FuncCall)**: 插件通过 `@command` 或工具注册，将自己的函数暴露给 Agent 调用。
5.  **OnAfterMessageSentEvent**: 消息发出后触发。

---

## 5. 结果返回 (Message Delivery)

1.  **结果设置**: Agent 的回复通过 `event.set_result()` 存入事件对象。
2.  **直接发送**: 某些工具调用过程中可能通过 `event.send()` 直接发送中间结果（如图片、文件）。
3.  **响应阶段**: `RespondStage` 读取 `event.get_result()`，调用平台适配器的 `send` 方法，将 `MessageChain` 转换为平台协议并发出。

---

## 重构启示 (For WEBUI_REDESIGN)

1.  **Agent 实体化**: 现在的 `build_main_agent` 过程相对松散，未来可以将其封装为独立的 `Agent` 类，包含完整的配置（模型、人格、工具组）。
2.  **Prompt 模板化**: 目前 Prompt 的拼接逻辑散落在各处，重构时应统一为模板管理器。
3.  **工具编组**: 插件工具和系统工具的加载逻辑可以更模块化，支持在 WebUI 中动态勾选工具组。
4.  **状态监控**: 链式调用的每一步（Step）都应产生 Trace 记录，以便在新的“模型调用追踪”面板中展示。
