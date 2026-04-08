<template>
  <div class="d-flex align-center justify-space-between">
    <span v-if="!hasSelection" style="color: rgb(var(--v-theme-primaryText));">
      {{ tm('providerSelector.notSelected') }}
    </span>
    <span v-else class="provider-name-text">
      <template v-if="multiple">
        {{ tm('providerSelector.selectedCount', { count: selectedProviders.length }) }}
      </template>
      <template v-else>
        {{ modelValue }}
      </template>
    </span>
    <v-btn size="small" color="primary" variant="tonal" @click="openDialog" rounded="xl">
      {{ buttonText || tm('providerSelector.buttonText') }}
    </v-btn>
  </div>

  <div v-if="multiple && selectedProviders.length > 0" class="selected-preview mt-2">
    <v-chip
      v-for="providerId in selectedProviders"
      :key="`preview-${providerId}`"
      size="x-small"
      color="primary"
      variant="tonal"
      class="mr-1 mb-1"
      label
    >
      {{ providerId }}
    </v-chip>
  </div>

  <!-- Provider Selection Dialog -->
  <v-dialog v-model="dialog" max-width="600px">
    <v-card rounded="xl">
      <v-card-title
        class="text-h3 py-4 d-flex align-center justify-space-between gap-4 flex-wrap px-6"
        style="font-weight: normal;"
      >
        <span>{{ tm('providerSelector.dialogTitle') }}</span>
        <v-btn
          size="small"
          color="primary"
          variant="tonal"
          prepend-icon="mdi-plus"
          rounded="xl"
          @click="openProviderDrawer"
        >
          {{ tm('providerSelector.createProvider') }}
        </v-btn>
      </v-card-title>
      
      <v-card-text class="pa-0" style="max-height: 500px; overflow-y: auto;">
        <v-progress-linear v-if="loading" indeterminate color="primary"></v-progress-linear>

        <!-- 已选项目（多选模式下排序） -->
        <div v-if="multiple && selectedProviders.length > 0" class="pa-4 bg-surface-variant-light">
          <div class="text-caption text-medium-emphasis mb-2 font-weight-bold">
            {{ tm('providerSelector.selectedCount', { count: selectedProviders.length }) }} (可拖动排序)
          </div>
          <v-list density="compact" class="selected-order-list pa-1" bg-color="transparent">
            <v-list-item
              v-for="(providerId, index) in selectedProviders"
              :key="`selected-${providerId}-${index}`"
              rounded="lg"
              class="mb-1 bg-surface shadow-sm"
            >
              <v-list-item-title class="font-weight-medium">{{ providerId }}</v-list-item-title>
              <template #append>
                <div class="d-flex ga-1">
                  <v-btn
                    icon="mdi-arrow-up"
                    size="x-small"
                    variant="text"
                    :disabled="index === 0"
                    @click.stop="moveSelected(index, -1)"
                  />
                  <v-btn
                    icon="mdi-arrow-down"
                    size="x-small"
                    variant="text"
                    :disabled="index === selectedProviders.length - 1"
                    @click.stop="moveSelected(index, 1)"
                  />
                  <v-btn
                    icon="mdi-close"
                    size="x-small"
                    variant="text"
                    color="error"
                    @click.stop="removeSelected(providerId)"
                  />
                </div>
              </template>
            </v-list-item>
          </v-list>
          <v-divider class="my-3"></v-divider>
        </div>
        
        <!-- 分组模型列表 -->
        <v-list v-if="!loading && providerList.length > 0" density="compact" class="pa-2">
          <!-- 不选择选项 -->
          <v-list-item
            v-if="!multiple"
            key="none"
            value=""
            @click="selectProvider({ id: '' })"
            :active="selectedProvider === ''"
            rounded="lg"
            class="ma-1 mb-2">
            <template v-slot:prepend>
              <v-icon color="grey">mdi-selection-off</v-icon>
            </template>
            <v-list-item-title>{{ tm('providerSelector.clearSelection') }}</v-list-item-title>
            <template v-slot:append>
              <v-icon v-if="selectedProvider === ''" color="primary">mdi-check-circle</v-icon>
            </template>
          </v-list-item>

          <!-- 循环分组 -->
          <v-list-group 
            v-for="group in groupedProviders" 
            :key="group.name" 
            :value="group.name"
          >
            <template v-slot:activator="{ props }">
              <v-list-item v-bind="props" rounded="lg" class="ma-1">
                <template v-slot:prepend>
                  <v-avatar size="24" rounded="0" class="me-2">
                    <v-img :src="getProviderIcon(group.providerId)" cover></v-img>
                  </v-avatar>
                </template>
                <v-list-item-title class="font-weight-bold">
                  {{ group.name }}
                  <v-chip v-if="group.isRouter" size="x-small" color="primary" variant="flat" class="ms-2" label>ROUTER</v-chip>
                </v-list-item-title>
                <template v-slot:append>
                  <v-chip size="x-small" variant="tonal">{{ group.items.length }}</v-chip>
                </template>
              </v-list-item>
            </template>

            <!-- 分组内的模型项 -->
            <v-list-item
              v-for="provider in group.items"
              :key="provider.id"
              :value="provider.id"
              @click="selectProvider(provider)"
              :active="isProviderSelected(provider.id)"
              rounded="lg"
              class="ms-8 me-1 my-1"
            >
              <v-list-item-title>{{ provider.id }}</v-list-item-title>
              <v-list-item-subtitle v-if="provider.model" class="text-caption">
                {{ provider.model }}
              </v-list-item-subtitle>
              <template v-slot:append>
                <v-icon v-if="isProviderSelected(provider.id)" color="primary">
                  {{ multiple ? 'mdi-checkbox-marked' : 'mdi-check-circle' }}
                </v-icon>
                <v-icon v-else-if="multiple" color="grey-lighten-1">mdi-checkbox-blank-outline</v-icon>
              </template>
            </v-list-item>
          </v-list-group>
        </v-list>
        
        <div v-else-if="!loading && providerList.length === 0" class="text-center py-12">
          <v-icon size="80" color="grey-lighten-2">mdi-api-off</v-icon>
          <p class="text-h4 text-grey-darken-1 mt-4">{{ tm('providerSelector.noProviders') }}</p>
          <p class="text-body-2 text-grey mt-1">请先在模型枢纽中配置服务商</p>
        </div>
      </v-card-text>
      
      <v-divider></v-divider>
      
      <v-card-actions class="pa-4 px-6">
        <v-spacer></v-spacer>
        <v-btn variant="text" rounded="xl" @click="cancelSelection">{{ tm('providerSelector.cancelSelection') }}</v-btn>
        <v-btn 
          color="primary" 
          variant="flat"
          rounded="xl"
          class="px-6"
          @click="confirmSelection">
          {{ tm('providerSelector.confirmSelection') }}
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>

  <v-overlay
    v-model="providerDrawer"
    class="provider-drawer-overlay"
    location="right"
    transition="slide-x-reverse-transition"
    :scrim="true"
    @click:outside="closeProviderDrawer"
  >
    <v-card class="provider-drawer-card" elevation="12">
      <div class="provider-drawer-header">
        <div class="text-h3 font-weight-bold">模型枢纽</div>
        <v-btn icon variant="text" @click="closeProviderDrawer">
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </div>
      <v-divider></v-divider>
      <div class="provider-drawer-content">
        <ProviderPage :default-tab="defaultTab" />
      </div>
    </v-card>
  </v-overlay>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import axios from 'axios'
