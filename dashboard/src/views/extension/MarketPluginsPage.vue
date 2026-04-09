<script setup>
import MarketPluginsTab from "./MarketPluginsTab.vue";
import { useExtensionPage } from "./useExtensionPage";
import AstrBotConfig from "@/components/shared/AstrBotConfig.vue";
import ConsoleDisplayer from "@/components/shared/ConsoleDisplayer.vue";
import ReadmeDialog from "@/components/shared/ReadmeDialog.vue";
import ProxySelector from "@/components/shared/ProxySelector.vue";

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
  readmeDialog,
  changelogDialog,
  updateConfig,
  dangerConfirmDialog,
  cancelDangerInstall,
  confirmDangerInstall,
  versionCompatibilityDialog,
  cancelInstallOnVersionWarning,
  continueInstallIgnoringVersionWarning,
  dialog,
  loading_,
  uploadTab,
  upload_file,
  fileInput,
  extension_url,
  selectedInstallPlugin,
  normalizePlatformList,
  getPlatformDisplayList,
  installCompat,
  newExtension,
  showSourceManagerDialog,
  selectedSource,
  selectPluginSource,
  sourceSelectItems,
  addCustomSource,
  customSources,
  editCustomSource,
  removeCustomSource,
  showSourceDialog,
  editingSource,
  sourceName,
  sourceUrl,
  saveCustomSource,
  showRemoveSourceDialog,
  sourceToRemove,
  confirmRemoveSource,
  forceUpdateDialog,
  confirmForceUpdate,
} = pageState;

// 强制设置当前 Tab 为 market
activeTab.value = 'market';
</script>

