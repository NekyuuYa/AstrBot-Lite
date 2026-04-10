<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useTheme } from 'vuetify'
import axios from 'axios'
import { useModuleI18n } from '@/i18n/composables'
import '@/styles/dashboard-shell.css'

const theme = useTheme()
const isDark = computed(() => theme.global.current.value.dark)
const { tm } = useModuleI18n('features/aar-prompts')

// --- State ---
const prompts = ref<any[]>([])
const stages = ref<any[]>([])
const loading = ref(false)
const search = ref('')
const filterCategory = ref('')
const filterSource = ref('')
const filterType = ref('')

// Editor state
const editorOpen = ref(false)
const editorMode = ref<'create' | 'edit'>('create')
const editForm = ref<any>({
  prompt_id: '',
  name: '',
  category: '',
  priority: 50,
  type: 'static',
  content: '',
  source: 'user',
  is_active: true,
})

// Snackbar
const snackbar = ref({ show: false, text: '', color: 'success' })
function toast(text: string, color = 'success') {
  snackbar.value = { show: true, text, color }
}

// --- Computed ---
const categoryColors: Record<string, string> = {
  SystemBase: 'blue',
  Identity: 'purple',
  Context: 'teal',
  Abilities: 'orange',
  Instruction: 'indigo',
  Constraint: 'red',
  Refinement: 'grey',
}

const uniqueSources = computed(() => {
  const s = new Set(prompts.value.map((p: any) => p.source))
  return Array.from(s).sort()
})

const filteredPrompts = computed(() => {
  let list = prompts.value
  if (filterCategory.value) {
    list = list.filter((p: any) => p.category === filterCategory.value)
  }
  if (filterSource.value) {
    list = list.filter((p: any) => p.source === filterSource.value)
  }
  if (filterType.value) {
    list = list.filter((p: any) => p.type === filterType.value)
  }
  if (search.value) {
    const q = search.value.toLowerCase()
    list = list.filter(
      (p: any) =>
        p.prompt_id.toLowerCase().includes(q) ||
        p.name.toLowerCase().includes(q)
    )
  }
  return list
})

// Overview stats
const overviewStats = computed(() => {
  const total = prompts.value.length
  const active = prompts.value.filter((p: any) => p.is_active).length
  const coveredStages = new Set(prompts.value.filter((p: any) => p.is_active && p.content).map((p: any) => p.category)).size
  const legacy = prompts.value.filter((p: any) => p.source && p.source.startsWith('legacy.')).length
  return { total, active, coveredStages, legacy }
})

