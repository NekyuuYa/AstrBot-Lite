<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import axios from 'axios';
import { useModuleI18n } from '@/i18n/composables';
import { normalizeTextInput } from '@/utils/inputValue';

// Composables
import { useToolData } from './composables/useToolData';

// Components
import ToolTable from './components/ToolTable.vue';

// Types
import type { ToolItem } from './types';

defineOptions({ name: 'ToolManager' });
const props = withDefaults(defineProps<{ active?: boolean }>(), {
  active: true
});

const { tm: tmTool } = useModuleI18n('features/tooluse');
const toolSearch = ref('');

// 数据管理
const { 
  tools,
  toolsLoading,
  snackbar, 
  toast, 
  fetchTools 
} = useToolData();

const filteredTools = computed(() => {
  const query = normalizeTextInput(toolSearch.value).trim().toLowerCase();
  if (!query) return tools.value;
  return tools.value.filter(tool => 
    tool.name?.toLowerCase().includes(query) ||
    tool.description?.toLowerCase().includes(query)
  );
});

const handleToggleTool = async (tool: ToolItem) => {
  if (tool.readonly) {
    toast(tmTool('messages.toggleToolReadonly'), 'info');
    return;
  }
  const previous = tool.active;
  tool.active = !tool.active;
  try {
    const res = await axios.post('/api/tools/toggle-tool', {
      name: tool.name,
      activate: tool.active
    });
    if (res.data.status === 'ok') {
      toast(res.data.message || tmTool('messages.toggleToolSuccess'));
    } else {
      tool.active = previous;
      toast(res.data.message || tmTool('messages.toggleToolError', { error: '' }), 'error');
    }
  } catch (error: any) {
    tool.active = previous;
    toast(error?.response?.data?.message || error?.message || tmTool('messages.toggleToolError', { error: '' }), 'error');
  }
};

// 生命周期
onMounted(async () => {
  await fetchTools(tmTool('messages.getToolsError', { error: '' }));
});

watch(() => props.active, async (isActive) => {
  if (isActive) {
    await fetchTools(tmTool('messages.getToolsError', { error: '' }));
  }
});
</script>

<template>
  <v-card variant="flat" style="background-color: transparent">
    <v-card-text style="padding: 0px;">
      <div class="d-flex flex-wrap align-center ga-3 mb-4">
        <div style="min-width: 240px; max-width: 380px; flex: 1;">
          <v-text-field
            :model-value="toolSearch"
            @update:model-value="toolSearch = normalizeTextInput($event)"
            prepend-inner-icon="mdi-magnify"
            :label="tmTool('functionTools.search')"
            variant="outlined"
            density="compact"
            hide-details
            clearable
          />
        </div>
      </div>

      <ToolTable
        :items="filteredTools"
        :loading="toolsLoading"
        @toggle-tool="handleToggleTool"
      />
    </v-card-text>
  </v-card>

  <!-- Snackbar -->
  <v-snackbar :timeout="2000" elevation="24" :color="snackbar.color" v-model="snackbar.show">
    {{ snackbar.message }}
  </v-snackbar>
</template>
