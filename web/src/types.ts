export type Market = 'us' | 'india' | 'uk'
export type MarketFilter = Market | 'all'
export type FactorFilter = 'all' | 'pass' | 'fail' | 'risk'
export type SortBy = 'score' | 'quality' | 'grade' | 'factors' | 'day' | 'rvol'

export interface FactorBreakdownItem {
  id?: string
  name?: string
  description?: string
  category?: string
  status?: 'pass' | 'fail' | 'risk' | string
  tier?: string
  label?: string
  weighted_points?: number | string
}

export interface SmartMoneyHit {
  id?: string
  name?: string
  kind?: string
  tier?: string
  headline?: string
  quality?: string
  // Optional whale-enrichment fields (backend may add these; older data omits them)
  investor_name?: string
  display_name?: string
  investor_type?: string
  action?: string
  conviction?: string
  conviction_tier?: string
  recency?: string
  seen_at?: string
  ts?: string
  why?: string
  why_it_matters?: string
  blurb?: string
}

export interface SmartMoney {
  hits?: SmartMoneyHit[]
  primary_alert?: string
}

export interface Metrics {
  market?: Market | string
  name?: string
  sector?: string
  price?: number
  buy_score?: number
  quality_score?: number
  score?: number
  day_chg_pct?: number
  rvol?: number
  relative_volume?: number
  confidence_score?: number
  is_extended?: boolean
  earnings_pre?: boolean
  smart_money?: SmartMoney
  factors_total?: number
  factors_hit?: number
  factor_breakdown?: FactorBreakdownItem[]
  [key: string]: unknown
}

export interface ResearchGroup {
  title: string
  reasons: string[]
}

export interface StockProfile {
  biz?: string
  archetype?: string
  moat?: string
  watch?: string[]
  valuation?: string
  peers?: string[]
  ownership?: string
  _curated?: boolean
}

export interface Research {
  grade?: string
  quality_score?: number
  fundamentally_strong?: boolean
  tags?: string[]
  reason_count?: number
  groups?: ResearchGroup[]
  summary?: string
  archetype?: string
  profile?: StockProfile
}

export interface Row {
  symbol: string
  research?: Research
  top_factors?: { id?: string; label?: string; category?: string; tier?: string; weighted_points?: number }[]
  market?: Market | string
  score?: number
  buy_score?: number
  quality_score?: number
  day_chg_pct?: number
  earnings_soon?: boolean
  alerts?: string[]
  news?: NewsItem[]
  earnings?: unknown
  discovered?: boolean
  full_exhaustive?: boolean
  sparkline?: number[]
  metrics?: Metrics
  factor_breakdown?: FactorBreakdownItem[]
  factors_total?: number
  factors_hit?: number
  [key: string]: unknown
}

export interface ServerAlert {
  symbol?: string
  rule_type?: string
  message?: string
  triggered_at?: string
  buy_score?: number
}

export interface ClientAlert {
  type: string
  symbol?: string
  msg?: string
  ts?: string
  score?: number
  server?: boolean
}

export interface SnapshotStats {
  market_events_count?: number
  symbols_tracked?: number
  analyzing_symbols?: string[]
  last_full_price_scan_result_count?: number
  last_price_batch_result_count?: number
  last_full_price_scan_attempted?: number
  last_price_batch_attempted?: number
  scan_in_progress?: boolean
  scan_batch?: number
  scan_batches_total?: number
  last_price_scan?: string
  last_price_tick?: string
  [key: string]: unknown
}

export interface NewsItem {
  symbol?: string
  url?: string
  title?: string
  headline?: string
  source?: string
  ts?: string
}

export interface EarningsItem {
  symbol?: string
  date?: string
  report_date?: string
  days_until?: number
  eps_est?: number | string
  eps_estimate?: number | string
  score?: number
  buy_score?: number
  day_chg_pct?: number
}

export interface InvestorEvent {
  symbol?: string
  investor_name?: string
  actor_name?: string
  display_name?: string
  name?: string
  kind?: string
  investor_type?: string
  event_type?: string
  action?: string
  conviction?: string
  conviction_tier?: string
  tier?: string
  recency?: string
  seen_at?: string
  ts?: string
  details?: string
  headline?: string
  why?: string
  why_it_matters?: string
  blurb?: string
}

export interface SectorSummary {
  sector?: string
  stock_count?: number
  hot_count?: number
  early_buy_count?: number
  rotation?: string
  cycle_label?: string
  top_picks?: Row[]
  stocks?: Row[]
}

export interface CycleSummary {
  cycle?: string
  label?: string
  stock_count?: number
  hot_count?: number
  sector_count?: number
  avg_buy_score?: number | string
}

export interface Snapshot {
  hot?: Row[]
  hot_by_market?: Partial<Record<Market, Row[]>>
  discoveries?: Row[]
  alerts?: ServerAlert[]
  stats?: SnapshotStats
  news?: NewsItem[]
  earnings?: EarningsItem[]
  events?: unknown[]
  investor_events?: InvestorEvent[]
  sectors?: SectorSummary[]
  cycle_overview?: CycleSummary[]
  scan_generation?: number
  [key: string]: unknown
}

export interface UiState {
  marketFilter: MarketFilter
  earlyOnly: boolean
  whaleOnly: boolean
  qualityOnly: boolean
  sectorFilter: string | null
  sortBy: SortBy
  search: string
  selectedSymbol: string | null
  factorSymbol: string | null
  factorFilter: FactorFilter
  toast: unknown | null
}

export interface LiveState {
  status: 'connecting' | 'live' | 'down' | string
  data: Snapshot | null
  alerts: ClientAlert[]
  seen: Record<string, boolean>
  lastGeneration: number
}

export interface WatchItem {
  symbol: string
  name?: string
  buy_score?: number
  last_score?: number
  quality_score?: number
  notes?: string
  added_at?: string
}

export interface WatchlistResponse { watches?: WatchItem[] }
export interface WatchBody { symbol: string; notes?: string }

export interface AlertRule {
  id: number | string
  rule_type: string
  condition?: Record<string, unknown>
  enabled?: boolean
}
export interface AlertRulesResponse { rules?: AlertRule[] }
export interface AlertRuleBody { rule_type: string; condition?: Record<string, unknown>; enabled?: boolean }

export interface Position {
  name?: string
  symbol: string
  qty?: number
  entry_price?: number
  est_pnl?: number
  sl?: number
  target?: number
  notes?: string
}
export interface PortfolioResponse {
  positions?: Position[]
  summary?: { unrealized_pnl?: number; realized_pnl?: number; [key: string]: unknown }
}
export interface AddPositionBody {
  symbol: string
  qty?: number
  entry_price: number
  entry_score?: number
  sl?: number
  target?: number
  notes?: string
}
export interface ClosePositionBody { symbol: string; price?: number; notes?: string }
export interface UpdatePositionBody { symbol: string; sl?: number; target?: number; notes?: string }

export interface JournalEntry {
  symbol?: string
  action?: string
  price?: number
  qty?: number
  outcome_pnl?: number
  notes?: string
}
export interface JournalResponse { journal?: JournalEntry[] }

export interface EdgeBucket {
  bucket?: string
  label?: string
  samples?: number
  n?: number
  avg_7d?: number
  avg_return?: number
  hit_rate?: number | string
}
export interface EdgeResponse { buckets?: EdgeBucket[]; score_buckets?: EdgeBucket[]; [key: string]: unknown }

export interface JobStatusResponse { status?: string; [key: string]: unknown }
export interface StartFullScanResponse { job_id?: string; id?: string; [key: string]: unknown }
