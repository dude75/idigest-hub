export const STATS_CHART_COLORS = {
  transcribe: '#2563eb',
  summarize: '#7c3aed',
  audio: '#059669',
  chars: '#d97706',
  amount: '#2563eb',
} as const

export type StatsChartMetric = keyof typeof STATS_CHART_COLORS
