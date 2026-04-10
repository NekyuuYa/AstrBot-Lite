<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useTheme } from 'vuetify'
import axios from 'axios'
import { useModuleI18n } from '@/i18n/composables'
import DialogOptionSelector from '@/components/shared/DialogOptionSelector.vue'
import '@/styles/dashboard-shell.css'

const props = defineProps<{ agentId?: string }>()
const route = useRoute()
const router = useRouter()
const theme = useTheme()
const isDark = computed(() => theme.global.current.value.dark)
const { tm } = useModuleI18n('features/aar-agents')

const isNew = computed(() => {
  const id = props.agentId || (route.params.agentId as string)
  return id === '__new__'
})
const currentAgentId = computed(() => {
  const id = props.agentId || (route.params.agentId as string)
  return id === '__new__' ? '' : id
})

// --- State ---
const loading = ref(false)
const form = ref<any>({
  agent_id: '',
  name: '',
  persona_id: null,
  prompts: [],
  tools: [],
  skills: [],
  context_policy: 'sys.batch_eviction',
  interceptors: [],
  config: defaultCapConfig(),
  tags: [],
})
const tagInput = ref('')

// Available prompts for the picker
const allPrompts = ref<any[]>([])
const promptPickerOpen = ref(false)
const promptPickerSelection = ref<string[]>([])

// Stages for prompt display
const stages = ref<any[]>([])

// Persona options
const allPersonas = ref<any[]>([])

const allTools = ref<any[]>([])
const allSkills = ref<any[]>([])

// Capability config helpers
function defaultCapConfig() {
  return {
    knowledgebase: { enabled: false, kb_names: [] as string[], fusion_top_k: 3, final_top_k: 3, agentic_mode: false },
    websearch: { enabled: false, provider: 'tavily', tavily_key: [] as string[], bocha_key: [] as string[], brave_key: [] as string[], baidu_key: '', show_link: true },
    computer_use: { runtime: 'none', require_admin: false, booter: 'shipyard_neo', neo_endpoint: '', neo_token: '', neo_profile: '', neo_ttl: 600 },
    proactive: { enabled: false },
  }
}

// Snackbar
const snackbar = ref({ show: false, text: '', color: 'success' })
function toast(text: string, color = 'success') {
  snackbar.value = { show: true, text, color }
}

// Stage category colors
const categoryColors: Record<string, string> = {
  SystemBase: 'blue',
  Identity: 'purple',
  Context: 'teal',
  Abilities: 'orange',
  Instruction: 'indigo',
  Constraint: 'red',
  Refinement: 'grey',
}

// Prompts grouped by stage
const promptsByStage = computed(() => {
  const map: Record<string, any[]> = {}
  for (const s of stages.value) {
    map[s.id] = []
  }
  for (const pid of (form.value.prompts || [])) {
    const p = allPrompts.value.find((x: any) => x.prompt_id === pid)
    if (p && map[p.category]) {
      map[p.category].push(p)
    }
  }
  return map
})

// Context policy options
const policyOptions = [
  { title: tm('policies.sys.batch_eviction') || 'sys.batch_eviction', value: 'sys.batch_eviction' },
]

const personaSelectorItems = computed(() =>
  allPersonas.value.map((p: any) => ({
    title: p.persona_id,
    value: p.persona_id,
    subtitle: p.system_prompt || ''
  }))
)

const contextPolicySelectorItems = computed(() =>
  policyOptions.map((policy) => ({
    title: policy.title,
    value: policy.value,
    subtitle: policy.value
  }))
)

const toolSelectorItems = computed(() =>
  allTools.value.map((tool: any) => ({
    title: tool.name,
    value: tool.name,
    subtitle: tool.description || tool.origin_name || ''
  }))
)

const skillSelectorItems = computed(() =>
  allSkills.value.map((skill: any) => ({
    title: skill.name,
    value: skill.name,
    subtitle: skill.description || ''
  }))
)

