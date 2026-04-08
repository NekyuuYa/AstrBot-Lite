import { ref } from 'vue'
import axios from 'axios'

export interface ProviderModelSummary {
  provider_model: string
  call_count: number
  total_input_tokens: number
  total_cached_tokens: number
  total_output_tokens: number
  total_tokens: number
  total_cost_usd: number
  avg_latency_ms: number
}

export interface ProviderStatRecord {
  id: number
  provider_id: string
  provider_model: string
  status: string
  umo: string
  token_input_other: number
  token_input_cached: number
  token_output: number
  cost_usd: number
  start_time: number
  end_time: number
  time_to_first_token: number
  created_at: string
}

export function useProviderStats() {
  const summary = ref<ProviderModelSummary[]>([])
  const recentRecords = ref<ProviderStatRecord[]>([])
  const recentTotal = ref(0)
  const loadingSummary = ref(false)
  const loadingRecent = ref(false)

  async function loadSummary(days = 7) {
    loadingSummary.value = true
    try {
      const res = await axios.get('/api/stat/provider/summary', { params: { days } })
      if (res.data.status === 'ok') {
        summary.value = res.data.data?.models || []
      }
    } catch (e) {
      console.error('Failed to load provider stats summary:', e)
    } finally {
      loadingSummary.value = false
    }
  }

  async function loadRecent(limit = 50, offset = 0) {
    loadingRecent.value = true
    try {
      const res = await axios.get('/api/stat/provider/recent', { params: { limit, offset } })
      if (res.data.status === 'ok') {
        recentRecords.value = res.data.data?.records || []
        recentTotal.value = res.data.data?.total || 0
      }
    } catch (e) {
      console.error('Failed to load provider recent stats:', e)
    } finally {
      loadingRecent.value = false
    }
  }

  return {
    summary,
    recentRecords,
    recentTotal,
    loadingSummary,
    loadingRecent,
    loadSummary,
    loadRecent,
  }
}
