<template>
  <div class="provider-page">
    <v-container fluid class="pa-0">
      <!-- 页面标题 -->
      <v-row class="d-flex justify-space-between align-center px-4 py-3 pb-4">
        <div>
          <h1 class="text-h1 font-weight-bold mb-2">
            <v-icon color="black" class="me-2">mdi-creation</v-icon>{{ tm('title') }}
          </h1>
          <p class="text-subtitle-1 text-medium-emphasis mb-4">
            {{ tm('subtitle') }}
          </p>
        </div>
      </v-row>

      <div>
        <!-- Model Hub Type 标签页 -->
        <v-tabs v-model="selectedProviderType" bg-color="transparent" class="mb-4">
          <v-tab v-for="type in providerTypes" :key="type.value" :value="type.value" class="font-weight-medium px-3">
            <v-icon start>{{ type.icon }}</v-icon>
            {{ type.label }}
          </v-tab>
        </v-tabs>

        <!-- 统一布局: 左侧列表 + 右侧配置 -->
        <div class="provider-workbench">
          <v-row class="provider-workbench__shell">
            <!-- 左侧提供商源列表 -->
            <v-col cols="12" md="4" lg="3" class="provider-workbench__sources">
              <ProviderSourcesPanel
                :displayed-provider-sources="displayedProviderSources"
                :selected-provider-source="selectedProviderSource"
                :available-source-types="availableSourceTypes"
                :tm="tm"
                :resolve-source-icon="resolveSourceIcon"
                :getSourceDisplayName="getSourceDisplayName"
                @add-provider-source="addProviderSource"
                @select-provider-source="selectProviderSource"
                @delete-provider-source="deleteProviderSource"
              />
            </v-col>

            <!-- 右侧配置面板 -->
            <v-col cols="12" md="8" lg="9" class="provider-workbench__settings">
              <v-card class="provider-config-card provider-settings-panel h-100" elevation="0">
                <div v-if="selectedProviderSource" class="provider-config-header">
                  <div class="provider-config-headline">
                    <div class="provider-config-kicker">{{ tm('providers.settings') }}</div>
                    <div class="d-flex align-center mt-2">
                      <v-avatar size="32" class="me-3" rounded="0">
                        <v-img :src="resolveSourceIcon(selectedProviderSource)" alt="logo" cover></v-img>
                      </v-avatar>
                      <div class="provider-config-title">{{ selectedProviderSource.id }}</div>
                    </div>
                  </div>

                  <div class="provider-config-actions">
                    <v-btn
                      color="primary"
                      prepend-icon="mdi-content-save-outline"
                      :loading="savingSource"
                      :disabled="!isSourceModified"
                      @click="saveProviderSource"
                      variant="tonal"
                      rounded="xl"
                    >
                      {{ tm('providerSources.save') }}
                    </v-btn>
                  </div>
                </div>

                <v-card-text class="provider-config-body" v-if="selectedProviderSource">
                  <!-- 提供商基础信息 -->
                  <section class="provider-section">
                    <div class="provider-section-head">
                      <div class="provider-section-title">基础配置</div>
                    </div>
                    
                    <div class="object-config">
                      <!-- Provider Selection Row (Hidden for Routers) -->
                      <v-row class="config-row" v-if="selectedProviderType !== 'routers'">
                        <v-col cols="12" sm="6" class="property-info">
                          <v-list-item density="compact">
                            <v-list-item-title class="property-name">
                              Provider <span class="property-key">(provider)</span>
                            </v-list-item-title>
                            <v-list-item-subtitle class="property-hint">
                              选择大模型服务提供商
                            </v-list-item-subtitle>
                          </v-list-item>
                        </v-col>
                        <v-col cols="12" sm="6" class="config-input">
                          <v-autocomplete
                            v-model="selectedTemplateKey"
                            :items="availableProviders"
                            item-title="label"
                            item-value="value"
                            variant="outlined"
                            density="compact"
                            hide-details
                            class="config-field"
                            auto-select-first
                            @update:model-value="onProviderChange"
                          >
                            <!-- 选定项显示图标 -->
                            <template v-slot:selection="{ item }">
                              <div class="d-flex align-center">
                                <v-avatar size="18" rounded="0" class="me-2">
                                  <v-img :src="getProviderIcon(templatesMap[item.value]?.provider)" cover></v-img>
                                </v-avatar>
                                <span class="text-body-2">{{ item.title }}</span>
                              </div>
                            </template>

                            <!-- 列表项显示图标 -->
                            <template v-slot:item="{ props, item }">
                              <v-list-item v-bind="props">
                                <template v-slot:prepend>
                                  <v-avatar size="20" rounded="0" class="me-2">
                                    <v-img :src="getProviderIcon(templatesMap[item.value]?.provider)" cover></v-img>
                                  </v-avatar>
                                </template>
                              </v-list-item>
                            </template>
                          </v-autocomplete>
                        </v-col>
                      </v-row>

                      <v-divider class="config-divider" v-if="selectedProviderType !== 'routers'"></v-divider>

                      <!-- ID Input Row -->
                      <v-row class="config-row">
                        <v-col cols="12" sm="6" class="property-info">
                          <v-list-item density="compact">
                            <v-list-item-title class="property-name">
                              ID <span class="property-key">(id)</span>
                            </v-list-item-title>
                            <v-list-item-subtitle class="property-hint">
                              该提供商源的唯一标识符
                            </v-list-item-subtitle>
                          </v-list-item>
                        </v-col>
                        <v-col cols="12" sm="6" class="config-input">
                          <v-text-field
                            v-model="editableProviderSource.id"
                            variant="outlined"
                            density="compact"
                            hide-details
                            class="config-field"
                            @input="idTouched = true"
                          ></v-text-field>
                        </v-col>
                      </v-row>

                      <v-divider class="config-divider"></v-divider>

                      <!-- 特殊：模型路由配置 -->
                      <template v-if="selectedProviderType === 'routers'">
                        <!-- 路由策略 -->
                        <v-row class="config-row">
                          <v-col cols="12" sm="6" class="property-info">
                            <v-list-item density="compact">
                              <v-list-item-title class="property-name">路由策略</v-list-item-title>
                              <v-list-item-subtitle class="property-hint">决定请求如何分配</v-list-item-subtitle>
                            </v-list-item>
                          </v-col>
                          <v-col cols="12" sm="6" class="config-input">
                            <v-select
                              v-model="editableProviderSource.routing_strategy"
                              :items="[
                                {title: '优先级 (Priority-Based Fallover)', value: 'priority-based'},
                                {title: '轮询 (Simple Shuffle)', value: 'simple-shuffle'},
                                {title: '最少忙碌 (Least Busy)', value: 'least-busy'},
                                {title: '最低延迟 (Latency Based)', value: 'latency-based-routing'}
                              ]"
                              variant="outlined"
                              density="compact"
                              hide-details
                            ></v-select>
                          </v-col>
                        </v-row>
                        <v-divider class="config-divider"></v-divider>

                        <!-- 参与路由的模型列表 (新样式 + 动画) -->
                        <div class="pa-4">
                          <div class="d-flex align-center justify-space-between mb-4">
                            <div class="text-subtitle-1 font-weight-bold">参与路由的模型组 (按优先级排序)</div>
                            <v-chip size="small" color="primary" variant="tonal">{{ activeRouterModelsCount }} 个激活</v-chip>
                          </div>
                          
                          <div class="router-model-list-container border rounded-lg overflow-hidden">
                            <transition-group name="flip-list" tag="div" class="v-list v-list--density-compact v-theme--light">
                              <template v-for="(model, index) in allCompletionModels" :key="model.id">
                                <v-list-item class="px-4 py-2 router-item" :class="{'bg-active-light': isModelInRouter(model.id)}">
                                  <template v-slot:prepend>
                                    <v-avatar size="32" rounded="0" class="me-3">
                                      <v-img :src="getProviderIcon(model.provider)" cover></v-img>
                                    </v-avatar>
                                    <div>
                                      <div class="text-body-1 font-weight-bold">{{ model.id }}</div>
                                      <div class="text-caption text-medium-emphasis">{{ model.model }}</div>
                                    </div>
                                  </template>

                                  <template v-slot:append>
                                    <div class="d-flex align-center ga-4">
                                      <!-- 优先级步进器 UI -->
                                      <div class="priority-stepper d-flex align-center" v-if="isModelInRouter(model.id)">
                                        <v-btn 
                                          icon="mdi-minus" 
                                          size="x-small" 
                                          variant="flat" 
                                          class="stepper-btn"
                                          @click="adjustPriority(model.id, -1)"
                                        ></v-btn>
                                        <div class="priority-display d-flex flex-column align-center">
                                          <span class="priority-val">{{ getModelPriority(model.id) }}</span>
                                          <span class="priority-label">PRIO</span>
                                        </div>
                                        <v-btn 
                                          icon="mdi-plus" 
                                          size="x-small" 
                                          variant="flat" 
                                          class="stepper-btn"
                                          @click="adjustPriority(model.id, 1)"
                                        ></v-btn>
                                      </div>

                                      <v-switch
                                        :model-value="isModelInRouter(model.id)"
                                        density="compact"
                                        inset
                                        hide-details
                                        color="primary"
                                        @update:model-value="toggleModelInRouter(model.id, $event)"
                                      ></v-switch>
                                    </div>
                                  </template>
                                </v-list-item>
                                <v-divider v-if="index !== allCompletionModels.length - 1" :key="'div-' + model.id"></v-divider>
                              </template>
                            </transition-group>
                          </div>
                        </div>
                      </template>

                      <!-- 使用 AstrBotConfig 渲染 Key, API Base 等 -->
                      <AstrBotConfig 
                        v-if="basicSourceConfig && selectedProviderType !== 'routers'" 
                        :iterable="basicSourceConfig" 
                        :metadata="providerSourceSchema"
                        metadataKey="provider" 
                        :is-editing="true" 
                      />
                    </div>
                    
                    <div class="d-flex justify-end mt-4" v-if="selectedProviderType !== 'routers'">
                       <v-btn
                        variant="tonal"
                        size="small"
                        color="info"
                        prepend-icon="mdi-swap-horizontal"
                        @click="testSourceConnectivity"
                        :loading="testingSource"
                        rounded="xl"
                      >
                        测试连接
                      </v-btn>
                    </div>
                  </section>

                  <!-- 高级配置 -->
                  <section v-if="advancedSourceConfig && selectedProviderType !== 'routers'" class="provider-section mt-4">
                    <div class="provider-section-head d-flex justify-space-between align-center">
                      <div class="provider-section-title">{{ tm('providerSources.advancedConfig') }}</div>
                      <v-btn
                        variant="text"
                        size="small"
                        :icon="showAdvanced ? 'mdi-chevron-up' : 'mdi-chevron-down'"
                        @click="showAdvanced = !showAdvanced"
                      ></v-btn>
                    </div>
                    <v-expand-transition>
                      <div v-show="showAdvanced">
                        <AstrBotConfig
                          :iterable="advancedSourceConfig"
                          :metadata="providerSourceSchema"
                          metadataKey="provider"
                          :is-editing="true"
                        />
                      </div>
                    </v-expand-transition>
                  </section>

                  <!-- 已配置模型管理 -->
                  <section class="provider-section provider-section--models mt-4" v-if="selectedProviderType !== 'routers'">
                    <ProviderModelsPanel
                      :entries="filteredMergedModelEntries"
                      :available-count="availableModels.length"
                      v-model:model-search="modelSearch"
                      :loading-models="loadingModels"
                      :is-source-modified="isSourceModified"
                      :supports-image-input="supportsImageInput"
                      :supports-audio-input="supportsAudioInput"
                      :supports-tool-call="supportsToolCall"
                      :supports-reasoning="supportsReasoning"
                      :format-context-limit="formatContextLimit"
                      :testing-providers="testingProviders"
                      :tm="tm"
                      @fetch-models="fetchAvailableModels"
                      @open-manual-model="openManualModelDialog"
                      @open-provider-edit="openProviderEdit"
                      @toggle-provider-enable="toggleProviderEnable"
                      @test-provider="testProvider"
                      @delete-provider="deleteProvider"
                      @add-model-provider="addModelProvider"
                    />
                  </section>
                </v-card-text>

                <div v-else class="provider-empty-state">
                  <v-icon size="64" color="grey-lighten-1">mdi-router-network</v-icon>
                  <p class="mt-4 text-h3">模型路由管理</p>
                  <p class="text-body-1 text-medium-emphasis">从左侧选择或创建一个路由组以开始配置</p>
                </div>
              </v-card>
            </v-col>
          </v-row>
        </div>
      </div>
    </v-container>

    <!-- 手动添加模型对话框 -->
    <v-dialog v-model="showManualModelDialog" max-width="450">
      <v-card :title="tm('models.manualDialogTitle')" rounded="lg">
        <v-card-text class="py-4">
          <v-text-field 
            v-model="manualModelId" 
            :label="tm('models.manualDialogModelLabel')" 
            flat 
            variant="solo-filled" 
            autofocus 
            clearable
            class="mb-4"
          ></v-text-field>
          <v-text-field 
            :model-value="manualProviderId" 
            flat 
            variant="solo-filled" 
            :label="tm('models.manualDialogPreviewLabel')" 
            persistent-hint
            readonly
            density="compact"
            :hint="tm('models.manualDialogPreviewHint')"
          ></v-text-field>
        </v-card-text>
        <v-card-actions class="pa-4">
          <v-spacer></v-spacer>
          <v-btn variant="text" @click="showManualModelDialog = false" rounded="lg">取消</v-btn>
          <v-btn color="primary" @click="confirmManualModel" variant="flat" rounded="lg">添加</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- 已配置模型编辑对话框 -->
    <v-dialog v-model="showProviderEditDialog" width="800">
      <v-card :title="providerEditData?.id || tm('dialogs.config.editTitle')" rounded="lg">
        <v-card-text class="py-4">
          <v-alert type="warning" variant="tonal" class="mb-4" density="compact">
            不建议修改 ID，可能会导致指向该模型的相关配置失效。
          </v-alert>
          <AstrBotConfig 
            v-if="providerEditData" 
            :iterable="providerEditData" 
            :metadata="configSchema"
            metadataKey="provider" 
            :is-editing="true" 
          />
        </v-card-text>
        <v-card-actions class="pa-4">
          <v-spacer></v-spacer>
          <v-btn variant="text" @click="showProviderEditDialog = false"
            :disabled="savingProviders.includes(providerEditData?.id)" rounded="lg">
            {{ tm('dialogs.config.cancel') }}
          </v-btn>
          <v-btn color="primary" @click="saveEditedProvider" 
            :loading="savingProviders.includes(providerEditData?.id)" variant="flat" rounded="lg">
            {{ tm('dialogs.config.save') }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- 消息提示 -->
    <v-snackbar v-model="snackbar.show" :color="snackbar.color" :timeout="3000" location="top" rounded="xl">
      {{ snackbar.message }}
    </v-snackbar>
  </div>
</template>

<script setup>
import { ref, watch, computed, onMounted } from 'vue'
import axios from 'axios'
import { useModuleI18n } from '@/i18n/composables'
import AstrBotConfig from '@/components/shared/AstrBotConfig.vue'
import ProviderModelsPanel from '@/components/provider/ProviderModelsPanel.vue'
import ProviderSourcesPanel from '@/components/provider/ProviderSourcesPanel.vue'
import { useProviderSources } from '@/composables/useProviderSources'
import { getProviderIcon } from '@/utils/providerUtils'

const props = defineProps({
  defaultTab: {
    type: String,
    default: 'completions'
  }
})

const { tm } = useModuleI18n('features/provider')

const snackbar = ref({
  show: false,
  message: '',
  color: 'success'
})

function showMessage(message, color = 'success') {
  snackbar.value = { show: true, message, color }
}

const {
  selectedProviderType,
  selectedProviderSource,
  selectedProviderSourceOriginalId,
  editableProviderSource,
  availableModels,
  loadingModels,
  savingSource,
  testingProviders,
  isSourceModified,
  configSchema,
  providerSourceSchema,
  manualModelId,
  modelSearch,
  providerTypes,
  availableSourceTypes,
  displayedProviderSources,
  filteredMergedModelEntries,
  basicSourceConfig,
  advancedSourceConfig,
  manualProviderId,
  resolveSourceIcon,
  getSourceDisplayName,
  supportsImageInput,
  supportsAudioInput,
  supportsToolCall,
  supportsReasoning,
  formatContextLimit,
  updateDefaultTab,
  selectProviderSource,
  addProviderSource,
  deleteProviderSource,
  saveProviderSource,
  fetchAvailableModels,
  addModelProvider,
  deleteProvider,
  modelAlreadyConfigured,
  testProvider,
  loadConfig,
  providerTemplates
} = useProviderSources({
  defaultTab: props.defaultTab,
  tm,
  showMessage
})

const showAdvanced = ref(false)
const testingSource = ref(false)
const showProviderEditDialog = ref(false)
const providerEditData = ref(null)
const providerEditOriginalId = ref('')
const showManualModelDialog = ref(false)
const savingProviders = ref([])

// 状态变量
const selectedTemplateKey = ref('')
const idTouched = ref(false) // 追踪用户是否手动改过 ID

const uiTypeToBackendType = {
    'completions': 'chat_completion',
    'routers': 'model_router',
    'audio/transcriptions': 'speech_to_text',
    'audio/speech': 'text_to_speech',
    'embeddings': 'embedding',
    'rerank': 'rerank'
}

const templatesMap = computed(() => providerTemplates.value || {})

const availableProviders = computed(() => {
  const templates = templatesMap.value
  const backendType = uiTypeToBackendType[selectedProviderType.value] || selectedProviderType.value
  
  return Object.entries(templates)
    .filter(([_, t]) => t.provider_type === backendType)
    .map(([name, t]) => ({
      label: name,
      value: name 
    }))
    .sort((a, b) => a.label.localeCompare(b.label)) // 增加首字母排序
})

// 用于模型路由的模型列表
const providerList = ref([])
const allCompletionModels = computed(() => {
  if (!providerList.value) return []
  
  // 给原始列表加个索引，方便稳定排序
  const indexedModels = providerList.value.map((p, idx) => ({ ...p, originalIndex: idx }))
  
  // 过滤掉当前的 router 本身，防止循环引用
  const models = indexedModels.filter(p => p.provider_type === 'chat_completion' && p.id !== editableProviderSource.value?.id)
  
  // 核心逻辑：自动排序 (三级排序)
  return [...models].sort((a, b) => {
    const inA = isModelInRouter(a.id)
    const inB = isModelInRouter(b.id)
    
    // 1. 状态比较
    if (inA && !inB) return -1
    if (!inA && inB) return 1
    
    // 2. 状态相同时
    if (inA && inB) {
      const diff = getModelPriority(a.id) - getModelPriority(b.id)
      if (diff !== 0) return diff // 优先级不同按优先级
      return a.originalIndex - b.originalIndex // 优先级相同保持原始顺序
    }
    
    // 3. 均未激活时按原始顺序
    return a.originalIndex - b.originalIndex
  })
})

const activeRouterModelsCount = computed(() => {
  if (!editableProviderSource.value?.model_list) return 0
  return editableProviderSource.value.model_list.length
})

function isModelInRouter(modelId) {
  const list = editableProviderSource.value?.model_list || []
  return list.some(item => (typeof item === 'string' ? item === modelId : item.id === modelId))
}

function getModelPriority(modelId) {
  const list = editableProviderSource.value?.model_list || []
  const found = list.find(item => (typeof item === 'object' && item.id === modelId))
  return found ? (found.priority || 0) : 0
}

function adjustPriority(modelId, delta) {
  if (!editableProviderSource.value.model_list) {
    editableProviderSource.value.model_list = []
  }
  const list = editableProviderSource.value.model_list
  const idx = list.findIndex(item => (typeof item === 'string' ? item === modelId : item.id === modelId))
  
  if (idx !== -1) {
    let item = list[idx]
    if (typeof item === 'string') {
      item = { id: item, priority: 0 }
    }
    item.priority = Math.max(0, (item.priority || 0) + delta)
    list[idx] = item
    isSourceModified.value = true
  }
}

function toggleModelInRouter(modelId, enabled) {
  if (!editableProviderSource.value.model_list) {
    editableProviderSource.value.model_list = []
  }
  const list = editableProviderSource.value.model_list
  
  if (enabled) {
    if (!isModelInRouter(modelId)) {
      list.push({ id: modelId, priority: 0 })
    }
  } else {
    const idx = list.findIndex(item => (typeof item === 'string' ? item === modelId : item.id === modelId))
    if (idx !== -1) {
      list.splice(idx, 1)
    }
  }
  isSourceModified.value = true
}

onMounted(async () => {
    try {
        const res = await axios.get('/api/config/provider/list', { params: { provider_type: 'chat_completion' }})
        if (res.data.status === 'ok') {
            providerList.value = res.data.data || []
        }
    } catch (err) {
        console.error("Failed to fetch provider list", err)
    }
})

// 监听选中源的变化，初始化状态
watch(selectedProviderSource, (newSource) => {
  idTouched.value = false // 切换源时，重置“手动修改”标记
  if (newSource) {
    const templates = templatesMap.value
    const found = Object.entries(templates).find(([_, t]) => 
      t.provider === newSource.provider && t.type === newSource.type
    )
    selectedTemplateKey.value = found ? found[0] : ''
  } else {
    selectedTemplateKey.value = ''
  }
}, { immediate: true })

function onProviderChange(templateName) {
  const templates = templatesMap.value
  const template = templates[templateName]
  
  if (template && editableProviderSource.value) {
    // 智能同步 ID：如果用户没手动改过 ID，则根据新模板自动更新 ID
    if (!idTouched.value) {
      editableProviderSource.value.id = template.id || templateName
    }

    editableProviderSource.value.provider = template.provider
    editableProviderSource.value.type = template.type

    const excludeKeys = ['id', 'enable', 'model', 'provider_source_id', 'modalities', 'custom_extra_body', 'provider']
    const baseFields = ['id', 'enable', 'provider', 'type', 'provider_type', 'api_base', 'key']
    
    Object.keys(editableProviderSource.value).forEach(key => {
        if (!baseFields.includes(key)) {
            delete editableProviderSource.value[key]
        }
    })
    
    for (const [key, value] of Object.entries(template)) {
      if (!excludeKeys.includes(key)) {
        editableProviderSource.value[key] = value
      }
    }
  }
  isSourceModified.value = true
}

async function testSourceConnectivity() {
  if (!editableProviderSource.value) return
  testingSource.value = true
  try {
    const response = await axios.get('/api/config/provider_sources/models', {
      params: { source_id: editableProviderSource.value.id }
    })
    if (response.data.status === 'ok') {
      showMessage('连接测试成功！已成功获取模型列表。')
    } else {
      throw new Error(response.data.message)
    }
  } catch (err) {
    showMessage('连接测试失败: ' + (err.response?.data?.message || err.message), 'error')
  } finally {
    testingSource.value = false
  }
}

function openProviderEdit(provider) {
  providerEditData.value = JSON.parse(JSON.stringify(provider))
  providerEditOriginalId.value = provider.id
  showProviderEditDialog.value = true
}

async function saveEditedProvider() {
  if (!providerEditData.value) return
  savingProviders.value.push(providerEditData.value.id)
  try {
    const res = await axios.post('/api/config/provider/update', {
      id: providerEditOriginalId.value || providerEditData.value.id,
      config: providerEditData.value
    })
    if (res.data.status === 'error') throw new Error(res.data.message)
    showMessage(res.data.message || tm('providerSources.saveSuccess'))
    showProviderEditDialog.value = false
    await loadConfig()
  } catch (err) {
    showMessage(err.response?.data?.message || err.message || tm('providerSources.saveError'), 'error')
  } finally {
    savingProviders.value = savingProviders.value.filter(id => id !== providerEditData.value?.id)
  }
}

function openManualModelDialog() {
  if (!selectedProviderSource.value) {
    showMessage(tm('providerSources.selectHint'), 'error')
    return
  }
  manualModelId.value = ''
  showManualModelDialog.value = true
}

async function confirmManualModel() {
  const modelId = manualModelId.value.trim()
  if (!selectedProviderSource.value) return
  if (!modelId) {
    showMessage(tm('models.manualModelRequired'), 'error')
    return
  }
  if (modelAlreadyConfigured(modelId)) {
    showMessage(tm('models.manualModelExists'), 'error')
    return
  }
  await addModelProvider(modelId)
  showManualModelDialog.value = false
}

watch(() => props.defaultTab, (val) => {
  updateDefaultTab(val)
})

</script>

<style scoped>
.provider-page {
  --provider-surface: rgb(var(--v-theme-surface));
  --provider-text: rgb(var(--v-theme-on-surface));
  --provider-muted: rgba(var(--v-theme-on-surface), 0.68);
  --provider-subtle: rgba(var(--v-theme-on-surface), 0.56);
  --provider-border: rgba(var(--v-theme-on-surface), 0.1);
  --provider-soft: rgba(var(--v-theme-primary), 0.08);
  padding: 20px;
  padding-top: 8px;
}

.provider-workbench {
  display: flex;
  justify-content: center;
}

.provider-workbench__shell {
  width: 100%;
  max-width: 1600px;
}

.provider-config-card {
  min-height: 500px;
  border: 1px solid var(--provider-border);
  border-radius: 20px;
  background: var(--provider-surface);
}

.provider-config-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 24px 24px 20px;
  border-bottom: 1px solid var(--provider-border);
}