// --- API ---
async function loadAgent() {
  if (isNew.value) return
  loading.value = true
  try {
    const res = await axios.get(`/api/agents/${currentAgentId.value}`)
    if (res.data.status === 'ok') {
      const data = res.data.data
      const defaults = defaultCapConfig()
      const rawCfg = data.config || {}
      form.value = {
        agent_id: data.agent_id || '',
        name: data.name || '',
        persona_id: data.persona_id || null,
        prompts: data.prompts || [],
        tools: data.tools || [],
        skills: data.skills || [],
        context_policy: data.context_policy || 'sys.batch_eviction',
        interceptors: data.interceptors || [],
        config: {
          ...rawCfg,
          knowledgebase: { ...defaults.knowledgebase, ...(rawCfg.knowledgebase || {}) },
          websearch: { ...defaults.websearch, ...(rawCfg.websearch || {}) },
          computer_use: { ...defaults.computer_use, ...(rawCfg.computer_use || {}) },
          proactive: { ...defaults.proactive, ...(rawCfg.proactive || {}) },
        },
        tags: data.tags || [],
      }
    }
  } catch {
    toast(tm('messages.loadFailed'), 'error')
  } finally {
    loading.value = false
  }
}

async function loadPrompts() {
  try {
    const [promptsRes, stagesRes] = await Promise.all([
      axios.get('/api/prompts', { params: { active_only: 'false' } }),
      axios.get('/api/prompts/stages'),
    ])
    if (promptsRes.data.status === 'ok') allPrompts.value = promptsRes.data.data
    if (stagesRes.data.status === 'ok') stages.value = stagesRes.data.data
  } catch {
    // silent
  }
}

async function loadPersonas() {
  try {
    const res = await axios.get('/api/persona/list')
    if (res.data.status === 'ok') allPersonas.value = res.data.data
  } catch {
    // silent
  }
}

async function loadTools() {
  try {
    const res = await axios.get('/api/tools/list')
    if (res.data.status === 'ok') allTools.value = res.data.data
  } catch {
    // silent
  }
}

async function loadSkills() {
  try {
    const res = await axios.get('/api/skills')
    if (res.data.status === 'ok') allSkills.value = res.data.data.skills || []
  } catch {
    // silent
  }
}

async function saveAgent() {
  const f = form.value
  if (!f.agent_id) { toast(tm('messages.idRequired'), 'error'); return }
  if (!f.name) { toast(tm('messages.nameRequired'), 'error'); return }

  try {
    const url = isNew.value ? '/api/agents' : `/api/agents/${f.agent_id}`
    const method = isNew.value ? 'post' : 'put'
    const res = await axios[method](url, f)
    if (res.data.status === 'ok') {
      toast(tm('messages.saveSuccess'))
      if (isNew.value) {
        router.replace(`/aar/agents/${f.agent_id}`)
      }
    } else {
      toast(res.data.message || tm('messages.saveFailed'), 'error')
    }
  } catch {
    toast(tm('messages.saveFailed'), 'error')
  }
}

// Tags
function addTag() {
  const val = tagInput.value.trim()
  if (val && !form.value.tags.includes(val)) {
    form.value.tags.push(val)
  }
  tagInput.value = ''
}

function removeTag(tag: string) {
  form.value.tags = form.value.tags.filter((t: string) => t !== tag)
}

// Prompt picker
function openPromptPicker() {
  promptPickerSelection.value = [...(form.value.prompts || [])]
  promptPickerOpen.value = true
}

function confirmPromptPicker() {
  form.value.prompts = [...promptPickerSelection.value]
  promptPickerOpen.value = false
}

function removePromptFromAgent(promptId: string) {
  form.value.prompts = form.value.prompts.filter((p: string) => p !== promptId)
}

function goBack() {
  router.push('/aar/agents')
}

