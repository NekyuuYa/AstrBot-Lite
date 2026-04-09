<script setup>
import InstalledPluginsTab from "./InstalledPluginsTab.vue";
import { useExtensionPage } from "./useExtensionPage";
import AstrBotConfig from "@/components/shared/AstrBotConfig.vue";
import ConsoleDisplayer from "@/components/shared/ConsoleDisplayer.vue";
import ReadmeDialog from "@/components/shared/ReadmeDialog.vue";
import UninstallConfirmDialog from "@/components/shared/UninstallConfirmDialog.vue";

const pageState = useExtensionPage();
const {
  tm,
  activeTab,
  snack_message,
  snack_show,
  snack_success,
  configDialog,
  extension_config,
  curr_namespace,
  loadingDialog,
  resetLoadingDialog,
  showPluginInfoDialog,
  selectedPlugin,
  plugin_handler_info_headers,
  readmeDialog,
  changelogDialog,
  showUninstallDialog,
  handleUninstallConfirm,
  updateAllConfirmDialog,
  updatableExtensions,
  cancelUpdateAll,
  confirmUpdateAll,
  conflictDialog,
  handleConflictConfirm,
  updateConfig,
  viewReadme,
  showPluginInfo,
} = pageState;

// 强制设置当前 Tab 为 installed，避免逻辑干扰
activeTab.value = 'installed';
</script>

<template>
  <v-container fluid class="pa-0">
    <v-row class="extension-page">
      <v-col cols="12">
        <v-card variant="flat" style="background-color: transparent">
          <v-card-text style="padding: 0px 12px">
            <InstalledPluginsTab :state="pageState" />
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- 公用对话框组件 -->
    <v-snackbar :timeout="2000" elevation="24" :color="snack_success" v-model="snack_show" location="bottom center">
      {{ snack_message }}
    </v-snackbar>

    <v-dialog v-model="configDialog" max-width="900">
      <v-card>
        <v-card-title class="text-h2 pa-4 pl-6 pb-0">{{ tm("dialogs.config.title") }}</v-card-title>
        <v-card-text>
          <div style="max-height: 60vh; overflow-y: auto; padding-right: 8px">
            <AstrBotConfig v-if="extension_config.metadata" :metadata="extension_config.metadata" :iterable="extension_config.config" :metadataKey="curr_namespace" :pluginName="curr_namespace" />
            <p v-else>{{ tm("dialogs.config.noConfig") }}</p>
          </div>
        </v-card-text>
        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn color="blue-darken-1" variant="text" @click="updateConfig">{{ tm("buttons.saveAndClose") }}</v-btn>
          <v-btn color="blue-darken-1" variant="text" @click="configDialog = false">{{ tm("buttons.close") }}</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <v-dialog v-model="loadingDialog.show" width="700" persistent>
      <v-card>
        <v-card-title class="text-h5">{{ loadingDialog.title }}</v-card-title>
        <v-card-text style="max-height: calc(100vh - 200px); overflow-y: auto">
          <v-progress-linear v-if="loadingDialog.statusCode === 0" indeterminate color="primary" class="mb-4"></v-progress-linear>
          <div v-if="loadingDialog.statusCode !== 0" class="py-8 text-center">
            <v-icon class="mb-6" :color="loadingDialog.statusCode === 1 ? 'success' : 'error'" :icon="loadingDialog.statusCode === 1 ? 'mdi-check-circle-outline' : 'mdi-alert-circle-outline'" size="128"></v-icon>
            <div class="text-h4 font-weight-bold">{{ loadingDialog.result }}</div>
          </div>
          <div style="margin-top: 32px">
            <h3>{{ tm("dialogs.loading.logs") }}</h3>
            <ConsoleDisplayer historyNum="10" style="height: 200px; margin-top: 16px; margin-bottom: 24px"></ConsoleDisplayer>
          </div>
        </v-card-text>
        <v-divider></v-divider>
        <v-card-actions class="pa-4">
          <v-spacer></v-spacer>
          <v-btn color="blue-darken-1" variant="text" @click="resetLoadingDialog">{{ tm("buttons.close") }}</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <v-dialog v-model="showPluginInfoDialog" width="1200">
      <v-card>
        <v-card-title class="text-h5">{{ selectedPlugin.name }} {{ tm("buttons.viewInfo") }}</v-card-title>
        <v-card-text>
          <v-data-table style="font-size: 17px" :headers="plugin_handler_info_headers" :items="selectedPlugin.handlers" item-key="name">
            <template v-slot:item.type="{ item }"><v-chip color="success">{{ item.type }}</v-chip></template>
            <template v-slot:item.cmd="{ item }"><span style="font-weight: bold">{{ item.cmd }}</span></template>
          </v-data-table>
        </v-card-text>
        <v-card-actions><v-spacer></v-spacer><v-btn color="blue-darken-1" variant="text" @click="showPluginInfoDialog = false">{{ tm("buttons.close") }}</v-btn></v-card-actions>
      </v-card>
    </v-dialog>

    <ReadmeDialog v-model:show="readmeDialog.show" :plugin-name="readmeDialog.pluginName" :repo-url="readmeDialog.repoUrl" />
    <ReadmeDialog v-model:show="changelogDialog.show" :plugin-name="changelogDialog.pluginName" :repo-url="changelogDialog.repoUrl" mode="changelog" />
    <UninstallConfirmDialog v-model="showUninstallDialog" @confirm="handleUninstallConfirm" />

    <v-dialog v-model="updateAllConfirmDialog.show" max-width="420">
      <v-card class="rounded-lg">
        <v-card-title class="d-flex align-center pa-4"><v-icon color="warning" class="mr-2">mdi-update</v-icon>{{ tm("dialogs.updateAllConfirm.title") }}</v-card-title>
        <v-card-text><p class="text-body-1">{{ tm("dialogs.updateAllConfirm.message", { count: updatableExtensions.length }) }}</p></v-card-text>
        <v-card-actions class="pa-4"><v-spacer></v-spacer><v-btn variant="text" @click="cancelUpdateAll">{{ tm("buttons.cancel") }}</v-btn><v-btn color="warning" variant="flat" @click="confirmUpdateAll">{{ tm("dialogs.updateAllConfirm.confirm") }}</v-btn></v-card-actions>
      </v-card>
    </v-dialog>

    <v-dialog v-model="conflictDialog.show" max-width="420">
      <v-card class="rounded-lg">
        <v-card-title class="d-flex align-center pa-4"><v-icon color="warning" class="mr-2">mdi-alert-circle</v-icon>{{ tm("conflicts.title") }}</v-card-title>
        <v-card-text class="px-4 pb-2">
          <div class="d-flex align-center mb-3"><v-chip color="warning" variant="tonal" size="large" class="font-weight-bold">{{ conflictDialog.count }}</v-chip><span class="ml-2 text-body-1">{{ tm("conflicts.pairs") }}</span></div>
          <p class="text-body-2" style="color: rgba(var(--v-theme-on-surface), 0.7)">{{ tm("conflicts.message") }}</p>
        </v-card-text>
        <v-card-actions class="pa-4 pt-2"><v-spacer></v-spacer><v-btn variant="text" @click="conflictDialog.show = false">{{ tm("conflicts.later") }}</v-btn><v-btn color="warning" variant="flat" @click="handleConflictConfirm">{{ tm("conflicts.goToManage") }}</v-btn></v-card-actions>
      </v-card>
    </v-dialog>
  </v-container>
</template>
