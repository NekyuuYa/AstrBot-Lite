<template>
  <v-autocomplete
    :model-value="modelValue"
    @update:model-value="handleUpdate"
    :items="agentOptions"
    item-title="title"
    item-value="value"
    :label="label || tm('agentSelector.label')"
    :placeholder="tm('agentSelector.placeholder')"
    variant="outlined"
    density="compact"
    hide-details
    clearable
    class="agent-selector"
    :loading="loading"
  >
    <template v-slot:item="{ props, item }">
      <v-list-item v-bind="props" :subtitle="item.raw.description">
        <template v-slot:prepend>
          <v-icon size="small">mdi-robot-outline</v-icon>
        </template>
        <template v-slot:append>
          <v-chip v-if="item.raw.isDefault" size="x-small" color="primary" variant="tonal">Default</v-chip>
        </template>
      </v-list-item>
    </template>
  </v-autocomplete>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import axios from 'axios'
import { useI18n, useModuleI18n } from '@/i18n/composables'

const props = defineProps({
  modelValue: {
    type: String,
    default: ''
  },
  label: {
    type: String,
    default: ''
  }
})

const emit = defineEmits(['update:modelValue'])
const { t } = useI18n()
const { tm } = useModuleI18n('core.shared')

const agents = ref<any[]>([])
const loading = ref(false)

const agentOptions = computed(() => {
  return agents.value.map((a: any) => ({
    title: a.name || a.agent_id,
    value: a.agent_id,
    description: a.agent_id,
    isDefault: a.agent_id === 'sys.default'
  }))
})

async function loadAgents() {
  loading.value = true
  try {
    const res = await axios.get('/api/agents')
    if (res.data.status === 'ok') {
      agents.value = res.data.data
    }
  } catch (error) {
    console.error('Failed to load agents:', error)
  } finally {
    loading.value = false
  }
}

function handleUpdate(value: string) {
  emit('update:modelValue', value)
}

onMounted(loadAgents)
</script>

<style scoped>
.agent-selector {
  width: 100%;
}
</style>
