<template>
  <div class="dialog-option-selector">
    <div class="d-flex align-center justify-space-between ga-3">
      <span class="selector-value" :class="{ 'selector-value--placeholder': !hasSelection }">
        {{ displayText }}
      </span>
      <v-btn size="small" color="primary" variant="tonal" rounded="lg" @click="openDialog">
        {{ buttonText }}
      </v-btn>
    </div>

    <div v-if="multiple && selectedItems.length > 0" class="selected-preview mt-2">
      <v-chip
        v-for="item in selectedItems"
        :key="`chip-${keyForValue(item.value)}`"
        size="x-small"
        color="primary"
        variant="tonal"
        class="mr-1 mb-1"
        label
      >
        {{ item.title }}
      </v-chip>
    </div>

    <div v-if="hint" class="selector-hint mt-1">
      {{ hint }}
    </div>
  </div>

  <v-dialog v-model="dialog" max-width="700px" scrollable>
    <v-card rounded="lg">
      <v-card-title class="d-flex align-center py-4 px-5">
        <span class="text-h3" style="font-weight: 500;">{{ title }}</span>
      </v-card-title>
      <v-divider />
      <v-card-text class="pa-4">
        <v-text-field
          v-if="searchable"
          v-model="keyword"
          :placeholder="searchPlaceholder"
          prepend-inner-icon="mdi-magnify"
          variant="outlined"
          density="comfortable"
          hide-details
          class="mb-3"
        />

        <v-list density="compact" class="selector-list pa-1" bg-color="transparent">
          <v-list-item
            v-if="clearable && !multiple"
            rounded="md"
            class="mb-1"
            :active="singleDraft === null"
            @click="selectItem(null)"
          >
            <template #prepend>
              <v-icon color="grey">mdi-selection-off</v-icon>
            </template>
            <v-list-item-title>{{ clearText }}</v-list-item-title>
            <template #append>
              <v-icon v-if="singleDraft === null" color="primary">mdi-check-circle</v-icon>
            </template>
          </v-list-item>

          <v-list-item
            v-for="item in visibleItems"
            :key="keyForValue(item.value)"
            rounded="md"
            class="mb-1"
            :disabled="item.disabled"
            :active="isSelected(item.value)"
            @click="selectItem(item.value)"
          >
            <v-list-item-title>{{ item.title }}</v-list-item-title>
            <v-list-item-subtitle v-if="item.subtitle">{{ item.subtitle }}</v-list-item-subtitle>
            <template #append>
              <v-icon v-if="isSelected(item.value)" color="primary">
                {{ multiple ? 'mdi-checkbox-marked' : 'mdi-check-circle' }}
              </v-icon>
              <v-icon v-else-if="multiple" color="grey-lighten-1">mdi-checkbox-blank-outline</v-icon>
            </template>
          </v-list-item>

          <div v-if="visibleItems.length === 0" class="py-10 text-center text-medium-emphasis">
            <v-icon size="48" color="grey-lighten-2">mdi-format-list-bulleted-square</v-icon>
            <div class="mt-3">{{ emptyText }}</div>
          </div>
        </v-list>
      </v-card-text>

      <v-divider />

      <v-card-actions class="px-5 py-3">
        <v-spacer />
        <v-btn variant="text" rounded="lg" @click="cancelSelection">
          {{ cancelText }}
        </v-btn>
        <v-btn color="primary" variant="flat" rounded="lg" @click="confirmSelection">
          {{ confirmText }}
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'

type OptionValue = string | number | null

type SelectorItem = {
  title: string
  value: OptionValue
  subtitle?: string
  disabled?: boolean
}

type ModelValue = OptionValue | OptionValue[]

