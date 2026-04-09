<script setup>
import SkillsSection from "@/components/extension/SkillsSection.vue";
import { useModuleI18n } from '@/i18n/composables';

const { tm } = useModuleI18n("features/extension");
</script>

<template>
  <v-container fluid class="pa-0">
    <v-row>
      <v-col cols="12">
        <div class="mb-4 pt-4 pb-4 px-3">
          <div class="d-flex align-center flex-wrap" style="gap: 12px">
            <h2 class="text-h2 mb-0">{{ tm("tabs.skills") }}</h2>
          </div>
        </div>
        <v-card class="mx-3 rounded-lg" variant="flat" style="background-color: transparent">
          <v-card-text class="pa-0">
            <SkillsSection />
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
