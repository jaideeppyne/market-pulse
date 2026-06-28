import type { Market, MarketFilter, Row, UiState, FactorBreakdownItem, SmartMoneyHit, InvestorEvent } from '../types'

export const DISPLAY_LIMIT = 220

export function marketOf(row: Partial<Row> = {}): Market {
  const sym = String(row.symbol || '').toUpperCase()
  const market = row.market || row.metrics?.market
  if (market === 'india' || market === 'uk' || market === 'us') return market
  if (sym.endsWith('.NS') || sym.endsWith('.BO')) return 'india'
  if (sym.endsWith('.L')) return 'uk'
  return 'us'
}

export const CURRENCY: Record<Market, string> = { india: '₹', uk: '£', us: '$' }
export function currencyOf(row: Partial<Row> = {}) {
  return CURRENCY[marketOf(row)] || '$'
}

export function rankScore(row: Partial<Row> = {}) {
  const m = row.metrics || {}
  return Number(row.buy_score ?? m.buy_score ?? row.score ?? m.score ?? 0)
}

export function qualityScore(row: Partial<Row> = {}) {
  const m = row.metrics || {}
  return Number(row.quality_score ?? m.quality_score ?? row.score ?? 0)
}

export function factorsDisplay(row: Partial<Row> = {}) {
  const breakdown = row.factor_breakdown || row.metrics?.factor_breakdown || []
  const total = Number(row.factors_total ?? row.metrics?.factors_total ?? breakdown.length ?? 0)
  const hit = Number(row.factors_hit ?? row.metrics?.factors_hit ?? breakdown.filter((f) => f.status === 'pass').length)
  return { hit, total }
}

export function hasSmartMoney(row: Partial<Row> = {}) {
  const sm = row.metrics?.smart_money
  if (sm?.hits?.length || sm?.primary_alert) return true
  return (row.alerts || []).some((a) => /LEGEND|WHALE|POLITICIAN|FOREIGN BUY|SMART MONEY|INSIDER|FORM 4/i.test(String(a)))
}

export function buyTier(score = 0) {
  const s = Number(score || 0)
  if (s >= 85) return ['buy-sp', 'S+'] as const
  if (s >= 70) return ['buy-a', 'A'] as const
  if (s >= 55) return ['buy-b', 'B'] as const
  if (s >= 40) return ['buy-c', 'C'] as const
  return ['buy-d', 'D'] as const
}

export function confTier(score = 0) {
  const s = Number(score || 0)
  if (s >= 80) return 'hi'
  if (s >= 60) return 'mid'
  return 'lo'
}

export function rvolTier(v = 0) {
  const n = Number(v || 0)
  if (n >= 2) return 'hi'
  if (n >= 1.15) return 'mid'
  return 'lo'
}

export function getHotPool(data: { hot?: Row[]; hot_by_market?: Partial<Record<Market, Row[]>>; discoveries?: Row[] } = {}, marketFilter: MarketFilter = 'all') {
  const pools = [
    ...(data.hot || []),
    ...((data.hot_by_market && data.hot_by_market.us) || []),
    ...((data.hot_by_market && data.hot_by_market.india) || []),
    ...((data.hot_by_market && data.hot_by_market.uk) || []),
    ...(data.discoveries || []),
  ]
  const seen = new Set<string>()
  const deduped: Row[] = []
  for (const row of pools) {
    if (!row?.symbol || seen.has(row.symbol)) continue
    seen.add(row.symbol)
    if (marketFilter !== 'all' && marketOf(row) !== marketFilter) continue
    deduped.push(row)
  }
  return deduped
}

export function researchOf(row: Row) {
  return (row.research || (row.metrics as any)?.research) as import('../types').Research | undefined
}
export function isFundamentallyStrong(row: Row) {
  return !!researchOf(row)?.fundamentally_strong
}
const GRADE_RANK: Record<string, number> = { 'A+': 6, 'A': 5, 'B': 4, 'C': 3, 'D': 2 }
export function gradeRank(row: Row) {
  return GRADE_RANK[String(researchOf(row)?.grade || '')] ?? 0
}

