<script setup lang="ts">
import ToolManager from "@/components/extension/componentPanel/ToolManager.vue";
import { useModuleI18n } from '@/i18n/composables';

// 加载 tooluse 特有国际化
const { tm: tmTool } = useModuleI18n('features/tooluse');
</script>

<template>
  <v-container fluid class="pa-0">
    <v-row>
      <v-col cols="12">
        <div class="mb-4 pt-4 pb-4 px-3">
          <div class="d-flex align-center flex-wrap" style="gap: 12px">
            <h2 class="text-h2 mb-0">{{ tmTool("functionTools.title") }}</h2>
          </div>
        </div>

        <v-card variant="flat" class="mx-3 rounded-lg">
          <v-card-text class="pa-4">
            <ToolManager :active="true" />
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>
  </v-container>
</template>

<style scoped>
.text-h2 {
  font-weight: 600;
  font-size: 1.75rem !important;
}
</style>
