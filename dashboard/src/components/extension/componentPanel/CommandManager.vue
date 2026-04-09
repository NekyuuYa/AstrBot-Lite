<script setup lang="ts">
import { onMounted, watch } from 'vue';
import { useModuleI18n } from '@/i18n/composables';

// Composables
import { useCommandData } from './composables/useCommandData';
import { useCommandFilters } from './composables/useCommandFilters';
import { useCommandActions } from './composables/useCommandActions';

// Components
import CommandFilters from './components/CommandFilters.vue';
import CommandTable from './components/CommandTable.vue';
import RenameDialog from './components/RenameDialog.vue';
import DetailsDialog from './components/DetailsDialog.vue';

// Types
import type { CommandItem } from './types';

defineOptions({ name: 'CommandManager' });
const props = withDefaults(defineProps<{ active?: boolean }>(), {
  active: true
});

const { tm } = useModuleI18n('features/command');

// 数据管理
const { 
  loading, 
  commands, 
  summary, 
  snackbar, 
  toast, 
  fetchCommands
} = useCommandData();

// 过滤逻辑
const {
  searchQuery,
  pluginFilter,
  permissionFilter,
  statusFilter,
  typeFilter,
  showSystemPlugins,
  expandedGroups,
  hasSystemPluginConflict,
  effectiveShowSystemPlugins,
  availablePlugins,
  filteredCommands,
  toggleGroupExpand
} = useCommandFilters(commands);

// 操作方法
const {
  renameDialog,
  detailsDialog,
  toggleCommand,
  updatePermission,
  openRenameDialog,
  confirmRename,
  openDetailsDialog
} = useCommandActions(toast, () => fetchCommands(tm('messages.loadFailed')));

// 处理切换指令状态
const handleToggleCommand = async (cmd: CommandItem) => {
  await toggleCommand(cmd, tm('messages.toggleSuccess'), tm('messages.toggleFailed'));
};

const handleUpdatePermission = async (cmd: CommandItem, permission: 'admin' | 'member') => {
  await updatePermission(cmd, permission, tm('messages.updateSuccess'), tm('messages.updateFailed'));
};

// 处理确认重命名
const handleConfirmRename = async () => {
  await confirmRename(tm('messages.renameSuccess'), tm('messages.renameFailed'));
};

// 生命周期
onMounted(async () => {
  await fetchCommands(tm('messages.loadFailed'));
});

watch(() => props.active, async (isActive) => {
  if (isActive) {
    await fetchCommands(tm('messages.loadFailed'));
  }
});
</script>

<template>
  <v-card variant="flat" style="background-color: transparent">
    <v-card-text style="padding: 0px;">
      <CommandFilters
        :plugin-filter="pluginFilter"
        @update:plugin-filter="pluginFilter = $event"
        :type-filter="typeFilter"
        @update:type-filter="typeFilter = $event"
        :permission-filter="permissionFilter"
        @update:permission-filter="permissionFilter = $event"
        :status-filter="statusFilter"
        @update:status-filter="statusFilter = $event"
        :show-system-plugins="showSystemPlugins"
        @update:show-system-plugins="showSystemPlugins = $event"
        :search-query="searchQuery"
        @update:search-query="searchQuery = $event"
        :available-plugins="availablePlugins"
        :has-system-plugin-conflict="hasSystemPluginConflict"
        :effective-show-system-plugins="effectiveShowSystemPlugins"
      >
        <template #stats>
          <div class="d-flex align-center">
            <v-icon size="18" color="primary" class="mr-1">mdi-console-line</v-icon>
            <span class="text-body-2 text-medium-emphasis mr-1">{{ tm('summary.total') }}:</span>
            <span class="text-body-1 font-weight-bold text-primary">{{ filteredCommands.length }}</span>
          </div>
          <v-divider vertical class="mx-1" style="height: 20px;" />
          <div class="d-flex align-center">
            <v-icon size="18" color="error" class="mr-1">mdi-close-circle-outline</v-icon>
            <span class="text-body-2 text-medium-emphasis mr-1">{{ tm('summary.disabled') }}:</span>
            <span class="text-body-1 font-weight-bold text-error">{{ summary.disabled }}</span>
          </div>
        </template>
      </CommandFilters>
      
      <v-alert
        v-if="summary.conflicts > 0"
        type="error"
        variant="tonal"
        class="mb-4"
        prominent
        border="start"
      >
        <template v-slot:prepend>
          <v-icon size="28">mdi-alert-circle</v-icon>
        </template>
        <v-alert-title class="text-subtitle-1 font-weight-bold">
          {{ tm('conflictAlert.title') }}
        </v-alert-title>
        <div class="text-body-2 mt-1">
          {{ tm('conflictAlert.description', { count: summary.conflicts }) }}
        </div>
        <div class="text-body-2 mt-2">
          <v-icon size="16" class="mr-1">mdi-lightbulb-outline</v-icon>
          {{ tm('conflictAlert.hint') }}
        </div>
      </v-alert>

      <CommandTable
        :items="filteredCommands"
        :expanded-groups="expandedGroups"
        :loading="loading"
        @toggle-expand="toggleGroupExpand"
        @toggle-command="handleToggleCommand"
        @rename="openRenameDialog"
        @view-details="openDetailsDialog"
        @update-permission="handleUpdatePermission"
      />
    </v-card-text>
  </v-card>

  <!-- 重命名对话框 -->
  <RenameDialog
    :show="renameDialog.show"
    @update:show="renameDialog.show = $event"
    :new-name="renameDialog.newName"
    @update:new-name="renameDialog.newName = $event"
    :aliases="renameDialog.aliases"
    @update:aliases="renameDialog.aliases = $event"
    :command="renameDialog.command"
    :loading="renameDialog.loading"
    @confirm="handleConfirmRename"
  />

  <!-- 详情对话框 -->
  <DetailsDialog
    :show="detailsDialog.show"
    @update:show="detailsDialog.show = $event"
    :command="detailsDialog.command"
  />

  <!-- Snackbar -->
  <v-snackbar :timeout="2000" elevation="24" :color="snackbar.color" v-model="snackbar.show">
    {{ snackbar.message }}
  </v-snackbar>
</template>
