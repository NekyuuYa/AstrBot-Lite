<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useTheme } from 'vuetify'
import axios from 'axios'
import { useModuleI18n } from '@/i18n/composables'
import '@/styles/dashboard-shell.css'

const theme = useTheme()
const isDark = computed(() => theme.global.current.value.dark)
const { tm } = useModuleI18n('features/aar-agents')
const router = useRouter()

// --- State ---
const agents = ref<any[]>([])
const loading = ref(false)
const search = ref('')
const filterTag = ref('')

// Snackbar
const snackbar = ref({ show: false, text: '', color: 'success' })
function toast(text: string, color = 'success') {
  snackbar.value = { show: true, text, color }
}

// --- Computed ---
const allTags = computed(() => {
  const tags = new Set<string>()
  agents.value.forEach((a: any) => {
    if (a.tags && Array.isArray(a.tags)) {
      a.tags.forEach((t: string) => tags.add(t))
    }
  })
  return Array.from(tags).sort()
})

const filteredAgents = computed(() => {
  let list = agents.value
  if (filterTag.value) {
    list = list.filter((a: any) => a.tags && a.tags.includes(filterTag.value))
  }
  if (search.value) {
    const q = search.value.toLowerCase()
    list = list.filter(
      (a: any) =>
        a.agent_id.toLowerCase().includes(q) ||
        a.name.toLowerCase().includes(q)
    )
  }
  return list
})

const overviewStats = computed(() => {
  const total = agents.value.length
  const withPersona = agents.value.filter((a: any) => a.persona_id).length
  const withTools = agents.value.filter((a: any) => a.tools && a.tools.length > 0).length
  const withPrompts = agents.value.filter((a: any) => a.prompts && a.prompts.length > 0).length
  return { total, withPersona, withTools, withPrompts }
})

// --- API ---
async function loadAgents() {
  loading.value = true
  try {
    const res = await axios.get('/api/agents')
    if (res.data.status === 'ok') agents.value = res.data.data
  } catch {
    toast(tm('messages.loadFailed'), 'error')
  } finally {
    loading.value = false
  }
}

async function deleteAgent(agentId: string) {
  if (!confirm(tm('messages.deleteConfirm').replace('{id}', agentId))) return
  try {
    const res = await axios.delete(`/api/agents/${agentId}`)
    if (res.data.status === 'ok') {
      toast(tm('messages.deleteSuccess'))
      await loadAgents()
    } else {
      toast(res.data.message || tm('messages.deleteFailed'), 'error')
    }
  } catch {
    toast(tm('messages.deleteFailed'), 'error')
  }
}

function editAgent(agentId: string) {
  router.push(`/aar/agents/${agentId}`)
}

function createAgent() {
  router.push('/aar/agents/__new__')
}

function isDefault(agent: any) {
  return agent.agent_id === 'sys.default'
}

onMounted(loadAgents)
</script>

