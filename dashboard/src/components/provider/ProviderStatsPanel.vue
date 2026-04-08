<template>
  <div class="stats-panel">
    <div class="stats-panel__header">
      <div class="stats-panel__title">
        <v-icon start size="20" color="primary">mdi-chart-bar</v-icon>
        Usage Statistics
      </div>
      <div class="stats-panel__controls">
        <v-btn-toggle v-model="selectedDays" mandatory density="compact" variant="outlined" rounded="lg">
          <v-btn :value="1" size="small">1d</v-btn>
          <v-btn :value="7" size="small">7d</v-btn>
          <v-btn :value="30" size="small">30d</v-btn>
        </v-btn-toggle>
        <v-btn icon="mdi-refresh" size="small" variant="text" :loading="loadingSummary" @click="reload" />
      </div>
    </div>

    <!-- Summary KPI cards -->
    <v-row class="mt-0 mb-2 mx-0" dense>
      <v-col cols="6" sm="3" v-for="kpi in kpis" :key="kpi.label">
        <v-card elevation="0" class="kpi-card pa-3" rounded="lg">
          <div class="kpi-label">{{ kpi.label }}</div>
          <div class="kpi-value">{{ kpi.value }}</div>
        </v-card>
      </v-col>
    </v-row>

    <!-- Per-model table + donut chart side-by-side -->
    <v-row class="mx-0 mb-2" dense>
      <v-col cols="12" md="7">
        <v-card elevation="0" class="stats-table-card" rounded="lg">
          <div class="stats-table-title">By Model</div>
          <v-table density="compact" class="stats-table">
            <thead>
              <tr>
                <th>Model</th>
                <th class="text-right">Calls</th>
                <th class="text-right">Tokens</th>
                <th class="text-right">Cost (USD)</th>
                <th class="text-right">Avg Latency</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="loadingSummary">
                <td colspan="5" class="text-center py-4">
                  <v-progress-circular indeterminate size="20" />
                </td>
              </tr>
              <tr v-else-if="summary.length === 0">
                <td colspan="5" class="text-center py-4 text-medium-emphasis text-caption">No data</td>
              </tr>
              <tr v-for="row in summary" :key="row.provider_model">
                <td class="text-caption font-weight-medium" style="max-width:160px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">
                  {{ row.provider_model || 'unknown' }}
                </td>
                <td class="text-right text-caption">{{ row.call_count }}</td>
                <td class="text-right text-caption">{{ formatTokens(row.total_tokens) }}</td>
                <td class="text-right text-caption">{{ row.total_cost_usd > 0 ? `$${row.total_cost_usd.toFixed(4)}` : '—' }}</td>
                <td class="text-right text-caption">{{ row.avg_latency_ms > 0 ? `${Math.round(row.avg_latency_ms)}ms` : '—' }}</td>
              </tr>
            </tbody>
          </v-table>
        </v-card>
      </v-col>

      <v-col cols="12" md="5" v-if="donutSeries.length > 0">
        <v-card elevation="0" class="stats-table-card d-flex flex-column align-center justify-center" rounded="lg" style="min-height:220px;">
          <div class="stats-table-title w-100">Token Distribution</div>
          <apexchart
            type="donut"
            :options="donutOptions"
            :series="donutSeries"
            width="100%"
            height="200"
          />
        </v-card>
      </v-col>
    </v-row>

    <!-- Recent calls -->
    <v-card elevation="0" class="stats-table-card" rounded="lg">
      <div class="stats-table-title d-flex align-center justify-space-between">
        <span>Recent Calls</span>
        <div class="d-flex align-center gap-2">
          <v-btn
            variant="text"
            size="x-small"
            icon="mdi-chevron-left"
            :disabled="recentPage === 0"
            @click="prevPage"
          />
          <span class="text-caption text-medium-emphasis">{{ recentPage + 1 }} / {{ totalPages }}</span>
          <v-btn
            variant="text"
            size="x-small"
            icon="mdi-chevron-right"
            :disabled="recentPage >= totalPages - 1"
            @click="nextPage"
          />
        </div>
      </div>
      <v-table density="compact" class="stats-table">
        <thead>
          <tr>
            <th>Model</th>
            <th>Status</th>
            <th class="text-right">Tokens In</th>
            <th class="text-right">Tokens Out</th>
            <th class="text-right">Cost</th>
            <th class="text-right">Latency</th>
            <th class="text-right">Time</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="loadingRecent">
            <td colspan="7" class="text-center py-4">
              <v-progress-circular indeterminate size="20" />
            </td>
          </tr>
          <tr v-else-if="recentRecords.length === 0">
            <td colspan="7" class="text-center py-4 text-medium-emphasis text-caption">No records</td>
          </tr>
          <tr v-for="rec in recentRecords" :key="rec.id">
            <td class="text-caption" style="max-width:160px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">
              {{ rec.provider_model || rec.provider_id || '—' }}
            </td>
            <td>
              <v-chip
                size="x-small"
                :color="rec.status === 'completed' ? 'success' : 'error'"
                variant="tonal"
              >{{ rec.status }}</v-chip>
            </td>
            <td class="text-right text-caption">{{ (rec.token_input_other + rec.token_input_cached) || '—' }}</td>
            <td class="text-right text-caption">{{ rec.token_output || '—' }}</td>
            <td class="text-right text-caption">{{ rec.cost_usd > 0 ? `$${rec.cost_usd.toFixed(5)}` : '—' }}</td>
            <td class="text-right text-caption">
              {{ rec.end_time && rec.start_time ? `${Math.round((rec.end_time - rec.start_time) * 1000)}ms` : '—' }}
            </td>
            <td class="text-right text-caption">{{ formatTime(rec.created_at) }}</td>
          </tr>
        </tbody>
      </v-table>
    </v-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { useProviderStats } from '@/composables/useProviderStats'

