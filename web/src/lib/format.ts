export const DISPLAY_LIMIT = 220

export function marketOf(row = {}) {
  const sym = String(row.symbol || '').toUpperCase()
  if (row.market || row.metrics?.market) return row.market || row.metrics?.market
  if (sym.endsWith('.NS') || sym.endsWith('.BO')) return 'india'
  if (sym.endsWith('.L')) return 'uk'
  return 'us'
}

export const CURRENCY = { india: '₹', uk: '£', us: '$' }
export function currencyOf(row = {}) {
  return CURRENCY[marketOf(row)] || '$'
}

export function rankScore(row = {}) {
  const m = row.metrics || {}
  return Number(row.buy_score ?? m.buy_score ?? row.score ?? m.score ?? 0)
}

export function qualityScore(row = {}) {
  const m = row.metrics || {}
  return Number(row.quality_score ?? m.quality_score ?? row.score ?? 0)
}

export function factorsDisplay(row = {}) {
  const total = Number(row.factors_total ?? row.metrics?.factors_total ?? row.factor_breakdown?.length ?? 0)
  const hit = Number(row.factors_hit ?? row.metrics?.factors_hit ?? (row.factor_breakdown || []).filter((f) => f.status === 'pass').length)
  return { hit, total }
}

export function hasSmartMoney(row = {}) {
  const sm = row.metrics?.smart_money
  if (sm?.hits?.length || sm?.primary_alert) return true
  return (row.alerts || []).some((a) => /LEGEND|WHALE|POLITICIAN|FOREIGN BUY|SMART MONEY|INSIDER|FORM 4/i.test(String(a)))
}

export function buyTier(score = 0) {
  const s = Number(score || 0)
  if (s >= 85) return ['buy-sp', 'S+']
  if (s >= 70) return ['buy-a', 'A']
  if (s >= 55) return ['buy-b', 'B']
  if (s >= 40) return ['buy-c', 'C']
  return ['buy-d', 'D']
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

export function getHotPool(data = {}, marketFilter = 'all') {
  const pools = [
    ...(data.hot || []),
    ...((data.hot_by_market && data.hot_by_market.us) || []),
    ...((data.hot_by_market && data.hot_by_market.india) || []),
    ...((data.hot_by_market && data.hot_by_market.uk) || []),
    ...(data.discoveries || []),
  ]
  const seen = new Set()
  const deduped = []
  for (const row of pools) {
    if (!row?.symbol || seen.has(row.symbol)) continue
    seen.add(row.symbol)
    if (marketFilter !== 'all' && marketOf(row) !== marketFilter) continue
    deduped.push(row)
  }
  return deduped
}

export function filterAndSort(rows = [], ui = {}) {
  const q = String(ui.search || '').trim().toUpperCase()
  const filtered = rows.filter((row) => {
    const m = row.metrics || {}
    if (ui.earlyOnly && m.is_extended) return false
    if (ui.whaleOnly && !hasSmartMoney(row)) return false
    if (ui.sectorFilter && m.sector !== ui.sectorFilter) return false
    if (q) {
      const hay = `${row.symbol || ''} ${m.name || ''} ${m.sector || ''}`.toUpperCase()
      if (!hay.includes(q)) return false
    }
    return true
  })
  const sortBy = ui.sortBy || 'score'
  const value = (row) => {
    const m = row.metrics || {}
    if (sortBy === 'quality') return qualityScore(row)
    if (sortBy === 'factors') return factorsDisplay(row).hit
    if (sortBy === 'day') return Number(m.day_chg_pct ?? row.day_chg_pct ?? 0)
    if (sortBy === 'rvol') return Number(m.rvol ?? m.relative_volume ?? 0)
    return rankScore(row)
  }
  return [...filtered].sort((a, b) => value(b) - value(a))
}

export function timeAgo(input) {
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