export function filterAndSort(rows: Row[] = [], ui: Partial<UiState> = {}) {
  const q = String(ui.search || '').trim().toUpperCase()
  const filtered = rows.filter((row) => {
    const m = row.metrics || {}
    if (ui.earlyOnly && m.is_extended) return false
    if (ui.whaleOnly && !hasSmartMoney(row)) return false
    if (ui.qualityOnly && !isFundamentallyStrong(row)) return false
    if (ui.sectorFilter && m.sector !== ui.sectorFilter) return false
    if (q && rows.length > 1) {
      const hay = `${row.symbol || ''} ${m.name || ''} ${m.sector || ''}`.toUpperCase()
      if (!hay.includes(q)) return false
    }
    return true
  })
  const sortBy = ui.sortBy || 'score'
  const value = (row: Row) => {
    const m = row.metrics || {}
    if (sortBy === 'quality') return qualityScore(row)
    if (sortBy === 'grade') return gradeRank(row) * 1000 + rankScore(row)
    if (sortBy === 'factors') return factorsDisplay(row).hit
    if (sortBy === 'day') return Number(m.day_chg_pct ?? (row as any).day_chg_pct ?? 0)
    if (sortBy === 'rvol') return Number(m.rvol ?? m.relative_volume ?? 0)
    return rankScore(row)
  }
  return [...filtered].sort((a, b) => value(b) - value(a))
}

export function timeAgo(input?: string) {
  if (!input) return 'now'
  const t = new Date(input).getTime()
  if (!Number.isFinite(t)) return ''
  const diff = Math.max(0, Date.now() - t)
  const min = Math.floor(diff / 60000)
  if (min < 1) return 'now'
  if (min < 60) return `${min}m`
  const hr = Math.floor(min / 60)
  if (hr < 24) return `${hr}h`
  const d = Math.floor(hr / 24)
  return `${d}d`
}

// ---- Plain-English verdict (added) ----------------------------------------
export type Verdict = { text: string; tone: 'good' | 'caution' | 'watch' | 'neutral' }

export function verdict(row: Partial<Row> = {}): Verdict {
  const m = row.metrics || {}
  const buy = rankScore(row)
  const qual = qualityScore(row)
  const extPen = Number((m as any).extension_penalty ?? 0)
  const extended = Boolean((m as any).is_extended) || extPen >= 10
  const smart = hasSmartMoney(row)
  const hasQual = qual > 0
  if (buy >= 70 && hasQual && qual >= 70 && !extended)
    return { text: 'High quality and ready — strong entry', tone: 'good' }
  if (buy >= 60 && extended)
    return { text: 'Strong setup, but extended — wait for a pullback', tone: 'caution' }
  if (hasQual && qual >= 70 && buy < 60)
    return { text: 'High quality, early entry — building, not yet extended', tone: 'watch' }
  if (buy >= 60 && hasQual && qual < 50)
    return smart
      ? { text: 'Speculative — smart-money driven, thin on fundamentals', tone: 'caution' }
      : { text: 'Momentum-led — light on the quality checklist', tone: 'caution' }
  if (buy >= 70) return { text: 'Strong buy rank — clearing on entry timing', tone: 'good' }
  if (smart) return { text: 'Smart-money interest — watch for confirmation', tone: 'watch' }
  if (buy >= 45) return { text: 'Developing setup — keep on the radar', tone: 'watch' }
  if (buy >= 20) return { text: 'Speculative mover — limited edge, watch closely', tone: 'neutral' }
  return { text: 'Low conviction — not a strong setup yet', tone: 'neutral' }
}

