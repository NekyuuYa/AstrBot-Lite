<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useTheme } from 'vuetify'
import axios from 'axios'

import { useModuleI18n } from '@/i18n/composables'
import AgentEditorPage from '@/views/aar/AgentEditorPage.vue'
import '@/styles/dashboard-shell.css'

const theme = useTheme()
const isDark = computed(() => theme.global.current.value.dark)
const { tm } = useModuleI18n('features/aar-agents')
const route = useRoute()
const router = useRouter()

const agents = ref<any[]>([])
const loading = ref(false)
const search = ref('')
const filterTag = ref('')
const selectedAgentId = ref<string>('__new__')

const snackbar = ref({ show: false, text: '', color: 'success' })
function toast(text: string, color = 'success') {
  snackbar.value = { show: true, text, color }
}

const allTags = computed(() => {
  const tags = new Set<string>()
  agents.value.forEach((a: any) => {
    if (Array.isArray(a.tags)) {
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

function syncRouteBySelection(agentId: string) {
  // Removed to make this a fixed page
}

function pickInitialSelection() {
  if (agents.value.length > 0) {
    selectedAgentId.value = agents.value[0].agent_id
  } else {
    selectedAgentId.value = '__new__'
  }
}

async function loadAgents() {
  loading.value = true
  try {
    const res = await axios.get('/api/agents')
    if (res.data.status === 'ok') {
      agents.value = res.data.data
      const hasSelected = agents.value.some(
        (a: any) => a.agent_id === selectedAgentId.value
      )
      if (selectedAgentId.value !== '__new__' && !hasSelected) {
        pickInitialSelection()
      }
    }
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
      if (selectedAgentId.value === agentId) {
        selectedAgentId.value = '__new__'
      }
      await loadAgents()
    } else {
      toast(res.data.message || tm('messages.deleteFailed'), 'error')
    }
  } catch {
    toast(tm('messages.deleteFailed'), 'error')
  }
}

const editorRef = ref<any>(null)

function selectAgent(agentId: string) {
  if (selectedAgentId.value === agentId) return
  if (editorRef.value?.isDirty) {
    if (!confirm(tm('messages.discardConfirm') || '当前修改未保存，确定要离开吗？')) return
  }
  selectedAgentId.value = agentId
}

function createAgent() {
  if (selectedAgentId.value === '__new__') return
  if (editorRef.value?.isDirty) {
    if (!confirm(tm('messages.discardConfirm') || '当前修改未保存，确定要离开吗？')) return
  }
  selectedAgentId.value = '__new__'
}

async function onEditorSaved(agentId: string) {
  selectedAgentId.value = agentId
  await loadAgents()
}

onMounted(async () => {
  await loadAgents()
  pickInitialSelection()
})
</script>

<template>
  <div class="dashboard-page aar-agents-page" :class="{ 'is-dark': isDark }">
    <v-container fluid class="dashboard-shell pa-4 pa-md-6">
      <div class="dashboard-header">
        <div class="dashboard-header-main">
        <div class="dashboard-eyebrow">{{ tm('eyebrow') || 'AAR Agent Hub' }}</div>
        <h1 class="dashboard-title">{{ tm('page.title') }}</h1>          <p class="dashboard-subtitle">{{ tm('page.subtitle') }}</p>
        </div>
      </div>

      <v-row class="agent-workbench ma-n2">
        <!-- 左侧 Agent 列表 -->
        <v-col cols="12" md="4" lg="3" class="pa-2">
          <v-card class="dashboard-card h-100 d-flex flex-column" elevation="0">
            <div class="sidebar-header pa-4 pb-2">
              <div class="d-flex align-center justify-space-between mb-4">
                <div class="d-flex align-center">
                  <div class="dashboard-section-title mr-2">{{ tm('page.title') }}</div>
                  <v-chip size="x-small" variant="tonal" label color="primary">
                    {{ agents.length }}
                  </v-chip>
                </div>
                <v-btn color="primary" variant="tonal" size="small" rounded="xl" prepend-icon="mdi-plus" @click="createAgent">
                  {{ tm('actions.create') }}
                </v-btn>
              </div>
              
              <v-text-field
                v-model="search"
                :placeholder="tm('filters.search')"
                prepend-inner-icon="mdi-magnify"
                density="compact"
                variant="solo-filled"
                flat
                hide-details
                clearable
                rounded="xl"
                class="mb-3"
              />

              <v-select
                v-if="allTags.length > 0"
                v-model="filterTag"
                :items="[
                  { title: tm('filters.allTags'), value: '' },
                  ...allTags.map((t) => ({ title: t, value: t })),
                ]"
                density="compact"
                variant="solo-filled"
                flat
                hide-details
                rounded="xl"
              />
            </div>

            <v-divider></v-divider>

            <v-list class="agent-list pa-2 flex-grow-1" nav density="compact" lines="two">
              <v-list-item
                v-for="agent in filteredAgents"
                :key="agent.agent_id"
                class="mb-1"
                :active="selectedAgentId === agent.agent_id"
                color="primary"
                rounded="lg"
                @click="selectAgent(agent.agent_id)"
              >
                <template #prepend>
                  <v-avatar size="32" color="secondary" variant="tonal">
                    <v-icon size="20">mdi-robot</v-icon>
                  </v-avatar>
                </template>
                
                <v-list-item-title class="font-weight-bold">{{ agent.name }}</v-list-item-title>
                <v-list-item-subtitle class="text-caption text-mono">{{ agent.agent_id }}</v-list-item-subtitle>

                <template #append>
                  <v-btn
                    v-if="agent.agent_id !== 'sys.default'"
                    icon="mdi-delete-outline"
                    variant="text"
                    size="x-small"
                    color="error"
                    @click.stop="deleteAgent(agent.agent_id)"
                  ></v-btn>
                </template>
              </v-list-item>
            </v-list>

            <div v-if="loading" class="d-flex justify-center pa-8">
              <v-progress-circular indeterminate color="primary" />
            </div>
          </v-card>
        </v-col>

        <!-- 右侧 编辑器 -->
        <v-col cols="12" md="8" lg="9" class="pa-2">
          <v-card class="dashboard-card h-100 overflow-auto" elevation="0">
            <AgentEditorPage
              ref="editorRef"
              embedded
              :agent-id="selectedAgentId"
              @saved="onEditorSaved"
            />
          </v-card>
        </v-col>
      </v-row>

      <v-snackbar
        v-model="snackbar.show"
        :color="snackbar.color"
        :timeout="3000"
        location="bottom right"
        rounded="xl"
      >
        {{ snackbar.text }}
      </v-snackbar>
    </v-container>
  </div>
</template>

<style scoped>
.agent-workbench {
  min-height: calc(100vh - 180px);
}

.text-mono {
  font-family: monospace;
}

.agent-list {
  max-height: calc(100vh - 380px);
  overflow-y: auto;
}

@media (max-width: 960px) {
  .agent-workbench {
    flex-direction: column;
  }
}
</style>
