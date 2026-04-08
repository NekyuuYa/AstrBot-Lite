<template>
  <div class="litellm-form">
    <!-- Header -->
    <div class="litellm-form__header">
      <div class="litellm-form__kicker">LiteLLM</div>
      <div class="litellm-form__title">{{ isEditing ? (formData.id || 'Edit Model') : 'Add Model' }}</div>
      <div class="litellm-form__subtitle">Configure a model via LiteLLM unified adapter</div>
    </div>

    <!-- Form -->
    <div class="litellm-form__body">
      <!-- Provider selector -->
      <v-select
        v-model="selectedProvider"
        :items="LITELLM_PROVIDERS"
        item-title="label"
        item-value="value"
        label="Provider"
        variant="solo-filled"
        flat
        density="comfortable"
        prepend-inner-icon="mdi-api"
        hint="Select the LLM provider"
        persistent-hint
        :disabled="isEditing"
        class="mb-1"
      />

      <!-- Common fields: ID + model name -->
      <template v-for="field in COMMON_FIELDS" :key="field.key">
        <v-text-field
          v-model="formData[field.key]"
          :label="field.label"
          :type="field.type === 'password' ? 'password' : 'text'"
          :placeholder="field.placeholder"
          :hint="field.hint"
          :persistent-hint="!!field.hint"
          :required="field.required"
          variant="solo-filled"
          flat
          density="comfortable"
          class="mb-1"
        />
      </template>

      <!-- Provider-specific fields -->
      <template v-if="selectedProvider && providerFields.length > 0">
        <v-divider class="my-3" />
        <div class="litellm-form__section-label">Provider Settings</div>
        <template v-for="field in providerFields" :key="field.key">
          <v-text-field
            v-if="field.type !== 'textarea'"
            v-model="formData[field.key]"
            :label="field.label"
            :type="field.type === 'password' ? 'password' : 'text'"
            :placeholder="field.placeholder"
            :hint="field.hint"
            :persistent-hint="!!field.hint"
            variant="solo-filled"
            flat
            density="comfortable"
            class="mb-1"
          />
          <v-textarea
            v-else
            v-model="formData[field.key]"
            :label="field.label"
            :placeholder="field.placeholder"
            :hint="field.hint"
            :persistent-hint="!!field.hint"
            variant="solo-filled"
            flat
            density="comfortable"
            rows="3"
            class="mb-1"
          />
        </template>
      </template>

      <!-- Extra params (JSON) -->
      <v-divider class="my-3" />
      <div class="litellm-form__section-label">Extra Parameters</div>
      <v-textarea
        v-model="extraParamsText"
        label="Extra Params (JSON)"
        variant="solo-filled"
        flat
        density="comfortable"
        rows="3"
        hint="Optional JSON object passed directly to LiteLLM (e.g. {&quot;temperature&quot;: 0.7})"
        persistent-hint
        :error-messages="extraParamsError"
        class="mb-1"
        placeholder="{}"
      />

      <!-- Enable toggle -->
      <v-divider class="my-3" />
      <v-switch
        v-model="formData.enable"
        label="Enable this model"
        color="primary"
        density="comfortable"
        hide-details
      />
    </div>

    <!-- Actions -->
    <div class="litellm-form__actions">
      <v-btn variant="text" @click="$emit('cancel')" :disabled="loading">Cancel</v-btn>
      <v-spacer />
      <v-btn
        color="primary"
        variant="tonal"
        :loading="loading"
        :disabled="!canSubmit"
        prepend-icon="mdi-content-save-outline"
        @click="submit"
      >
        {{ isEditing ? 'Save Changes' : 'Add Model' }}
      </v-btn>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import axios from 'axios'
import {
  LITELLM_PROVIDERS,
  COMMON_FIELDS,
  PROVIDER_FIELDS,
  parseLiteLLMProvider,
  parseLiteLLMModel,
} from '@/utils/litellmProviders'

interface Props {
  /** Existing provider config to edit. Leave undefined for "add" mode. */
  existingProvider?: Record<string, any> | null
}

const props = withDefaults(defineProps<Props>(), {
  existingProvider: null,
})

const emit = defineEmits<{
  (e: 'saved'): void
  (e: 'cancel'): void
}>()

const loading = ref(false)

const isEditing = computed(() => !!props.existingProvider)

const selectedProvider = ref<string>('')
const formData = ref<Record<string, any>>({
  id: '',
  model_name: '',
  api_key: '',
  api_base: '',
  enable: true,
})
const extraParamsText = ref('{}')
const extraParamsError = ref('')