const {
  summary,
  recentRecords,
  recentTotal,
  loadingSummary,
  loadingRecent,
  loadSummary,
  loadRecent,
} = useProviderStats()

const selectedDays = ref(7)
const recentPage = ref(0)
const pageSize = 20

const totalPages = computed(() => Math.max(1, Math.ceil(recentTotal.value / pageSize)))

const kpis = computed(() => {
  const totalCalls = summary.value.reduce((s, r) => s + r.call_count, 0)
  const totalTokens = summary.value.reduce((s, r) => s + r.total_tokens, 0)
  const totalCost = summary.value.reduce((s, r) => s + r.total_cost_usd, 0)
  const avgLatency = summary.value.length
    ? summary.value.reduce((s, r) => s + r.avg_latency_ms, 0) / summary.value.length
    : 0

  return [
    { label: 'Total Calls', value: totalCalls.toLocaleString() },
    { label: 'Total Tokens', value: formatTokens(totalTokens) },
    { label: 'Total Cost', value: totalCost > 0 ? `$${totalCost.toFixed(4)}` : '—' },
    { label: 'Avg Latency', value: avgLatency > 0 ? `${Math.round(avgLatency)}ms` : '—' },
  ]
})

const donutSeries = computed(() => summary.value.map((r) => r.total_tokens))
const donutOptions = computed(() => ({
  chart: { type: 'donut' },
  labels: summary.value.map((r) => r.provider_model || 'unknown'),
  legend: { position: 'bottom', fontSize: '11px' },
  plotOptions: { pie: { donut: { size: '60%' } } },
  dataLabels: { enabled: false },
  tooltip: {
    y: { formatter: (v: number) => formatTokens(v) }
  }
}))

function formatTokens(n: number): string {
  if (!n) return '0'
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`
  return `${n}`
}

function formatTime(isoStr: string): string {
  if (!isoStr) return '—'
  try {
    const d = new Date(isoStr)
    const now = new Date()
    const diff = now.getTime() - d.getTime()
    if (diff < 60_000) return `${Math.round(diff / 1000)}s ago`
    if (diff < 3_600_000) return `${Math.round(diff / 60_000)}m ago`
    if (diff < 86_400_000) return `${Math.round(diff / 3_600_000)}h ago`
    return d.toLocaleDateString()
  } catch {
    return '—'
  }
}

async function reload() {
  await Promise.all([
    loadSummary(selectedDays.value),
    loadRecent(pageSize, recentPage.value * pageSize),
  ])
}

async function prevPage() {
  if (recentPage.value > 0) {
    recentPage.value -= 1
    await loadRecent(pageSize, recentPage.value * pageSize)
  }
}

async function nextPage() {
  if (recentPage.value < totalPages.value - 1) {
    recentPage.value += 1
    await loadRecent(pageSize, recentPage.value * pageSize)
  }
}

watch(selectedDays, async (days) => {
  recentPage.value = 0
  await loadSummary(days)
})

onMounted(reload)
</script>

<style scoped>
.stats-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.stats-panel__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.stats-panel__title {
  font-size: 15px;
  font-weight: 650;
  display: flex;
  align-items: center;
}

.stats-panel__controls {
  display: flex;
  align-items: center;
  gap: 8px;
}

.kpi-card {
  border: 1px solid rgba(var(--v-theme-on-surface), 0.08);
  background: rgba(var(--v-theme-primary), 0.04);
}

.kpi-label {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: rgba(var(--v-theme-on-surface), 0.56);
}

.kpi-value {
  font-size: 22px;
  font-weight: 700;
  letter-spacing: -0.03em;
  line-height: 1.2;
  margin-top: 4px;
}

.stats-table-card {
  border: 1px solid rgba(var(--v-theme-on-surface), 0.08);
  padding: 14px 14px 8px;
  overflow: hidden;
}

.stats-table-title {
  font-size: 13px;
  font-weight: 650;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: rgba(var(--v-theme-on-surface), 0.56);
  margin-bottom: 8px;
}

.stats-table :deep(th) {
  font-size: 11px !important;
  font-weight: 600 !important;
  letter-spacing: 0.04em !important;
  color: rgba(var(--v-theme-on-surface), 0.56) !important;
}

.stats-table :deep(td) {
  border-bottom: none !important;
}

.gap-2 {
  gap: 8px;
}
</style>
