<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useTheme } from 'vuetify'
import axios from 'axios'
import { useModuleI18n } from '@/i18n/composables'
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
  config: {},
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
const personaOptions = computed(() => [
  { title: tm('editor.noPersona') || '(None)', value: null },
  ...allPersonas.value.map((p: any) => ({ title: p.persona_id, value: p.persona_id })),
])

// Tools transfer state
const allTools = ref<any[]>([])
const toolSearch = ref('')
const toolSelectedSearch = ref('')
const toolLeftChecked = ref<string[]>([])
const toolRightChecked = ref<string[]>([])

const availableToolItems = computed(() =>
  allTools.value
    .filter((t: any) => !(form.value.tools || []).includes(t.name))
    .filter((t: any) => !toolSearch.value || t.name.toLowerCase().includes(toolSearch.value.toLowerCase()) || (t.description || '').toLowerCase().includes(toolSearch.value.toLowerCase()))
)
const selectedToolItems = computed(() =>
  (form.value.tools || [])
    .map((name: string) => allTools.value.find((t: any) => t.name === name) || { name, description: '', origin_name: '' })
    .filter((t: any) => !toolSelectedSearch.value || t.name.toLowerCase().includes(toolSelectedSearch.value.toLowerCase()))
)

function moveToolsToSelected() {
  for (const name of toolLeftChecked.value) {
    if (!form.value.tools.includes(name)) form.value.tools.push(name)
  }
  toolLeftChecked.value = []
}
function moveToolsToAvailable() {
  form.value.tools = (form.value.tools || []).filter((n: string) => !toolRightChecked.value.includes(n))
  toolRightChecked.value = []
}

// Skills transfer state
const allSkills = ref<any[]>([])
const skillSearch = ref('')
const skillSelectedSearch = ref('')
const skillLeftChecked = ref<string[]>([])
const skillRightChecked = ref<string[]>([])

const availableSkillItems = computed(() =>
  allSkills.value
    .filter((s: any) => !(form.value.skills || []).includes(s.name))
    .filter((s: any) => !skillSearch.value || s.name.toLowerCase().includes(skillSearch.value.toLowerCase()))
)
const selectedSkillItems = computed(() =>
  (form.value.skills || [])
    .map((name: string) => allSkills.value.find((s: any) => s.name === name) || { name, description: '' })
    .filter((s: any) => !skillSelectedSearch.value || s.name.toLowerCase().includes(skillSelectedSearch.value.toLowerCase()))
)

function moveSkillsToSelected() {
  for (const name of skillLeftChecked.value) {
    if (!form.value.skills.includes(name)) form.value.skills.push(name)
  }
  skillLeftChecked.value = []
}
function moveSkillsToAvailable() {
  form.value.skills = (form.value.skills || []).filter((n: string) => !skillRightChecked.value.includes(n))
  skillRightChecked.value = []
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

// --- API ---
async function loadAgent() {
  if (isNew.value) return
  loading.value = true
  try {
    const res = await axios.get(`/api/agents/${currentAgentId.value}`)
    if (res.data.status === 'ok') {
      const data = res.data.data
      form.value = {
        agent_id: data.agent_id || '',
        name: data.name || '',
        persona_id: data.persona_id || null,
        prompts: data.prompts || [],
        tools: data.tools || [],
        skills: data.skills || [],
        context_policy: data.context_policy || 'sys.batch_eviction',
        interceptors: data.interceptors || [],
        config: data.config || {},
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
            <v-autocomplete
              v-model="form.persona_id"
              :label="tm('editor.persona')"
              :hint="tm('editor.personaHint')"
              :items="personaOptions"
              persistent-hint
              density="compact"
              variant="outlined"
              clearable
              item-title="title"
              item-value="value"
            />
            <v-select
              v-model="form.context_policy"
              :label="tm('editor.contextPolicy')"
              :items="policyOptions"
              :hint="tm('editor.contextPolicyHint')"
              persistent-hint
              density="compact"
              variant="outlined"
            />
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
            <!-- Tools Select -->
            <v-autocomplete
              v-model="form.tools"
              :items="allTools"
              item-title="name"
              item-value="name"
              multiple
              chips
              closable-chips
              clearable
              variant="outlined"
              density="compact"
              :label="tm('editor.toolsLabel')"
              :hint="tm('editor.toolsHint')"
              persistent-hint
            >
              <template v-slot:item="{ props, item }">
                <v-list-item v-bind="props" :subtitle="item.raw.description"></v-list-item>
              </template>
            </v-autocomplete>

            <!-- Skills Select -->
            <v-autocomplete
              v-model="form.skills"
              :items="allSkills"
              item-title="name"
              item-value="name"
              multiple
              chips
              closable-chips
              clearable
              variant="outlined"
              density="compact"
              :label="tm('editor.skillsLabel')"
              :hint="tm('editor.skillsHint')"
              persistent-hint
            ></v-autocomplete>
          </div>
        </div>

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
.transfer-box {
  display: flex;
  gap: 12px;
  align-items: flex-start;
}

.transfer-panel {
  flex: 1;
  border: 1px solid rgba(128, 128, 128, 0.2);
  border-radius: 8px;
  padding: 12px;
  min-height: 200px;
  max-height: 280px;
  display: flex;
  flex-direction: column;
}

.transfer-panel-header {
  font-size: 12px;
  font-weight: 600;
  color: var(--dashboard-muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 8px;
}

.transfer-list {
  flex: 1;
  overflow-y: auto;
}

.transfer-item {
  padding: 2px 0;
}

.transfer-actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
  justify-content: center;
  padding-top: 44px;
}
</style>