const providerFields = computed(() => {
  if (!selectedProvider.value) return []
  return PROVIDER_FIELDS[selectedProvider.value] || []
})

const canSubmit = computed(() => {
  if (!selectedProvider.value) return false
  const id = (formData.value.id || '').trim()
  const model = (formData.value.model_name || '').trim()
  if (!id || !model) return false
  // check required provider fields
  for (const field of providerFields.value) {
    if (field.required && !(formData.value[field.key] || '').trim()) return false
  }
  return true
})

/** Populate form from existingProvider on mount/change */
function loadFromExisting() {
  if (!props.existingProvider) {
    resetForm()
    return
  }
  const p = props.existingProvider
  selectedProvider.value = parseLiteLLMProvider(p.model || '')
  formData.value = {
    id: p.id || '',
    model_name: parseLiteLLMModel(p.model || ''),
    api_key: p.api_key || '',
    api_base: p.api_base || '',
    api_version: p.api_version || '',
    enable: p.enable !== false,
  }
  // copy any extra provider-specific fields
  const allProviderFieldKeys = Object.values(PROVIDER_FIELDS)
    .flat()
    .map((f) => f.key)
  for (const key of allProviderFieldKeys) {
    if (p[key] !== undefined) {
      formData.value[key] = p[key]
    }
  }
  extraParamsText.value = p.extra_params
    ? JSON.stringify(p.extra_params, null, 2)
    : '{}'
  extraParamsError.value = ''
}

function resetForm() {
  selectedProvider.value = ''
  formData.value = { id: '', model_name: '', api_key: '', api_base: '', enable: true }
  extraParamsText.value = '{}'
  extraParamsError.value = ''
}

watch(() => props.existingProvider, loadFromExisting, { immediate: true })

// Clear provider-specific fields when provider changes (add mode only)
watch(selectedProvider, (newProvider, oldProvider) => {
  if (isEditing.value) return
  if (!oldProvider) return
  // remove old provider fields
  const oldFields = PROVIDER_FIELDS[oldProvider] || []
  for (const f of oldFields) {
    delete formData.value[f.key]
  }
})

async function submit() {
  extraParamsError.value = ''
  let extra_params: Record<string, any> = {}
  try {
    const text = (extraParamsText.value || '').trim() || '{}'
    extra_params = JSON.parse(text)
    if (typeof extra_params !== 'object' || Array.isArray(extra_params)) {
      throw new Error('Must be a JSON object')
    }
  } catch (e: any) {
    extraParamsError.value = `Invalid JSON: ${e.message}`
    return
  }

  const modelString = `${selectedProvider.value}/${(formData.value.model_name || '').trim()}`

  const payload: Record<string, any> = {
    id: (formData.value.id || '').trim(),
    type: 'litellm_chat_completion',
    enable: formData.value.enable !== false,
    model: modelString,
    api_key: formData.value.api_key || '',
    api_base: formData.value.api_base || '',
    extra_params,
  }

  // include provider-specific fields
  for (const f of providerFields.value) {
    if (f.key !== 'api_key' && f.key !== 'api_base') {
      payload[f.key] = formData.value[f.key] || ''
    }
  }

  loading.value = true
  try {
    if (isEditing.value) {
      const originalId = props.existingProvider!.id
      const res = await axios.post('/api/config/provider/update', {
        id: originalId,
        config: payload,
      })
      if (res.data.status === 'error') throw new Error(res.data.message)
    } else {
      const res = await axios.post('/api/config/provider/new', payload)
      if (res.data.status === 'error') throw new Error(res.data.message)
    }
    emit('saved')
  } catch (e: any) {
    extraParamsError.value = e.response?.data?.message || e.message || 'Request failed'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.litellm-form {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.litellm-form__header {
  padding: 20px 20px 16px;
  border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.1);
  flex-shrink: 0;
}

.litellm-form__kicker {
  color: rgba(var(--v-theme-on-surface), 0.56);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.litellm-form__title {
  margin-top: 8px;
  font-size: 22px;
  font-weight: 650;
  letter-spacing: -0.03em;
  line-height: 1.1;
  overflow-wrap: anywhere;
}

.litellm-form__subtitle {
  margin-top: 6px;
  font-size: 13px;
  color: rgba(var(--v-theme-on-surface), 0.68);
}

.litellm-form__body {
  flex: 1;
  overflow-y: auto;
  padding: 18px 20px;
}

.litellm-form__section-label {
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: rgba(var(--v-theme-on-surface), 0.56);
  margin-bottom: 10px;
}

.litellm-form__actions {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 20px;
  border-top: 1px solid rgba(var(--v-theme-on-surface), 0.1);
  flex-shrink: 0;
}
</style>