import { useModuleI18n } from '@/i18n/composables'
import ProviderPage from '@/views/ProviderPage.vue'
import { getProviderIcon } from '@/utils/providerUtils'

const props = defineProps({
  modelValue: {
    type: [String, Array],
    default: ''
  },
  providerType: {
    type: String,
    default: 'chat_completion'
  },
  providerSubtype: {
    type: String,
    default: ''
  },
  buttonText: {
    type: String,
    default: ''
  },
  multiple: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['update:modelValue'])
const { tm } = useModuleI18n('core.shared')

const dialog = ref(false)
const providerList = ref([])
const loading = ref(false)
const selectedProvider = ref('')
const selectedProviders = ref([])
const providerDrawer = ref(false)

const hasSelection = computed(() => {
  if (props.multiple) {
    return selectedProviders.value.length > 0
  }
  return Boolean(props.modelValue)
})

const defaultTab = computed(() => {
  if (props.providerType === 'agent_runner' && props.providerSubtype) {
    return `select_agent_runner_provider:${props.providerSubtype}`
  }
  return props.providerType || 'chat_completion'
})

// 分组逻辑
const groupedProviders = computed(() => {
  const groups = {}
  
  providerList.value.forEach(item => {
    // 识别 Router
    const isRouter = item.type === 'model_router'
    const providerId = isRouter ? 'model_router' : (item.provider || 'unknown')
    const groupName = isRouter ? '模型路由 (Routers)' : (item.provider_display_name || providerId.toUpperCase())
    
    if (!groups[groupName]) {
      groups[groupName] = {
        name: groupName,
        providerId: providerId,
        isRouter: isRouter,
        items: []
      }
    }
    groups[groupName].items.push(item)
  })

  // 排序：Router 置顶，其余按名称字母排序
  return Object.values(groups).sort((a, b) => {
    if (a.isRouter) return -1
    if (b.isRouter) return 1
    return a.name.localeCompare(b.name)
  })
})

// 监听 modelValue 变化，同步到 selectedProvider
watch(() => props.modelValue, (newValue) => {
  if (props.multiple) {
    selectedProviders.value = Array.isArray(newValue)
      ? [...newValue.filter((v) => typeof v === 'string' && v)]
      : []
    return
  }
  selectedProvider.value = typeof newValue === 'string' ? newValue : ''
}, { immediate: true })

watch(providerDrawer, (isOpen, wasOpen) => {
  if (!isOpen && wasOpen) {
    loadProviders()
  }
})

async function openDialog() {
  if (props.multiple) {
    selectedProviders.value = Array.isArray(props.modelValue)
      ? [...props.modelValue.filter((v) => typeof v === 'string' && v)]
      : []
  } else {
    selectedProvider.value = typeof props.modelValue === 'string' ? props.modelValue : ''
  }
  dialog.value = true
  await loadProviders()
}

async function loadProviders() {
  loading.value = true
  try {
    const response = await axios.get('/api/config/provider/list', {
      params: {
        provider_type: props.providerType
      }
    })
    if (response.data.status === 'ok') {
      const providers = response.data.data || []
      providerList.value = props.providerSubtype
        ? providers.filter((provider) => matchesProviderSubtype(provider, props.providerSubtype))
        : providers
    }
  } catch (error) {
    console.error('加载提供商列表失败:', error)
    providerList.value = []
  } finally {
    loading.value = false
  }
}

function matchesProviderSubtype(provider, subtype) {
  if (!subtype) {
    return true
  }
  const normalized = String(subtype).toLowerCase()
  const candidates = [provider.type, provider.provider, provider.id]
    .filter(Boolean)
    .map((value) => String(value).toLowerCase())
  return candidates.includes(normalized)
}

function selectProvider(provider) {
  if (props.multiple) {
    if (!provider.id) {
      selectedProviders.value = []
      return
    }
    const idx = selectedProviders.value.indexOf(provider.id)
    if (idx >= 0) {
      selectedProviders.value.splice(idx, 1)
    } else {
      selectedProviders.value.push(provider.id)
    }
    return
  }
  selectedProvider.value = provider.id
}

function confirmSelection() {
  if (props.multiple) {
    emit('update:modelValue', [...selectedProviders.value])
  } else {
    emit('update:modelValue', selectedProvider.value)
  }
  dialog.value = false
}

function cancelSelection() {
  if (props.multiple) {
    selectedProviders.value = Array.isArray(props.modelValue)
      ? [...props.modelValue.filter((v) => typeof v === 'string' && v)]
      : []
  } else {
    selectedProvider.value = typeof props.modelValue === 'string' ? props.modelValue : ''
  }
  dialog.value = false
}

function isProviderSelected(providerId) {
  if (props.multiple) {
    return selectedProviders.value.includes(providerId)
  }
  return selectedProvider.value === providerId
}

function removeSelected(providerId) {
  const idx = selectedProviders.value.indexOf(providerId)
  if (idx >= 0) {
    selectedProviders.value.splice(idx, 1)
  }
}

function moveSelected(index, delta) {
  const targetIndex = index + delta
  if (
    targetIndex < 0
    || targetIndex >= selectedProviders.value.length
    || index < 0
    || index >= selectedProviders.value.length
  ) {
    return
  }
  const copied = [...selectedProviders.value]
  const [item] = copied.splice(index, 1)
  copied.splice(targetIndex, 0, item)
  selectedProviders.value = copied
}

function openProviderDrawer() {
  providerDrawer.value = true
}

function closeProviderDrawer() {
  providerDrawer.value = false
}
</script>

<style scoped>
.provider-name-text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: calc(100% - 80px);
  display: inline-block;
  font-weight: 500;
}

.selected-preview {
  width: 100%;
}

.selected-order-list {
  background: rgba(var(--v-theme-primary), 0.03);
  border-radius: 12px;
}

.shadow-sm {
  box-shadow: 0 2px 4px rgba(0,0,0,0.05);
}

.v-list-item {
  transition: all 0.2s ease;
}

.v-list-group :deep(.v-list-item--active) {
  color: rgb(var(--v-theme-primary)) !important;
}

.provider-drawer-overlay {
  align-items: stretch;
  justify-content: flex-end;
}

.provider-drawer-card {
  width: clamp(400px, 80vw, 1400px);
  height: 100vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.provider-drawer-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 24px;
}

.provider-drawer-content {
  flex: 1;
  overflow: hidden;
  background: rgb(var(--v-theme-background));
}

.provider-drawer-content > * {
  height: 100%;
  overflow: auto;
}
</style>
