// Shared domain types for the Pulse Terminal frontend.
export type Market = 'us' | 'india' | 'uk'

export interface SmartMoneyHit {
  name?: string
  kind?: string
  tier?: string
  quality?: string
  headline?: string
}

export interface Metrics {
  price?: number
  day_chg_pct?: number
  buy_score?: number
  quality_score?: number
  confidence_score?: number
  rvol?: number
  name?: string
  sector?: string
  market?: Market
  is_extended?: boolean
  factors_hit?: number
  factors_total?: number
  news_count?: number
  earnings_pre?: boolean
  days_until_earnings?: number
  smart_money?: { hits?: SmartMoneyHit[]; primary_alert?: string }
  [k: string]: unknown
}

export interface Factor {
  name?: string
  id?: string
  description?: string
  label?: string
  status?: 'pass' | 'fail' | 'risk' | 'na'
  tier?: string
  weighted_points?: number
  category?: string
}

export interface Row {
  symbol: string
  market?: Market
  score?: number
  buy_score?: number
  quality_score?: number
  factors_hit?: number
  factors_total?: number
  metrics?: Metrics
  alerts?: string[]
  sparkline?: number[]
  factor_breakdown?: Factor[]
  news?: unknown[]
  earnings?: unknown
  earnings_soon?: boolean
  discovered?: boolean
  full_exhaustive?: boolean
  ad_hoc?: boolean
}

export interface Snapshot {
  hot?: Row[]
  hot_by_market?: Partial<Record<Market, Row[]>>
  news?: any[]
  earnings?: any[]
  sectors?: any[]
  cycle_overview?: any[]
  events?: any[]
  investor_events?: any[]
  alerts?: any[]
  stats?: Record<string, any>
  scan_generation?: number
}

export interface AlertItem {
  type: string
  symbol?: string
  msg?: string
  ts?: string
  score?: number
  server?: boolean
}