onMounted(async () => {
  await Promise.all([loadPrompts(), loadPersonas(), loadTools(), loadSkills()])
  await loadAgent()
})
</script>

<template>
  <div class="dashboard-page aar-agent-editor-page" :class="{ 'is-dark': isDark }">
    <v-container fluid class="dashboard-shell pa-4 pa-md-6">
      <!-- Header -->
      <div class="dashboard-header">
        <div class="dashboard-header-main">
          <div class="dashboard-eyebrow">{{ tm('header.eyebrow') }}</div>
          <h1 class="dashboard-title">{{ isNew ? tm('editor.titleCreate') : tm('editor.titleEdit') }}</h1>
        </div>
        <div class="dashboard-header-actions">
          <v-btn variant="tonal" size="small" @click="goBack">
            <v-icon start>mdi-arrow-left</v-icon>{{ tm('actions.backToList') }}
          </v-btn>
          <v-btn color="primary" size="small" @click="saveAgent" :loading="loading">
            <v-icon start>mdi-content-save-outline</v-icon>{{ tm('actions.save') }}
          </v-btn>
        </div>
      </div>

      <div v-if="loading" style="text-align: center; padding: 60px">
        <v-progress-circular indeterminate size="40" />
      </div>

      <div v-else>
        <!-- Section: Basic Info -->
        <div class="dashboard-section-head">
          <div>
            <div class="dashboard-section-title">{{ tm('editor.basicInfo') }}</div>
          </div>
        </div>
        <div class="dashboard-card dashboard-card--padded mb-5">
          <div class="dashboard-form-grid mb-3">
            <v-text-field
              v-model="form.agent_id"
              :label="tm('editor.agentId')"
              :hint="tm('editor.agentIdHint')"
              persistent-hint
              density="compact"
              variant="outlined"
              :readonly="!isNew"
            />
            <v-text-field
              v-model="form.name"
              :label="tm('editor.name')"
              :hint="tm('editor.nameHint')"
              persistent-hint
              density="compact"
              variant="outlined"
            />
          </div>
          <!-- Tags -->
          <div class="mb-2" style="font-size: 13px; font-weight: 500; color: var(--dashboard-muted)">{{ tm('editor.tags') }}</div>
          <div style="display: flex; gap: 8px; flex-wrap: wrap; align-items: center; margin-bottom: 8px">
            <v-chip
              v-for="tag in form.tags"
              :key="tag"
              size="small"
              closable
              color="primary"
              variant="tonal"
              @click:close="removeTag(tag)"
            >{{ tag }}</v-chip>
            <v-text-field
              v-model="tagInput"
              :placeholder="tm('editor.tagsHint')"
              density="compact"
              variant="plain"
              hide-details
              style="max-width: 200px"
              @keydown.enter.prevent="addTag"
            />
          </div>
        </div>

        <!-- Section: Identity & Policy -->
        <div class="dashboard-section-head">
          <div>
            <div class="dashboard-section-title">{{ tm('editor.identityPolicy') }}</div>
          </div>
        </div>
        <div class="dashboard-card dashboard-card--padded mb-5">
          <div class="dashboard-form-grid mb-3">
            <div class="selector-wrap">
              <div class="selector-label">{{ tm('editor.persona') }}</div>
              <div class="selector-card">
                <DialogOptionSelector
                  v-model="form.persona_id"
                  :items="personaSelectorItems"
                  :title="tm('editor.selector.personaDialogTitle')"
                  :hint="tm('editor.personaHint')"
                  :button-text="tm('editor.selector.openButton')"
                  :search-placeholder="tm('editor.selector.searchPlaceholder')"
                  :not-selected-text="tm('editor.noPersona')"
                  :clear-text="tm('editor.selector.clearSelection')"
                  :empty-text="tm('editor.selector.empty')"
                  :confirm-text="tm('promptPicker.confirm')"
                  :cancel-text="tm('actions.cancel')"
                  clearable
                />
              </div>
            </div>

            <div class="selector-wrap">
              <div class="selector-label">{{ tm('editor.contextPolicy') }}</div>
              <div class="selector-card">
                <DialogOptionSelector
                  v-model="form.context_policy"
                  :items="contextPolicySelectorItems"
                  :title="tm('editor.selector.contextPolicyDialogTitle')"
                  :hint="tm('editor.contextPolicyHint')"
                  :button-text="tm('editor.selector.openButton')"
                  :search-placeholder="tm('editor.selector.searchPlaceholder')"
                  :not-selected-text="tm('editor.selector.notSelected')"
                  :empty-text="tm('editor.selector.empty')"
                  :confirm-text="tm('promptPicker.confirm')"
                  :cancel-text="tm('actions.cancel')"
                />
              </div>
            </div>
          </div>
        </div>

        <!-- Section: Abilities -->
        <div class="dashboard-section-head">
          <div>
            <div class="dashboard-section-title">{{ tm('editor.abilities') }}</div>
          </div>
        </div>
        <div class="dashboard-card dashboard-card--padded mb-5">
          <div class="dashboard-form-grid mb-3">
            <div class="selector-wrap">
              <div class="selector-label">{{ tm('editor.toolsLabel') }}</div>
              <div class="selector-card">
                <DialogOptionSelector
                  v-model="form.tools"
                  :items="toolSelectorItems"
                  :title="tm('editor.selector.toolsDialogTitle')"
                  :hint="tm('editor.toolsHint')"
                  :button-text="tm('editor.selector.openButton')"
                  :search-placeholder="tm('editor.selector.searchPlaceholder')"
                  :not-selected-text="tm('editor.selector.notSelected')"
                  :empty-text="tm('editor.selector.empty')"
                  :selected-count-template="tm('editor.selector.selectedCount')"
                  :confirm-text="tm('promptPicker.confirm')"
                  :cancel-text="tm('actions.cancel')"
                  multiple
                />
              </div>
            </div>

            <div class="selector-wrap">
              <div class="selector-label">{{ tm('editor.skillsLabel') }}</div>
              <div class="selector-card">
                <DialogOptionSelector
                  v-model="form.skills"
                  :items="skillSelectorItems"
                  :title="tm('editor.selector.skillsDialogTitle')"
                  :hint="tm('editor.skillsHint')"
                  :button-text="tm('editor.selector.openButton')"
                  :search-placeholder="tm('editor.selector.searchPlaceholder')"
                  :not-selected-text="tm('editor.selector.notSelected')"
                  :empty-text="tm('editor.selector.empty')"
                  :selected-count-template="tm('editor.selector.selectedCount')"
                  :confirm-text="tm('promptPicker.confirm')"
                  :cancel-text="tm('actions.cancel')"
                  multiple
                />
              </div>
            </div>
          </div>
        </div>

        <!-- Section: Capabilities -->
        <div class="dashboard-section-head">
          <div>
            <div class="dashboard-section-title">{{ tm('editor.capabilities') }}</div>
            <div class="dashboard-section-subtitle">{{ tm('editor.capabilitiesHint') }}</div>
          </div>
        </div>
        <v-expansion-panels variant="accordion" class="mb-5">

          <!-- Knowledge Base -->
          <v-expansion-panel>
            <v-expansion-panel-title>
              <div style="display: flex; align-items: center; gap: 10px">
                <v-icon size="18">mdi-database-outline</v-icon>
                <span>{{ tm('editor.cap.knowledgebase.title') }}</span>
                <v-chip v-if="form.config.knowledgebase.enabled" color="success" size="x-small" variant="tonal">{{ tm('editor.cap.enabled') }}</v-chip>
              </div>
            </v-expansion-panel-title>
            <v-expansion-panel-text>
              <v-switch
                v-model="form.config.knowledgebase.enabled"
                :label="tm('editor.cap.knowledgebase.enable')"
                :hint="tm('editor.cap.knowledgebase.enableHint')"
                persistent-hint
                density="compact"
                color="primary"
                class="mb-3"
              />
              <div v-if="form.config.knowledgebase.enabled">
                <v-combobox
                  v-model="form.config.knowledgebase.kb_names"
                  :label="tm('editor.cap.knowledgebase.names')"
                  :hint="tm('editor.cap.knowledgebase.namesHint')"
                  persistent-hint
                  density="compact"
                  variant="outlined"
                  multiple
                  chips
                  closable-chips
                  class="mb-3"
                />
                <div class="dashboard-form-grid mb-3">
                  <v-text-field
                    v-model.number="form.config.knowledgebase.fusion_top_k"
                    :label="tm('editor.cap.knowledgebase.fusionTopK')"
                    :hint="tm('editor.cap.knowledgebase.fusionTopKHint')"
                    persistent-hint
                    type="number"
                    density="compact"
                    variant="outlined"
                  />
                  <v-text-field
                    v-model.number="form.config.knowledgebase.final_top_k"
                    :label="tm('editor.cap.knowledgebase.finalTopK')"
                    :hint="tm('editor.cap.knowledgebase.finalTopKHint')"
                    persistent-hint
                    type="number"
                    density="compact"
                    variant="outlined"
                  />
                </div>
                <v-switch
                  v-model="form.config.knowledgebase.agentic_mode"
                  :label="tm('editor.cap.knowledgebase.agenticMode')"
                  :hint="tm('editor.cap.knowledgebase.agenticModeHint')"
                  persistent-hint
                  density="compact"
                  color="primary"
                />
              </div>
            </v-expansion-panel-text>
          </v-expansion-panel>

          <!-- Web Search -->
          <v-expansion-panel>
            <v-expansion-panel-title>
              <div style="display: flex; align-items: center; gap: 10px">
                <v-icon size="18">mdi-web</v-icon>
                <span>{{ tm('editor.cap.websearch.title') }}</span>
                <v-chip v-if="form.config.websearch.enabled" color="success" size="x-small" variant="tonal">{{ tm('editor.cap.enabled') }}</v-chip>
              </div>
            </v-expansion-panel-title>
            <v-expansion-panel-text>
              <v-switch
                v-model="form.config.websearch.enabled"
                :label="tm('editor.cap.websearch.enable')"
                :hint="tm('editor.cap.websearch.enableHint')"
                persistent-hint
                density="compact"
                color="primary"
                class="mb-3"
              />
              <div v-if="form.config.websearch.enabled">
                <div class="dashboard-form-grid mb-3">
                  <v-select
                    v-model="form.config.websearch.provider"
                    :label="tm('editor.cap.websearch.provider')"
                    :items="[
                      { title: 'Tavily', value: 'tavily' },
                      { title: 'BoCha', value: 'bocha' },
                      { title: 'Brave Search', value: 'brave' },
                      { title: tm('editor.cap.websearch.baiduProvider'), value: 'baidu_ai_search' },
                    ]"
                    density="compact"
                    variant="outlined"
                  />
                  <v-switch
                    v-model="form.config.websearch.show_link"
                    :label="tm('editor.cap.websearch.showLink')"
                    density="compact"
                    color="primary"
                  />
                </div>
                <v-combobox
                  v-if="form.config.websearch.provider === 'tavily'"
                  v-model="form.config.websearch.tavily_key"
                  :label="tm('editor.cap.websearch.tavilyKey')"
                  :hint="tm('editor.cap.websearch.keyHint')"
                  persistent-hint
                  density="compact"
                  variant="outlined"
                  multiple
                  chips
                  closable-chips
                  class="mb-3"
                />
                <v-combobox
                  v-if="form.config.websearch.provider === 'bocha'"
                  v-model="form.config.websearch.bocha_key"
                  :label="tm('editor.cap.websearch.bochaKey')"
                  :hint="tm('editor.cap.websearch.keyHint')"
                  persistent-hint
                  density="compact"
                  variant="outlined"
                  multiple
                  chips
                  closable-chips
                  class="mb-3"
                />
                <v-combobox
                  v-if="form.config.websearch.provider === 'brave'"
                  v-model="form.config.websearch.brave_key"
                  :label="tm('editor.cap.websearch.braveKey')"
                  :hint="tm('editor.cap.websearch.keyHint')"
                  persistent-hint
                  density="compact"
                  variant="outlined"
                  multiple
                  chips
                  closable-chips
                  class="mb-3"
                />
                <v-text-field
                  v-if="form.config.websearch.provider === 'baidu_ai_search'"
                  v-model="form.config.websearch.baidu_key"
                  :label="tm('editor.cap.websearch.baiduKey')"
                  density="compact"
                  variant="outlined"
                  class="mb-3"
                />
              </div>
            </v-expansion-panel-text>
          </v-expansion-panel>

          <!-- Computer Use -->
          <v-expansion-panel>
            <v-expansion-panel-title>
              <div style="display: flex; align-items: center; gap: 10px">
                <v-icon size="18">mdi-monitor</v-icon>
                <span>{{ tm('editor.cap.computerUse.title') }}</span>
                <v-chip v-if="form.config.computer_use.runtime !== 'none'" color="success" size="x-small" variant="tonal">{{ tm('editor.cap.enabled') }}</v-chip>
              </div>
            </v-expansion-panel-title>
            <v-expansion-panel-text>
              <div class="dashboard-form-grid mb-3">
                <v-select
                  v-model="form.config.computer_use.runtime"
                  :label="tm('editor.cap.computerUse.runtime')"
                  :hint="tm('editor.cap.computerUse.runtimeHint')"
                  persistent-hint
                  :items="[
                    { title: tm('editor.cap.computerUse.runtimeNone'), value: 'none' },
                    { title: tm('editor.cap.computerUse.runtimeLocal'), value: 'local' },
                    { title: tm('editor.cap.computerUse.runtimeSandbox'), value: 'sandbox' },
                  ]"
                  density="compact"
                  variant="outlined"
                />
                <v-switch
                  v-model="form.config.computer_use.require_admin"
                  :label="tm('editor.cap.computerUse.requireAdmin')"
                  :hint="tm('editor.cap.computerUse.requireAdminHint')"
                  persistent-hint
                  density="compact"
                  color="primary"
                />
              </div>
              <div v-if="form.config.computer_use.runtime === 'sandbox'">
                <v-select
                  v-model="form.config.computer_use.booter"
                  :label="tm('editor.cap.computerUse.booter')"
                  :items="[
                    { title: 'Shipyard Neo', value: 'shipyard_neo' },
                    { title: 'Shipyard', value: 'shipyard' },
                  ]"
                  density="compact"
                  variant="outlined"
                  class="mb-3"
                />
                <div v-if="form.config.computer_use.booter === 'shipyard_neo'" class="dashboard-form-grid mb-3">
                  <v-text-field
                    v-model="form.config.computer_use.neo_endpoint"
                    :label="tm('editor.cap.computerUse.neoEndpoint')"
                    :hint="tm('editor.cap.computerUse.neoEndpointHint')"
                    persistent-hint
                    density="compact"
                    variant="outlined"
                  />
                  <v-text-field
                    v-model="form.config.computer_use.neo_token"
                    :label="tm('editor.cap.computerUse.neoToken')"
                    :hint="tm('editor.cap.computerUse.neoTokenHint')"
                    persistent-hint
                    density="compact"
                    variant="outlined"
                    type="password"
                  />
                  <v-text-field
                    v-model="form.config.computer_use.neo_profile"
                    :label="tm('editor.cap.computerUse.neoProfile')"
                    :hint="tm('editor.cap.computerUse.neoProfileHint')"
                    persistent-hint
                    density="compact"
                    variant="outlined"
                  />
                  <v-text-field
                    v-model.number="form.config.computer_use.neo_ttl"
                    :label="tm('editor.cap.computerUse.neoTtl')"
                    :hint="tm('editor.cap.computerUse.neoTtlHint')"
                    persistent-hint
                    type="number"
                    density="compact"
                    variant="outlined"
                  />
                </div>
              </div>
            </v-expansion-panel-text>
          </v-expansion-panel>

          <!-- Proactive -->
          <v-expansion-panel>
            <v-expansion-panel-title>
              <div style="display: flex; align-items: center; gap: 10px">
                <v-icon size="18">mdi-clock-alert-outline</v-icon>
                <span>{{ tm('editor.cap.proactive.title') }}</span>
                <v-chip v-if="form.config.proactive.enabled" color="success" size="x-small" variant="tonal">{{ tm('editor.cap.enabled') }}</v-chip>
              </div>
            </v-expansion-panel-title>
            <v-expansion-panel-text>
              <v-switch
                v-model="form.config.proactive.enabled"
                :label="tm('editor.cap.proactive.enable')"
                :hint="tm('editor.cap.proactive.enableHint')"
                persistent-hint
                density="compact"
                color="primary"
              />
            </v-expansion-panel-text>
          </v-expansion-panel>

        </v-expansion-panels>

        <!-- Section: Prompt Orchestration -->
        <div class="dashboard-section-head">
          <div>
            <div class="dashboard-section-title">{{ tm('editor.promptOrchestration') }}</div>
            <div class="dashboard-section-subtitle">{{ tm('editor.promptOrchestrationHint') }}</div>
          </div>
          <div class="dashboard-section-actions">
            <v-btn variant="tonal" size="small" @click="openPromptPicker">
              <v-icon start>mdi-plus</v-icon>{{ tm('actions.addPrompt') }}
            </v-btn>
          </div>
        </div>
        <div class="dashboard-card dashboard-card--padded mb-5">
          <div v-if="!form.prompts || form.prompts.length === 0" class="dashboard-empty" style="text-align: center; padding: 30px 0">
            {{ tm('editor.noPrompts') }}
          </div>
          <div v-else>
            <div v-for="stage in stages" :key="stage.id" class="mb-4">
              <div v-if="promptsByStage[stage.id] && promptsByStage[stage.id].length > 0">
                <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 10px">
                  <v-chip :color="categoryColors[stage.id] || 'grey'" size="small" label>
                    {{ stage.order }}. {{ stage.name }}
                  </v-chip>
                  <span style="font-size: 12px; color: var(--dashboard-muted)">{{ stage.description }}</span>
                </div>
                <div class="dashboard-list">
                  <div
                    v-for="p in promptsByStage[stage.id]"
                    :key="p.prompt_id"
                    class="dashboard-list-row"
                  >
                    <div style="min-width: 0">
                      <div class="dashboard-list-label">
                        <strong style="font-family: monospace; font-size: 13px">{{ p.prompt_id }}</strong>
                        <span style="margin-left: 8px; color: var(--dashboard-muted)">{{ p.name }}</span>
                      </div>
                    </div>
                    <div style="display: flex; align-items: center; gap: 8px">
                      <v-chip size="x-small" variant="tonal" color="primary">P{{ p.priority }}</v-chip>
                      <v-btn icon size="x-small" variant="text" color="error" @click="removePromptFromAgent(p.prompt_id)">
                        <v-icon size="14">mdi-close</v-icon>
                      </v-btn>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Section: Advanced Config JSON -->
        <div class="dashboard-section-head">
          <div>
            <div class="dashboard-section-title">{{ tm('editor.configJson') }}</div>
            <div class="dashboard-section-subtitle">{{ tm('editor.configJsonHint') }}</div>
          </div>
        </div>
        <div class="dashboard-card dashboard-card--padded mb-5">
          <v-textarea
            :model-value="JSON.stringify(form.config || {}, null, 2)"
            @update:model-value="(v: string) => { try { form.config = JSON.parse(v) } catch {} }"
            variant="outlined"
            density="compact"
            rows="5"
            auto-grow
            style="font-family: monospace; font-size: 13px"
          />
        </div>
      </div>

      <!-- Prompt Picker Dialog -->
      <v-dialog v-model="promptPickerOpen" max-width="680" scrollable>
        <v-card class="dashboard-dialog-card">
          <v-card-title class="pa-4">
            <div style="font-size: 18px; font-weight: 600">{{ tm('promptPicker.title') }}</div>
            <div style="font-size: 13px; color: var(--dashboard-muted); margin-top: 4px">{{ tm('promptPicker.subtitle') }}</div>
          </v-card-title>
          <v-divider />
          <v-card-text style="max-height: 400px; overflow-y: auto; padding: 16px">
            <div v-for="stage in stages" :key="stage.id" class="mb-3">
              <div style="font-weight: 600; font-size: 13px; margin-bottom: 6px">
                <v-chip :color="categoryColors[stage.id] || 'grey'" size="x-small" label class="mr-2">{{ stage.order }}</v-chip>
                {{ stage.name }}
              </div>
              <div
                v-for="p in allPrompts.filter((x: any) => x.category === stage.id)"
                :key="p.prompt_id"
                style="display: flex; align-items: center; gap: 8px; padding: 6px 0"
              >
                <v-checkbox
                  :model-value="promptPickerSelection.includes(p.prompt_id)"
                  @update:model-value="(v: boolean | null) => {
                    if (v) promptPickerSelection.push(p.prompt_id)
                    else promptPickerSelection = promptPickerSelection.filter(id => id !== p.prompt_id)
                  }"
                  density="compact"
                  hide-details
                />
                <div style="min-width: 0; flex: 1">
                  <div style="font-family: monospace; font-size: 13px; font-weight: 500">{{ p.prompt_id }}</div>
                  <div style="font-size: 12px; color: var(--dashboard-muted)">{{ p.name }}</div>
                </div>
                <v-chip size="x-small" variant="tonal">P{{ p.priority }}</v-chip>
                <v-chip size="x-small" :color="p.is_active ? 'success' : 'grey'" variant="tonal">
                  {{ p.is_active ? 'Active' : 'Inactive' }}
                </v-chip>
              </div>
              <div
                v-if="allPrompts.filter((x: any) => x.category === stage.id).length === 0"
                style="font-size: 12px; color: var(--dashboard-subtle); padding: 6px 0"
              >
                {{ tm('editor.stageEmpty') }}
              </div>
            </div>
          </v-card-text>
          <v-divider />
          <v-card-actions class="pa-3">
            <span style="font-size: 13px; color: var(--dashboard-muted)">
              {{ tm('promptPicker.selected').replace('{count}', String(promptPickerSelection.length)) }}
            </span>
            <v-spacer />
            <v-btn variant="text" @click="promptPickerOpen = false">{{ tm('actions.cancel') }}</v-btn>
            <v-btn color="primary" @click="confirmPromptPicker">{{ tm('promptPicker.confirm') }}</v-btn>
          </v-card-actions>
        </v-card>
      </v-dialog>

      <!-- Snackbar -->
      <v-snackbar v-model="snackbar.show" :color="snackbar.color" :timeout="3000" location="bottom right">
        {{ snackbar.text }}
      </v-snackbar>
    </v-container>
  </div>
</template>

<style scoped>
.selector-wrap {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.selector-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--dashboard-muted);
}

.selector-card {
  border: 1px solid rgba(var(--v-border-color), 0.3);
  border-radius: 10px;
  padding: 10px 12px;
  background: rgba(var(--v-theme-surface), 0.8);
}
</style>