export function topReasons(row: Partial<Row> = {}, n = 3): { reasons: FactorBreakdownItem[]; risk: FactorBreakdownItem | null } {
  const breakdown = (row.factor_breakdown || []) as FactorBreakdownItem[]
  const passed = breakdown
    .filter((f) => f.status === 'pass')
    .sort((a, b) => Number(b.weighted_points || 0) - Number(a.weighted_points || 0))
  const risks = breakdown.filter((f) => f.status === 'risk' || f.status === 'fail')
  const risk = risks.find((f) => f.status === 'risk') || risks[0] || null
  return { reasons: passed.slice(0, n), risk }
}


// ---- Company name display helpers ------------------------------------------
// Returns the best human-readable company name for a row, or '' if none usable
// (i.e. the name is missing or identical to the symbol).
export function companyName(row: Partial<Row> = {}): string {
  const sym = String(row.symbol || '').toUpperCase()
  const raw = String((row.metrics?.name as string) || (row as { name?: string }).name || '').trim()
  if (!raw) return ''
  if (raw.toUpperCase() === sym) return ''
  return raw
}

// Name to show in dense lists: falls back to sector, then market label.
export function displayName(row: Partial<Row> = {}): string {
  const nm = companyName(row)
  if (nm) return nm
  const sector = String(row.metrics?.sector || '').trim()
  if (sector) return sector
  return marketOf(row).toUpperCase()
}

// ---- Whale / smart-money enrichment helpers --------------------------------
export interface WhaleView {
  investor: string
  type: string
  typeLabel: string
  action: string
  conviction: string
  recency: string
  blurb: string
  rank: number
}

const INVESTOR_TYPE_LABELS: Record<string, string> = {
  india_legend: 'Legend',
  us_legend: 'Legend',
  legend: 'Legend',
  politician_us: 'Politician',
  politician_india: 'Politician',
  politician: 'Politician',
  foreign_india: 'FII',
  fii: 'FII',
  insider: 'Insider',
  promoter: 'Promoter',
  signal: 'Signal',
}

const CONVICTION_RANK: Record<string, number> = { 'S+': 4, S: 3, A: 2, B: 1 }

export function investorTypeLabel(kind?: string): string {
  const k = String(kind || '').toLowerCase().replace(/\s+/g, '_')
  if (INVESTOR_TYPE_LABELS[k]) return INVESTOR_TYPE_LABELS[k]
  if (k.includes('politician')) return 'Politician'
  if (k.includes('legend')) return 'Legend'
  if (k.includes('fii') || k.includes('foreign')) return 'FII'
  if (k.includes('insider')) return 'Insider'
  if (k.includes('promoter')) return 'Promoter'
  return k ? k.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()) : 'Smart money'
}

// Normalise a backend whale hit (or investor event) into a uniform view model,
// gracefully tolerating missing/older fields.
export function whaleView(
  hit: Partial<SmartMoneyHit & InvestorEvent> = {},
  fallbackText = '',
): WhaleView {
  const investor =
    hit.investor_name || hit.display_name || hit.actor_name || hit.name || 'Smart money'
  const rawType = hit.investor_type || hit.kind || hit.event_type || ''
  const typeLabel = investorTypeLabel(rawType)
  const action = String(hit.action || '').trim()
  const conviction = String(hit.conviction_tier || hit.conviction || hit.tier || '').toUpperCase()
  const recencyStr = hit.recency || timeAgo(hit.seen_at || hit.ts)
  const blurb = String(
    hit.why_it_matters || hit.why || hit.blurb || hit.quality || hit.headline ||
    hit.details || fallbackText || '',
  ).trim()
  const rank = (CONVICTION_RANK[conviction] || 0) * 1000 + recencyScore(hit.seen_at || hit.ts)
  return {
    investor: String(investor),
    type: String(rawType),
    typeLabel,
    action,
    conviction,
    recency: recencyStr === 'now' ? 'just now' : recencyStr,
    blurb,
    rank,
  }
}

// Higher = more recent. Used as a secondary sort key.
function recencyScore(ts?: string): number {
  if (!ts) return 0
  const t = new Date(ts).getTime()
  return Number.isFinite(t) ? t / 1e9 : 0
}
