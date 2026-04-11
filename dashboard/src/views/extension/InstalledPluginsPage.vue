<script setup>
import InstalledPluginsTab from "./InstalledPluginsTab.vue";
import ExtensionGlobalDialogs from "@/components/extension/ExtensionGlobalDialogs.vue";
import { useExtensionPage } from "./useExtensionPage";

const pageState = useExtensionPage();
const { activeTab } = pageState;

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

    <!-- 插件管理通用对话框 -->
    <ExtensionGlobalDialogs :state="pageState" />
  </v-container>
</template>