.provider-config-kicker {
  color: var(--provider-subtle);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}

.provider-config-title {
  font-size: 24px;
  font-weight: 700;
  letter-spacing: -0.02em;
  color: var(--provider-text);
}

.provider-config-body {
  padding: 24px;
}

.provider-section {
  border: 1px solid var(--provider-border);
  border-radius: 16px;
  background: rgba(var(--v-theme-on-surface), 0.01);
  padding: 20px;
}

.provider-section-title {
  font-size: 16px;
  font-weight: 700;
  color: var(--provider-text);
  margin-bottom: 16px;
}

.provider-empty-state {
  min-height: 500px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: var(--provider-muted);
  text-align: center;
}

.router-model-list-container {
  background: rgb(var(--v-theme-surface));
  max-height: 400px;
  overflow-y: auto;
}

.bg-active-light {
  background-color: rgba(var(--v-theme-primary), 0.04);
}

.router-item {
  transition: all 0.3s ease;
}

/* 优先级步进器样式 */
.priority-stepper {
  background: rgba(var(--v-theme-on-surface), 0.05);
  border-radius: 12px;
  padding: 2px;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.1);
}

.stepper-btn {
  width: 24px !important;
  height: 24px !important;
  min-width: 24px !important;
  background: white !important;
  border-radius: 8px !important;
  box-shadow: 0 2px 4px rgba(0,0,0,0.05) !important;
}