<template>
  <v-container fluid class="pa-0">
    <v-row class="extension-page">
      <v-col cols="12">
        <v-card variant="flat" style="background-color: transparent">
          <v-card-text style="padding: 0px 12px">
            <MarketPluginsTab :state="pageState" />
          </v-card-text>
        </v-card>
      </v-col>

      <v-col cols="12">
        <div class="d-flex align-center justify-center mt-4 mb-4 gap-4">
          <v-btn variant="text" prepend-icon="mdi-book-open-variant" href="https://docs.astrbot.app/dev/star/plugin-new.html" target="_blank" color="primary" class="text-none">
            {{ tm("market.devDocs") }}
          </v-btn>
          <div style="height: 24px; width: 1px; background-color: rgba(var(--v-theme-on-surface), 0.12);"></div>
          <v-btn variant="text" prepend-icon="mdi-github" href="https://github.com/AstrBotDevs/AstrBot_Plugins_Collection" target="_blank" color="primary" class="text-none">
            {{ tm("market.submitRepo") }}
          </v-btn>
        </div>
      </v-col>
    </v-row>

    <!-- 市场相关对话框 -->
    <v-snackbar :timeout="2000" elevation="24" :color="snack_success" v-model="snack_show" location="bottom center">
      {{ snack_message }}
    </v-snackbar>

    <v-dialog v-model="dialog" width="500">
      <div class="v-card v-card--density-default rounded-lg v-card--variant-elevated">
        <div class="v-card__loader"><v-progress-linear :indeterminate="loading_" color="primary" height="2" :active="loading_"></v-progress-linear></div>
        <v-card-title class="text-h3 pa-4 pb-0 pl-6">{{ tm("dialogs.install.title") }}</v-card-title>
        <div class="v-card-text">
          <v-tabs v-model="uploadTab" color="primary"><v-tab value="file">{{ tm("dialogs.install.fromFile") }}</v-tab><v-tab value="url">{{ tm("dialogs.install.fromUrl") }}</v-tab></v-tabs>
          <v-window v-model="uploadTab" class="mt-4">
            <v-window-item value="file">
              <div class="d-flex flex-column align-center justify-center pa-4">
                <v-file-input ref="fileInput" v-model="upload_file" :label="tm('upload.selectFile')" accept=".zip" hide-details hide-input class="d-none"></v-file-input>
                <v-btn color="primary" size="large" prepend-icon="mdi-upload" @click="$refs.fileInput.click()" elevation="2">{{ tm("buttons.selectFile") }}</v-btn>
                <div class="text-body-2 text-medium-emphasis mt-2">{{ tm("messages.supportedFormats") }}</div>
                <div v-if="upload_file" class="mt-4 text-center"><v-chip color="primary" size="large" closable @click:close="upload_file = null">{{ upload_file.name }}<template v-slot:append><span class="text-caption ml-2">({{ (upload_file.size / 1024).toFixed(1) }}KB)</span></template></v-chip></div>
              </div>
            </v-window-item>
            <v-window-item value="url">
              <div class="pa-4">
                <v-text-field v-model="extension_url" :label="tm('upload.enterUrl')" variant="outlined" prepend-inner-icon="mdi-link" hide-details class="rounded-lg mb-4" placeholder="https://github.com/username/repo"></v-text-field>
                <div v-if="selectedInstallPlugin" class="mb-3">
                  <v-chip v-if="selectedInstallPlugin.astrbot_version" size="small" color="secondary" variant="outlined" class="mr-2 mb-2">{{ tm("card.status.astrbotVersion") }}: {{ selectedInstallPlugin.astrbot_version }}</v-chip>
                  <v-chip v-if="normalizePlatformList(selectedInstallPlugin.support_platforms).length" size="small" color="info" variant="outlined" class="mb-2">{{ tm("card.status.supportPlatform") }}: {{ getPlatformDisplayList(selectedInstallPlugin.support_platforms).join(", ") }}</v-chip>
                  <v-alert v-if="selectedInstallPlugin.astrbot_version && installCompat.checked && !installCompat.compatible" type="warning" variant="tonal" density="comfortable" class="mt-2">{{ installCompat.message }}</v-alert>
                </div>
                <ProxySelector></ProxySelector>
              </div>
            </v-window-item>
          </v-window>
        </div>
        <div class="v-card-actions"><v-spacer></v-spacer><v-btn color="grey" variant="text" @click="dialog = false">{{ tm("buttons.cancel") }}</v-btn><v-btn color="primary" variant="text" @click="newExtension">{{ tm("buttons.install") }}</v-btn></div>
      </div>
    </v-dialog>

    <v-dialog v-model="dangerConfirmDialog" width="500" persistent>
      <v-card>
        <v-card-title class="text-h5 d-flex align-center"><v-icon color="warning" class="mr-2">mdi-alert-circle</v-icon>{{ tm("dialogs.danger_warning.title") }}</v-card-title>
        <v-card-text><div>{{ tm("dialogs.danger_warning.message") }}</div></v-card-text>
        <v-card-actions><v-spacer></v-spacer><v-btn color="grey" @click="cancelDangerInstall">{{ tm("dialogs.danger_warning.cancel") }}</v-btn><v-btn color="warning" @click="confirmDangerInstall">{{ tm("dialogs.danger_warning.confirm") }}</v-btn></v-card-actions>
      </v-card>
    </v-dialog>

    <v-dialog v-model="versionCompatibilityDialog.show" width="520" persistent>
      <v-card>
        <v-card-title class="text-h5 d-flex align-center"><v-icon color="warning" class="mr-2">mdi-alert</v-icon>{{ tm("dialogs.versionCompatibility.title") }}</v-card-title>
        <v-card-text><div class="mb-2">{{ tm("dialogs.versionCompatibility.message") }}</div><div class="text-medium-emphasis">{{ versionCompatibilityDialog.message }}</div></v-card-text>
        <v-card-actions><v-spacer></v-spacer><v-btn color="grey" @click="cancelInstallOnVersionWarning">{{ tm("dialogs.versionCompatibility.cancel") }}</v-btn><v-btn color="warning" @click="continueInstallIgnoringVersionWarning">{{ tm("dialogs.versionCompatibility.confirm") }}</v-btn></v-card-actions>
      </v-card>
    </v-dialog>

    <v-dialog v-model="showSourceManagerDialog" width="640">
      <v-card>
        <v-card-title class="text-h3 pa-4 pl-6">{{ tm("market.sourceManagement") }}</v-card-title>
        <v-card-text>
          <v-select :model-value="selectedSource || '__default__'" @update:model-value="selectPluginSource($event === '__default__' ? null : $event)" :items="sourceSelectItems" :label="tm('market.currentSource')" variant="outlined" prepend-inner-icon="mdi-source-branch" hide-details class="mb-4"></v-select>
          <div class="d-flex align-center justify-space-between mb-2"><div class="text-subtitle-2">{{ tm("market.availableSources") }}</div><v-btn size="small" color="primary" variant="tonal" prepend-icon="mdi-plus" @click="addCustomSource">{{ tm("market.addSource") }}</v-btn></div>
          <v-list density="compact" nav class="pa-0">
            <v-list-item rounded="md" color="primary" :active="selectedSource === null" @click="selectPluginSource(null)"><template v-slot:prepend><v-icon icon="mdi-shield-check" size="small" class="mr-2"></v-icon></template><v-list-item-title>{{ tm("market.defaultSource") }}</v-list-item-title></v-list-item>
            <v-list-item v-for="source in customSources" :key="source.url" rounded="md" color="primary" :active="selectedSource === source.url" @click="selectPluginSource(source.url)"><template v-slot:prepend><v-icon icon="mdi-link-variant" size="small" class="mr-2"></v-icon></template><v-list-item-title>{{ source.name }}</v-list-item-title><v-list-item-subtitle class="text-caption">{{ source.url }}</v-list-item-subtitle><template v-slot:append><v-btn icon="mdi-pencil-outline" size="small" variant="text" color="medium-emphasis" @click.stop="editCustomSource(source)"></v-btn><v-btn icon="mdi-trash-can-outline" size="small" variant="text" color="error" @click.stop="removeCustomSource(source)"></v-btn></template></v-list-item>
          </v-list>
        </v-card-text>
        <v-card-actions><v-spacer></v-spacer><v-btn color="primary" variant="text" @click="showSourceManagerDialog = false">{{ tm("buttons.close") }}</v-btn></v-card-actions>
      </v-card>
    </v-dialog>

    <v-dialog v-model="showSourceDialog" width="500">
      <v-card>
        <v-card-title class="text-h5">{{ editingSource ? tm("market.editSource") : tm("market.addSource") }}</v-card-title>
        <v-card-text><div class="pa-2"><v-text-field v-model="sourceName" :label="tm('market.sourceName')" variant="outlined" prepend-inner-icon="mdi-rename-box" hide-details class="mb-4" placeholder="我的插件源"></v-text-field><v-text-field v-model="sourceUrl" :label="tm('market.sourceUrl')" variant="outlined" prepend-inner-icon="mdi-link" hide-details placeholder="https://example.com/plugins.json"></v-text-field><div class="text-caption text-medium-emphasis mt-2">{{ tm("messages.enterJsonUrl") }}</div></div></v-card-text>
        <v-card-actions><v-spacer></v-spacer><v-btn color="grey" variant="text" @click="showSourceDialog = false">{{ tm("buttons.cancel") }}</v-btn><v-btn color="primary" variant="text" @click="saveCustomSource">{{ tm("buttons.save") }}</v-btn></v-card-actions>
      </v-card>
    </v-dialog>

    <v-dialog v-model="showRemoveSourceDialog" width="400">
      <v-card>
        <v-card-title class="text-h5 d-flex align-center"><v-icon color="warning" class="mr-2">mdi-alert-circle</v-icon>{{ tm("dialogs.uninstall.title") }}</v-card-title>
        <v-card-text><div>{{ tm("market.confirmRemoveSource") }}</div><div v-if="sourceToRemove" class="mt-2"><strong>{{ sourceToRemove.name }}</strong><div class="text-caption">{{ sourceToRemove.url }}</div></div></v-card-text>
        <v-card-actions><v-spacer></v-spacer><v-btn color="grey" variant="text" @click="showRemoveSourceDialog = false">{{ tm("buttons.cancel") }}</v-btn><v-btn color="error" variant="text" @click="confirmRemoveSource">{{ tm("buttons.deleteSource") }}</v-btn></v-card-actions>
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
        <v-card-actions class="pa-4"><v-spacer></v-spacer><v-btn color="blue-darken-1" variant="text" @click="resetLoadingDialog">{{ tm("buttons.close") }}</v-btn></v-card-actions>
      </v-card>
    </v-dialog>

    <ReadmeDialog v-model:show="readmeDialog.show" :plugin-name="readmeDialog.pluginName" :repo-url="readmeDialog.repoUrl" />
    <ReadmeDialog v-model:show="changelogDialog.show" :plugin-name="changelogDialog.pluginName" :repo-url="changelogDialog.repoUrl" mode="changelog" />
  </v-container>
</template>