const props = withDefaults(defineProps<{
  modelValue?: ModelValue
  items: SelectorItem[]
  title: string
  buttonText?: string
  hint?: string
  multiple?: boolean
  clearable?: boolean
  searchable?: boolean
  searchPlaceholder?: string
  notSelectedText?: string
  clearText?: string
  emptyText?: string
  selectedCountTemplate?: string
  confirmText?: string
  cancelText?: string
}>(), {
  modelValue: null,
  buttonText: 'Select',
  hint: '',
  multiple: false,
  clearable: false,
  searchable: true,
  searchPlaceholder: 'Search...',
  notSelectedText: 'Not selected',
  clearText: 'Clear selection',
  emptyText: 'No options available',
  selectedCountTemplate: '{count} selected',
  confirmText: 'Confirm',
  cancelText: 'Cancel'
})

const emit = defineEmits<{
  'update:modelValue': [value: ModelValue]
}>()

const dialog = ref(false)
const keyword = ref('')
const singleDraft = ref<OptionValue>(null)
const multipleDraft = ref<OptionValue[]>([])

const normalizedKeyword = computed(() => keyword.value.trim().toLowerCase())

const visibleItems = computed(() => {
  if (!normalizedKeyword.value) {
    return props.items
  }
  return props.items.filter((item) => {
    const title = (item.title || '').toLowerCase()
    const subtitle = (item.subtitle || '').toLowerCase()
    return title.includes(normalizedKeyword.value) || subtitle.includes(normalizedKeyword.value)
  })
})

const selectedItems = computed(() => {
  if (!props.multiple) {
    const selected = props.items.find((item) => isSelected(item.value))
    return selected ? [selected] : []
  }
  return props.items.filter((item) => isSelected(item.value))
})

const hasSelection = computed(() => {
  if (props.multiple) {
    return multipleDraft.value.length > 0
  }
  return singleDraft.value !== null
})

const displayText = computed(() => {
  if (!hasSelection.value) {
    return props.notSelectedText
  }
  if (props.multiple) {
    return props.selectedCountTemplate.replace('{count}', String(multipleDraft.value.length))
  }
  const selected = props.items.find((item) => item.value === singleDraft.value)
  return selected?.title || String(singleDraft.value)
})

watch(
  () => props.modelValue,
  () => {
    syncFromModel()
  },
  { immediate: true, deep: true }
)

function syncFromModel() {
  if (props.multiple) {
    multipleDraft.value = Array.isArray(props.modelValue)
      ? [...props.modelValue]
      : []
    return
  }

  if (Array.isArray(props.modelValue)) {
    singleDraft.value = props.modelValue[0] ?? null
    return
  }
  singleDraft.value = props.modelValue ?? null
}

function openDialog() {
  syncFromModel()
  keyword.value = ''
  dialog.value = true
}

function keyForValue(value: OptionValue) {
  return value === null ? '__null__' : String(value)
}

function isSelected(value: OptionValue) {
  if (props.multiple) {
    return multipleDraft.value.includes(value)
  }
  return singleDraft.value === value
}

function selectItem(value: OptionValue) {
  if (props.multiple) {
    const idx = multipleDraft.value.indexOf(value)
    if (idx >= 0) {
      multipleDraft.value.splice(idx, 1)
    } else {
      multipleDraft.value.push(value)
    }
    return
  }
  singleDraft.value = value
}

function cancelSelection() {
  syncFromModel()
  dialog.value = false
}

function confirmSelection() {
  if (props.multiple) {
    emit('update:modelValue', [...multipleDraft.value])
  } else {
    emit('update:modelValue', singleDraft.value)
  }
  dialog.value = false
}
</script>

<style scoped>
.selector-value {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: calc(100% - 90px);
  font-weight: 500;
}

.selector-value--placeholder {
  color: rgb(var(--v-theme-primaryText));
  font-weight: 400;
}

.selector-hint {
  color: rgba(var(--v-theme-on-surface), 0.62);
  font-size: 12px;
  line-height: 1.45;
}

.selector-list {
  max-height: 420px;
  overflow-y: auto;
}

.v-list-item {
  transition: all 0.15s ease;
}
</style>
