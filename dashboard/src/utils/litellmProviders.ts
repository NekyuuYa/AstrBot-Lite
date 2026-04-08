export interface FieldDef {
  key: string
  label: string
  type: 'text' | 'password' | 'textarea'
  required: boolean
  hint?: string
  placeholder?: string
}

export interface LiteLLMProviderOption {
  value: string
  label: string
}

export const LITELLM_PROVIDERS: LiteLLMProviderOption[] = [
  { value: 'openai', label: 'OpenAI' },
  { value: 'anthropic', label: 'Anthropic' },
  { value: 'gemini', label: 'Google Gemini' },
  { value: 'azure', label: 'Azure OpenAI' },
  { value: 'ollama', label: 'Ollama' },
  { value: 'vllm', label: 'vLLM' },
  { value: 'groq', label: 'Groq' },
  { value: 'openrouter', label: 'OpenRouter' },
  { value: 'deepseek', label: 'DeepSeek' },
  { value: 'bedrock', label: 'AWS Bedrock' },
  { value: 'vertex_ai', label: 'Google Vertex AI' },
  { value: 'mistral', label: 'Mistral AI' },
  { value: 'cohere', label: 'Cohere' },
  { value: 'together_ai', label: 'Together AI' },
  { value: 'huggingface', label: 'HuggingFace' },
  { value: 'xai', label: 'xAI (Grok)' },
  { value: 'openai_compatible', label: 'OpenAI Compatible' },
]

/** Fields shown for every provider (always rendered first). */
export const COMMON_FIELDS: FieldDef[] = [
  {
    key: 'id',
    label: 'Model ID',
    type: 'text',
    required: true,
    hint: 'Unique identifier for this model entry (e.g. my-gpt4o)',
  },
  {
    key: 'model_name',
    label: 'Model Name',
    type: 'text',
    required: true,
    hint: 'Model name without provider prefix (e.g. gpt-4o, claude-3-5-sonnet-20241022)',
    placeholder: 'gpt-4o',
  },
]

/** Per-provider fields rendered after COMMON_FIELDS. */
export const PROVIDER_FIELDS: Record<string, FieldDef[]> = {
  openai: [
    { key: 'api_key', label: 'API Key', type: 'password', required: true },
    {
      key: 'api_base',
      label: 'API Base URL',
      type: 'text',
      required: false,
      hint: 'Leave empty for default (https://api.openai.com/v1)',
    },
  ],
  anthropic: [
    { key: 'api_key', label: 'API Key', type: 'password', required: true },
    { key: 'api_base', label: 'API Base URL', type: 'text', required: false },
  ],
  gemini: [
    { key: 'api_key', label: 'API Key', type: 'password', required: true },
  ],
  azure: [
    { key: 'api_key', label: 'API Key', type: 'password', required: true },
    {
      key: 'api_base',
      label: 'Azure Endpoint URL',
      type: 'text',
      required: true,
      hint: 'https://{resource-name}.openai.azure.com/',
    },
    {
      key: 'api_version',
      label: 'API Version',
      type: 'text',
      required: false,
      placeholder: '2024-02-01',
    },
  ],
  ollama: [
    {
      key: 'api_base',
      label: 'Server URL',
      type: 'text',
      required: true,
      hint: 'http://localhost:11434',
      placeholder: 'http://localhost:11434',
    },
  ],
  vllm: [
    {
      key: 'api_base',
      label: 'Server URL',
      type: 'text',
      required: true,
      placeholder: 'http://localhost:8000',
    },
    {
      key: 'api_key',
      label: 'API Key',
      type: 'password',
      required: false,
      hint: 'Optional for local vLLM instances',
    },
  ],
  groq: [
    { key: 'api_key', label: 'API Key', type: 'password', required: true },
  ],
  openrouter: [
    { key: 'api_key', label: 'API Key', type: 'password', required: true },
  ],
  deepseek: [
    { key: 'api_key', label: 'API Key', type: 'password', required: true },
    { key: 'api_base', label: 'API Base URL', type: 'text', required: false },
  ],
  bedrock: [
    {
      key: 'api_key',
      label: 'AWS Access Key ID',
      type: 'password',
      required: false,
      hint: 'Uses env vars or IAM role if empty',
    },
    {
      key: 'api_base',
      label: 'AWS Region',
      type: 'text',
      required: false,
      placeholder: 'us-east-1',
    },
  ],
  vertex_ai: [
    {
      key: 'api_base',
      label: 'GCP Project ID',
      type: 'text',
      required: false,
    },
  ],
  mistral: [
    { key: 'api_key', label: 'API Key', type: 'password', required: true },
  ],
  cohere: [
    { key: 'api_key', label: 'API Key', type: 'password', required: true },
  ],
  together_ai: [
    { key: 'api_key', label: 'API Key', type: 'password', required: true },
  ],
  huggingface: [
    {
      key: 'api_key',
      label: 'API Key',
      type: 'password',
      required: false,
    },
    {
      key: 'api_base',
      label: 'Inference Endpoint',
      type: 'text',
      required: false,
      hint: 'HuggingFace Inference Endpoint URL (optional)',
    },
  ],
  xai: [
    { key: 'api_key', label: 'API Key', type: 'password', required: true },
  ],
  openai_compatible: [
    {
      key: 'api_base',
      label: 'API Base URL',
      type: 'text',
      required: true,
      hint: 'Base URL of the OpenAI-compatible API',
    },
    {
      key: 'api_key',
      label: 'API Key',
      type: 'password',
      required: false,
    },
  ],
}

/**
 * Parse provider prefix from a litellm model string.
 * e.g. "openai/gpt-4o" → "openai"
 * Returns '' if no known prefix is found.
 */
export function parseLiteLLMProvider(modelString: string): string {
  if (!modelString) return ''
  const idx = modelString.indexOf('/')
  if (idx === -1) return ''
  const prefix = modelString.slice(0, idx)
  return LITELLM_PROVIDERS.some((p) => p.value === prefix) ? prefix : prefix
}

/**
 * Parse model name (without provider prefix) from a litellm model string.
 * e.g. "openai/gpt-4o" → "gpt-4o"
 */
export function parseLiteLLMModel(modelString: string): string {
  if (!modelString) return ''
  const idx = modelString.indexOf('/')
  if (idx === -1) return modelString
  return modelString.slice(idx + 1)
}