// --- API ---
async function loadPrompts() {
  loading.value = true
  try {
    const [promptsRes, stagesRes] = await Promise.all([
      axios.get('/api/prompts', { params: { active_only: 'false' } }),
      axios.get('/api/prompts/stages'),
    ])
    if (promptsRes.data.status === 'ok') prompts.value = promptsRes.data.data
    if (stagesRes.data.status === 'ok') stages.value = stagesRes.data.data
  } catch {
    toast(tm('messages.loadFailed'), 'error')
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editorMode.value = 'create'
  editForm.value = {
    prompt_id: '',
    name: '',
    category: '',
    priority: 50,
    type: 'static',
    content: '',
    source: 'user',
    is_active: true,
  }
  editorOpen.value = true
}

function openEdit(item: any) {
  editorMode.value = 'edit'
  editForm.value = { ...item }
  editorOpen.value = true
}

async function savePrompt() {
  const f = editForm.value
  if (!f.prompt_id) { toast(tm('messages.idRequired'), 'error'); return }
  if (!f.name) { toast(tm('messages.nameRequired'), 'error'); return }
  if (!f.category) { toast(tm('messages.categoryRequired'), 'error'); return }

  try {
    const url = editorMode.value === 'create' ? '/api/prompts' : `/api/prompts/${f.prompt_id}`
    const method = editorMode.value === 'create' ? 'post' : 'put'
    const res = await axios[method](url, f)
    if (res.data.status === 'ok') {
      toast(tm('messages.saveSuccess'))
      editorOpen.value = false
      await loadPrompts()
    } else {
      toast(res.data.message || tm('messages.saveFailed'), 'error')
    }
  } catch {
    toast(tm('messages.saveFailed'), 'error')
  }
}

async function deletePrompt(promptId: string) {
  if (!confirm(tm('messages.deleteConfirm').replace('{id}', promptId))) return
  try {
    const res = await axios.delete(`/api/prompts/${promptId}`)
    if (res.data.status === 'ok') {
      toast(tm('messages.deleteSuccess'))
      await loadPrompts()
    } else {
      toast(res.data.message || tm('messages.deleteFailed'), 'error')
    }
  } catch {
    toast(tm('messages.deleteFailed'), 'error')
  }
}

async function toggleActive(item: any) {
  try {
    await axios.put(`/api/prompts/${item.prompt_id}`, {
      ...item,
      is_active: !item.is_active,
    })
    await loadPrompts()
  } catch {
    toast(tm('messages.saveFailed'), 'error')
  }
}

function isSystemEntry(item: any) {
  return item.source?.startsWith('system') || item.source?.startsWith('legacy.')
}

onMounted(loadPrompts)
</script>

<template>
  <div class="dashboard-page aar-prompts-page" :class="{ 'is-dark': isDark }">
    <v-container fluid class="dashboard-shell pa-4 pa-md-6">
      <!-- Header -->
      <div class="dashboard-header">
        <div class="dashboard-header-main">
          <div class="dashboard-eyebrow">{{ tm('header.eyebrow') }}</div>
          <h1 class="dashboard-title">{{ tm('page.title') }}</h1>
          <p class="dashboard-subtitle">{{ tm('page.subtitle') }}</p>
        </div>
        <div class="dashboard-header-actions">
          <v-btn variant="tonal" size="small" @click="loadPrompts" :loading="loading">
            <v-icon start>mdi-refresh</v-icon>{{ tm('actions.refresh') }}
          </v-btn>
          <v-btn color="primary" size="small" @click="openCreate">
            <v-icon start>mdi-plus</v-icon>{{ tm('actions.create') }}
          </v-btn>
        </div>
      </div>

      <!-- Overview Cards -->
      <div class="dashboard-overview-grid mb-5">
        <div class="dashboard-card dashboard-overview-card">
          <div class="dashboard-card-icon"><v-icon size="18">mdi-format-list-bulleted</v-icon></div>
          <div class="dashboard-card-label">{{ tm('overview.total') }}</div>
          <div class="dashboard-card-value">{{ overviewStats.total }}</div>
          <div class="dashboard-card-note">{{ tm('overview.totalNote') }}</div>
        </div>
        <div class="dashboard-card dashboard-overview-card">
          <div class="dashboard-card-icon"><v-icon size="18">mdi-check-circle-outline</v-icon></div>
          <div class="dashboard-card-label">{{ tm('overview.active') }}</div>
          <div class="dashboard-card-value">{{ overviewStats.active }}</div>
          <div class="dashboard-card-note">{{ tm('overview.activeNote') }}</div>
        </div>
        <div class="dashboard-card dashboard-overview-card">
          <div class="dashboard-card-icon"><v-icon size="18">mdi-layers-outline</v-icon></div>
          <div class="dashboard-card-label">{{ tm('overview.stages') }}</div>
          <div class="dashboard-card-value">{{ overviewStats.coveredStages }} / 7</div>
          <div class="dashboard-card-note">{{ tm('overview.stagesNote') }}</div>
        </div>
        <div class="dashboard-card dashboard-overview-card">
          <div class="dashboard-card-icon"><v-icon size="18">mdi-archive-outline</v-icon></div>
          <div class="dashboard-card-label">{{ tm('overview.legacy') }}</div>
          <div class="dashboard-card-value">{{ overviewStats.legacy }}</div>
          <div class="dashboard-card-note">{{ tm('overview.legacyNote') }}</div>
        </div>
      </div>

      <!-- Filters -->
      <div class="dashboard-card dashboard-card--padded mb-5">
        <div style="display: flex; gap: 12px; flex-wrap: wrap; align-items: center">
          <v-text-field
            v-model="search"
            :placeholder="tm('actions.search')"
            prepend-inner-icon="mdi-magnify"
            density="compact"
            variant="outlined"
            hide-details
            clearable
            style="max-width: 280px"
          />
          <v-select
            v-model="filterCategory"
            :items="[{ title: tm('filters.allCategories'), value: '' }, ...stages.map((s: any) => ({ title: s.name, value: s.id }))]"
            density="compact"
            variant="outlined"
            hide-details
            style="max-width: 180px"
          />
          <v-select
            v-model="filterSource"
            :items="[{ title: tm('filters.allSources'), value: '' }, ...uniqueSources.map((s: any) => ({ title: s, value: s }))]"
            density="compact"
            variant="outlined"
            hide-details
            style="max-width: 160px"
          />
          <v-select
            v-model="filterType"
            :items="[
              { title: tm('filters.allTypes'), value: '' },
              { title: tm('types.static'), value: 'static' },
              { title: tm('types.template'), value: 'template' },
              { title: tm('types.functional'), value: 'functional' },
            ]"
            density="compact"
            variant="outlined"
            hide-details
            style="max-width: 140px"
          />
        </div>
      </div>

      <!-- Table -->
      <div class="dashboard-card">
        <v-table density="comfortable" hover>
          <thead>
            <tr>
              <th>{{ tm('table.promptId') }}</th>
              <th>{{ tm('table.name') }}</th>
              <th>{{ tm('table.category') }}</th>
              <th>{{ tm('table.type') }}</th>
              <th>{{ tm('table.source') }}</th>
              <th style="text-align:center">{{ tm('table.priority') }}</th>
              <th style="text-align:center">{{ tm('table.active') }}</th>
              <th style="text-align:right">{{ tm('table.actions') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="loading">
              <td colspan="8" style="text-align:center; padding: 32px">
                <v-progress-circular indeterminate size="32" />
              </td>
            </tr>
            <tr v-else-if="filteredPrompts.length === 0">
              <td colspan="8" class="dashboard-empty" style="text-align:center; padding: 32px">
                {{ search || filterCategory || filterSource || filterType ? tm('table.noMatch') : tm('table.noData') }}
              </td>
            </tr>
            <tr
              v-for="item in filteredPrompts"
              :key="item.prompt_id"
              style="cursor: pointer"
              @click="openEdit(item)"
            >
              <td><strong style="font-family: monospace; font-size: 13px">{{ item.prompt_id }}</strong></td>
              <td>{{ item.name }}</td>
              <td>
                <v-chip :color="categoryColors[item.category] || 'grey'" size="small" label>
                  {{ item.category }}
                </v-chip>
              </td>
              <td>
                <v-chip size="x-small" variant="outlined">{{ tm(`types.${item.type}`) || item.type }}</v-chip>
              </td>
              <td style="font-size: 13px; color: var(--dashboard-muted)">{{ item.source }}</td>
              <td style="text-align:center">
                <v-chip size="x-small" color="primary" variant="tonal">{{ item.priority }}</v-chip>
              </td>
              <td style="text-align:center" @click.stop>
                <v-switch
                  :model-value="item.is_active"
                  density="compact"
                  hide-details
                  color="primary"
                  @update:model-value="toggleActive(item)"
                />
              </td>
              <td style="text-align:right" @click.stop>
                <v-btn icon size="x-small" variant="text" @click="openEdit(item)">
                  <v-icon size="16">mdi-pencil-outline</v-icon>
                </v-btn>
                <v-btn icon size="x-small" variant="text" color="error" @click="deletePrompt(item.prompt_id)">
                  <v-icon size="16">mdi-delete-outline</v-icon>
                </v-btn>
              </td>
            </tr>
          </tbody>
        </v-table>
      </div>

      <!-- Editor Drawer -->
      <v-navigation-drawer
        v-model="editorOpen"
        location="right"
        temporary
        width="520"
        class="pa-0"
      >
        <div style="padding: 24px; height: 100%; display: flex; flex-direction: column">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px">
            <h3 style="font-size: 18px; font-weight: 600">
              {{ editorMode === 'create' ? tm('editor.titleCreate') : tm('editor.titleEdit') }}
            </h3>
            <v-btn icon variant="text" size="small" @click="editorOpen = false">
              <v-icon>mdi-close</v-icon>
            </v-btn>
          </div>

          <v-alert
            v-if="editorMode === 'edit' && isSystemEntry(editForm)"
            type="warning"
            density="compact"
            variant="tonal"
            class="mb-4"
          >
            {{ tm('editor.systemWarning') }}
          </v-alert>

          <div style="flex: 1; overflow-y: auto">
            <v-text-field
              v-model="editForm.prompt_id"
              :label="tm('editor.promptId')"
              :hint="tm('editor.promptIdHint')"
              persistent-hint
              density="compact"
              variant="outlined"
              :readonly="editorMode === 'edit'"
              class="mb-3"
            />
            <v-text-field
              v-model="editForm.name"
              :label="tm('editor.name')"
              :hint="tm('editor.nameHint')"
              persistent-hint
              density="compact"
              variant="outlined"
              class="mb-3"
            />
            <div class="dashboard-form-grid mb-3">
              <v-select
                v-model="editForm.category"
                :label="tm('editor.category')"
                :items="stages.map((s: any) => ({ title: `${s.order}. ${s.name}`, value: s.id }))"
                :hint="tm('editor.categoryHint')"
                persistent-hint
                density="compact"
                variant="outlined"
              />
              <v-text-field
                v-model.number="editForm.priority"
                :label="tm('editor.priority')"
                :hint="tm('editor.priorityHint')"
                persistent-hint
                type="number"
                :min="0"
                :max="100"
                density="compact"
                variant="outlined"
              />
            </div>
            <div class="dashboard-form-grid mb-3">
              <v-select
                v-model="editForm.type"
                :label="tm('editor.type')"
                :items="[
                  { title: tm('types.static'), value: 'static' },
                  { title: tm('types.template'), value: 'template' },
                  { title: tm('types.functional'), value: 'functional' },
                ]"
                density="compact"
                variant="outlined"
              />
              <v-text-field
                v-model="editForm.source"
                :label="tm('editor.source')"
                :hint="tm('editor.sourceHint')"
                persistent-hint
                density="compact"
                variant="outlined"
              />
            </div>
            <v-switch
              v-model="editForm.is_active"
              :label="tm('editor.active')"
              density="compact"
              color="primary"
              hide-details
              class="mb-4"
            />
            <v-textarea
              v-model="editForm.content"
              :label="tm('editor.content')"
              :hint="editForm.type === 'functional' ? tm('editor.contentFunctionalHint') : tm('editor.contentHint')"
              persistent-hint
              :readonly="editForm.type === 'functional'"
              variant="outlined"
              rows="10"
              auto-grow
            />
          </div>

          <div style="display: flex; gap: 10px; justify-content: flex-end; padding-top: 16px; border-top: 1px solid var(--dashboard-border)">
            <v-btn variant="text" @click="editorOpen = false">{{ tm('actions.cancel') }}</v-btn>
            <v-btn color="primary" @click="savePrompt">{{ tm('actions.save') }}</v-btn>
          </div>
        </div>
      </v-navigation-drawer>

      <!-- Snackbar -->
      <v-snackbar v-model="snackbar.show" :color="snackbar.color" :timeout="3000" location="bottom right">
        {{ snackbar.text }}
      </v-snackbar>
    </v-container>
  </div>
</template>