.priority-display {
  padding: 0 10px;
  min-width: 40px;
}

.priority-val {
  font-size: 14px;
  line-height: 1;
  font-weight: 800;
  color: rgb(var(--v-theme-primary));
}

.priority-label {
  font-size: 8px;
  font-weight: 700;
  color: var(--provider-muted);
  letter-spacing: 0.05em;
}

/* FLIP 动画样式 */
.flip-list-move {
  transition: transform 0.5s ease;
}

.flip-list-enter-active,
.flip-list-leave-active {
  transition: all 0.5s ease;
}

.flip-list-enter-from,
.flip-list-leave-to {
  opacity: 0;
  transform: translateX(30px);
}

/* Replicating AstrBotConfig styles */
.config-row {
  margin: 0;
  align-items: center;
  padding: 4px 8px;
  border-radius: 4px;
}

.config-row:hover {
  background-color: rgba(var(--v-theme-on-surface), 0.03);
}

.property-info {
  padding: 0;
}

.property-name {
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--v-theme-primaryText);
}

.property-hint {
  font-size: 0.75rem;
  color: var(--v-theme-secondaryText);
  margin-top: 2px;
}

.property-key {
  font-size: 0.85em;
  opacity: 0.7;
  font-weight: normal;
  display: none; /* Matches AstrBotConfig behavior */
}

.config-input {
  padding: 4px 8px;
}

.config-field {
  margin-bottom: 0;
}

.config-divider {
  border-color: rgba(var(--v-theme-on-surface), 0.05);
  margin: 0px 16px;
}

@media (max-width: 960px) {
  .provider-config-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 16px;
  }
  .provider-config-actions {
    width: 100%;
    display: flex;
    justify-content: flex-end;
  }
}
</style>
