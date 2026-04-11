<script setup>
import MarketPluginsTab from "./MarketPluginsTab.vue";
import ExtensionGlobalDialogs from "@/components/extension/ExtensionGlobalDialogs.vue";
import { useExtensionPage } from "./useExtensionPage";

const pageState = useExtensionPage();
const {
  tm,
  activeTab,
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

    <!-- 插件管理通用对话框 -->
    <ExtensionGlobalDialogs :state="pageState" />
  </v-container>
</template>