<template>
  <div class="dashboard-page aar-agents-page" :class="{ 'is-dark': isDark }">
    <v-container fluid class="dashboard-shell pa-4 pa-md-6">
      <!-- Header -->
      <div class="dashboard-header">
        <div class="dashboard-header-main">
          <div class="dashboard-eyebrow">{{ tm('header.eyebrow') }}</div>
          <h1 class="dashboard-title">{{ tm('page.title') }}</h1>
          <p class="dashboard-subtitle">{{ tm('page.subtitle') }}</p>
        </div>
        <div class="dashboard-header-actions">
          <v-btn variant="tonal" size="small" @click="loadAgents" :loading="loading">
            <v-icon start>mdi-refresh</v-icon>{{ tm('actions.create').replace(tm('actions.create'), '') }}
          </v-btn>
          <v-btn color="primary" size="small" @click="createAgent">
            <v-icon start>mdi-plus</v-icon>{{ tm('actions.create') }}
          </v-btn>
        </div>
      </div>

      <!-- Overview Cards -->
      <div class="dashboard-overview-grid mb-5">
        <div class="dashboard-card dashboard-overview-card">
          <div class="dashboard-card-icon"><v-icon size="18">mdi-robot-outline</v-icon></div>
          <div class="dashboard-card-label">{{ tm('overview.total') }}</div>
          <div class="dashboard-card-value">{{ overviewStats.total }}</div>
          <div class="dashboard-card-note">{{ tm('overview.totalNote') }}</div>
        </div>
        <div class="dashboard-card dashboard-overview-card">
          <div class="dashboard-card-icon"><v-icon size="18">mdi-heart-outline</v-icon></div>
          <div class="dashboard-card-label">{{ tm('overview.withPersona') }}</div>
          <div class="dashboard-card-value">{{ overviewStats.withPersona }}</div>
          <div class="dashboard-card-note">{{ tm('overview.withPersonaNote') }}</div>
        </div>
        <div class="dashboard-card dashboard-overview-card">
          <div class="dashboard-card-icon"><v-icon size="18">mdi-wrench-outline</v-icon></div>
          <div class="dashboard-card-label">{{ tm('overview.withTools') }}</div>
          <div class="dashboard-card-value">{{ overviewStats.withTools }}</div>
          <div class="dashboard-card-note">{{ tm('overview.withToolsNote') }}</div>
        </div>
        <div class="dashboard-card dashboard-overview-card">
          <div class="dashboard-card-icon"><v-icon size="18">mdi-script-text-outline</v-icon></div>
          <div class="dashboard-card-label">{{ tm('overview.withPrompts') }}</div>
          <div class="dashboard-card-value">{{ overviewStats.withPrompts }}</div>
          <div class="dashboard-card-note">{{ tm('overview.withPromptsNote') }}</div>
        </div>
      </div>

      <!-- Filters -->
      <div style="display: flex; gap: 12px; flex-wrap: wrap; align-items: center; margin-bottom: 20px">
        <v-text-field
          v-model="search"
          :placeholder="tm('filters.search')"
          prepend-inner-icon="mdi-magnify"
          density="compact"
          variant="outlined"
          hide-details
          clearable
          style="max-width: 280px"
        />
        <v-select
          v-if="allTags.length > 0"
          v-model="filterTag"
          :items="[{ title: tm('filters.allTags'), value: '' }, ...allTags.map(t => ({ title: t, value: t }))]"
          density="compact"
          variant="outlined"
          hide-details
          style="max-width: 180px"
        />
      </div>

      <!-- Empty State -->
      <div v-if="!loading && filteredAgents.length === 0" class="dashboard-card dashboard-card--padded" style="text-align: center; padding: 60px 20px">
        <v-icon size="48" color="grey-lighten-1" class="mb-3">mdi-robot-off-outline</v-icon>
        <h3 style="font-size: 18px; font-weight: 600; margin-bottom: 8px">{{ tm('empty.title') }}</h3>
        <p class="dashboard-empty mb-4">{{ tm('empty.subtitle') }}</p>
        <v-btn color="primary" @click="createAgent">
          <v-icon start>mdi-plus</v-icon>{{ tm('empty.action') }}
        </v-btn>
      </div>

      <!-- Loading -->
      <div v-else-if="loading" style="text-align: center; padding: 60px">
        <v-progress-circular indeterminate size="40" />
      </div>

      <!-- Agent Card Grid -->
      <div v-else class="agent-card-grid">
        <div
          v-for="agent in filteredAgents"
          :key="agent.agent_id"
          class="dashboard-card dashboard-card--padded agent-card"
          @click="editAgent(agent.agent_id)"
        >
          <!-- Card Header -->
          <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 14px">
            <div style="min-width: 0">
              <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap">
                <h3 style="font-size: 16px; font-weight: 600; margin: 0">{{ agent.name }}</h3>
                <v-chip v-if="isDefault(agent)" size="x-small" color="primary" variant="flat">
                  {{ tm('card.defaultBadge') }}
                </v-chip>
              </div>
              <div style="font-size: 12px; color: var(--dashboard-muted); font-family: monospace; margin-top: 4px">
                {{ agent.agent_id }}
              </div>
            </div>
            <div style="display: flex; gap: 4px" @click.stop>
              <v-btn icon size="x-small" variant="text" @click="editAgent(agent.agent_id)">
                <v-icon size="16">mdi-pencil-outline</v-icon>
              </v-btn>
              <v-btn
                v-if="!isDefault(agent)"
                icon size="x-small" variant="text" color="error"
                @click="deleteAgent(agent.agent_id)"
              >
                <v-icon size="16">mdi-delete-outline</v-icon>
              </v-btn>
            </div>
          </div>

          <!-- Tags -->
          <div v-if="agent.tags && agent.tags.length" style="display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 14px">
            <v-chip v-for="tag in agent.tags" :key="tag" size="x-small" variant="tonal" color="primary">
              {{ tag }}
            </v-chip>
          </div>
          <div v-else style="font-size: 12px; color: var(--dashboard-subtle); margin-bottom: 14px">
            {{ tm('card.noTags') }}
          </div>

          <!-- Capabilities Preview -->
          <div class="dashboard-meta-list" style="margin-top: 0; padding-top: 0; border-top: none">
            <div class="dashboard-meta-row">
              <span>{{ tm('card.persona') }}</span>
              <span style="font-weight: 500; color: var(--dashboard-text)">
                {{ agent.persona_id || tm('card.nonePersona') }}
              </span>
            </div>
            <div class="dashboard-meta-row">
              <span>{{ tm('card.tools') }}</span>
              <v-chip size="x-small" variant="tonal">{{ agent.tools ? agent.tools.length : 0 }}</v-chip>
            </div>
            <div class="dashboard-meta-row">
              <span>{{ tm('card.prompts') }}</span>
              <v-chip size="x-small" variant="tonal">{{ agent.prompts ? agent.prompts.length : 0 }}</v-chip>
            </div>
            <div class="dashboard-meta-row">
              <span>{{ tm('card.policy') }}</span>
              <span style="font-size: 12px; font-family: monospace">{{ agent.context_policy }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Snackbar -->
      <v-snackbar v-model="snackbar.show" :color="snackbar.color" :timeout="3000" location="bottom right">
        {{ snackbar.text }}
      </v-snackbar>
    </v-container>
  </div>
</template>

<style scoped>
.agent-card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  gap: 16px;
}

.agent-card {
  cursor: pointer;
  transition: border-color 0.15s, box-shadow 0.15s;
}

.agent-card:hover {
  border-color: rgb(var(--v-theme-primary));
  box-shadow: 0 0 0 1px rgba(var(--v-theme-primary), 0.2);
}
</style>
