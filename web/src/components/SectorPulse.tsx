import { useState } from 'react'
import { useAppDispatch, useAppSelector } from '../store/hooks'
import { setSectorFilter, selectSymbol } from '../store/uiSlice'

type Pick = {
  symbol: string; name?: string; market?: string; grade?: string; archetype?: string
  buy_score?: number; quality_score?: number; day_chg_pct?: number; price?: number
  fundamentally_strong?: boolean; tags?: string[]; headline?: string
}
type Sector = {
  sector?: string; cycle?: string; cycle_label?: string; rotation?: string
  stock_count?: number; hot_count?: number; early_buy_count?: number; extended_count?: number
  avg_buy_score?: number; avg_quality_score?: number; avg_day_chg_pct?: number
  us_count?: number; india_count?: number; top_picks?: Pick[]; stocks?: Pick[]
}

// What drives each sector + the sector-level risk — info most users don't know.
const SECTOR_NOTE: Record<string, { drives: string; watch: string }> = {
  'Technology': { drives: 'Dollar-billed IT exports; earnings track global tech budgets.', watch: 'A US/Europe slowdown or AI disruption hits the whole group.' },
  'Financial Services': { drives: 'Lends and earns on the spread; grows with India’s credit cycle.', watch: 'Bad loans rise and margins compress in a downturn.' },
  'Consumer Defensive': { drives: 'Everyday staples — steady demand, pricing power.', watch: 'Rural demand and raw-material costs swing margins; usually pricey.' },
  'Consumer Cyclical': { drives: 'Discretionary spending — autos, retail, durables.', watch: 'Slows fast when incomes or sentiment dip.' },
  'Healthcare': { drives: 'Generics + specialty pharma, much of it exported.', watch: 'US FDA actions and generic price erosion are constant risks.' },
  'Energy': { drives: 'Oil, gas and power — commodity-linked cash flows.', watch: 'Crude swings and the energy transition cloud the long term.' },
  'Basic Materials': { drives: 'Cement, metals, chemicals — cyclical to construction/industry.', watch: 'Prices and demand are cyclical; input costs bite.' },
  'Industrials': { drives: 'Capex, defence and infrastructure — India’s build-out.', watch: 'Lumpy order cycles and execution risk.' },
  'Utilities': { drives: 'Regulated power — steady, defensive returns.', watch: 'Capped upside; coal-heavy names face transition pressure.' },
  'Communication Services': { drives: 'Telecom and media — subscriber and ARPU driven.', watch: 'Heavy capex and price competition.' },
}

const CYCLE_TONE: Record<string, string> = { cyclical: 'cyc', defensive: 'def', growth: 'grw' }

function gradeClass(g?: string) { return g ? 'g-' + g.replace('+', 'p') : '' }

function PickRow({ p }: { p: Pick }) {
  const dispatch = useAppDispatch()
  const day = Number(p.day_chg_pct ?? 0)
  return (
    <button className="spx-pick" title={`Open ${p.symbol}`} onClick={(e) => { e.stopPropagation(); dispatch(selectSymbol(p.symbol)) }}>
      {p.grade && <span className={'spx-grade ' + gradeClass(p.grade)}>{p.grade}</span>}
      <span className="spx-pick__name">{p.name || p.symbol}</span>
      {(p.headline || p.archetype) && <span className="spx-pick__arch" title={p.headline || p.archetype}>{p.headline || p.archetype}</span>}
      <span className="spx-pick__spacer" />
      {p.buy_score != null && <span className="spx-pick__score" title="Buy score">{Math.round(p.buy_score)}</span>}
      {p.price != null ? <span className={'spx-pick__day ' + (day >= 0 ? 'pos' : 'neg')}>{day > 0 ? '+' : ''}{day}%</span> : <span className="spx-pick__pending">px pending</span>}
    </button>
  )
}

function SectorCard({ s }: { s: Sector }) {
  const dispatch = useAppDispatch()
  const sectorFilter = useAppSelector((u) => u.ui.sectorFilter)
  const [open, setOpen] = useState(false)
  const total = s.stock_count || 0
  const hot = s.hot_count || 0
  const ratio = total > 0 ? hot / total : 0
  const heat = hot >= 3 || ratio >= 0.4 ? 'hot' : hot >= 1 || ratio >= 0.15 ? 'warm' : 'cool'
  const note = SECTOR_NOTE[s.sector || '']
  const cyc = CYCLE_TONE[(s.cycle || '').toLowerCase()] || 'neu'
  const picks = s.top_picks || []
  const all = s.stocks || []
  const active = sectorFilter === s.sector
  const strong = all.filter((x) => x.fundamentally_strong).length
  const aCount = all.filter((x) => x.grade === 'A+' || x.grade === 'A').length

  return (
    <div className={'spx-card heat-' + heat + (open ? ' open' : '') + (active ? ' active' : '')}>
      <button className="spx-card__head" onClick={() => setOpen((o) => !o)} title="Expand to see every stock + sector view">
        <div className="spx-card__title">
          <span className="spx-name">{s.sector}</span>
          {s.cycle_label && <span className={'spx-cyc spx-cyc--' + cyc}>{s.cycle_label}</span>}
          {s.rotation && s.rotation !== 'neutral' && <span className={'spx-rot spx-rot--' + s.rotation}>{s.rotation}</span>}
        </div>
        <span className="spx-caret">{open ? '−' : '+'}</span>
      </button>

      <div className="spx-strength" title={`${hot} of ${total} names hot`}><div className="spx-strength__fill" style={{ width: Math.round(ratio * 100) + '%' }} /></div>

      <div className="spx-stats">
        <span><b>{total}</b> stocks</span>
        <span><b className="hot">{hot}</b> hot</span>
        <span><b className="early">{s.early_buy_count ?? 0}</b> early</span>
        <span><b className="strong">{strong}</b> strong</span>
        <span><b>{aCount}</b> A-grade</span>
        {s.avg_quality_score != null && <span title="Average quality score">avg Q <b>{s.avg_quality_score}</b></span>}
      </div>

      {!open && picks.length > 0 && (
        <div className="spx-toppicks">
          {picks.slice(0, 4).map((p) => (
            <button key={p.symbol} className={'spx-chip ' + gradeClass(p.grade)} title={`${p.name || p.symbol}${p.archetype ? ' — ' + p.archetype : ''}`} onClick={(e) => { e.stopPropagation(); dispatch(selectSymbol(p.symbol)) }}>
              {p.grade && <span className="spx-chip__g">{p.grade}</span>}{p.symbol.replace(/\.(NS|BO|L)$/, '')}
            </button>
          ))}
          {all.length > 4 && <span className="spx-more" onClick={() => setOpen(true)}>+{all.length - 4} more</span>}
        </div>
      )}

      {open && (
        <div className="spx-expand">
          {note && (
            <div className="spx-note">
              <div className="spx-note__row"><span className="spx-note__lbl">What drives it</span>{note.drives}</div>
              <div className="spx-note__row watch"><span className="spx-note__lbl">⚠ Watch</span>{note.watch}</div>
            </div>
          )}
          <div className="spx-metrics">
            <span>Avg buy <b>{s.avg_buy_score ?? '—'}</b></span>
            <span>Avg day <b className={Number(s.avg_day_chg_pct ?? 0) >= 0 ? 'pos' : 'neg'}>{s.avg_day_chg_pct ?? '—'}%</b></span>
            {(s.india_count || 0) > 0 && <span><b>{s.india_count}</b> IN</span>}
            {(s.us_count || 0) > 0 && <span><b>{s.us_count}</b> US</span>}
            {(s.extended_count || 0) > 0 && <span><b>{s.extended_count}</b> extended</span>}
          </div>
          <div className="spx-list">
            {all.map((p) => <PickRow key={p.symbol} p={p} />)}
          </div>
          <button className={'spx-filter' + (active ? ' on' : '')} onClick={() => dispatch(setSectorFilter(active ? null : s.sector || null))}>
            {active ? '✓ Filtering Hot Movers to this sector' : 'Filter Hot Movers to ' + s.sector}
          </button>
        </div>
      )}
    </div>
  )
}

const SORTS: [string, string][] = [
  ['hot', 'Most hot'], ['quality', 'Best quality'], ['size', 'Most stocks'], ['movers', 'Biggest move'],
]

export default function SectorPulse() {
  const dispatch = useAppDispatch()
  const data = useAppSelector((s) => s.live.data)
  const sectors: Sector[] = (data?.sectors || []) as Sector[]
  const cycles: any[] = (data?.cycle_overview || []) as any[]
  const [sort, setSort] = useState('hot')
  const [cycleFilter, setCycleFilter] = useState<string | null>(null)

  let ranked = sectors.filter((s) => s.sector && (s.stock_count || 0) > 0)
  if (cycleFilter) ranked = ranked.filter((s) => (s.cycle || '').toLowerCase() === cycleFilter)
  ranked = [...ranked].sort((a, b) => {
    if (sort === 'quality') return (b.avg_quality_score || 0) - (a.avg_quality_score || 0)
    if (sort === 'size') return (b.stock_count || 0) - (a.stock_count || 0)
    if (sort === 'movers') return (b.avg_day_chg_pct || 0) - (a.avg_day_chg_pct || 0)
    return (b.hot_count || 0) - (a.hot_count || 0) || (b.avg_buy_score || 0) - (a.avg_buy_score || 0)
  })

  if (ranked.length === 0 && !cycleFilter) {
    return (
      <section className="sector-pulse">
        <div className="sp-head"><h2>Sector Pulse</h2><span className="sp-sub">Live sector rotation — building as the scanner runs…</span></div>
        <p className="sp-empty">No sector data yet. Sectors fill in automatically as stocks are scored — no action needed.</p>
      </section>
    )
  }

  return (
    <section className="sector-pulse">
      <div className="sp-head">
        <h2>Sector Pulse</h2>
        <span className="sp-sub">Where money is rotating — click any sector to see every stock, grades & what to watch</span>
        <span className="sp-spacer" />
        <select className="sp-sort" value={sort} onChange={(e) => setSort(e.target.value)} title="Sort sectors">
          {SORTS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </select>
      </div>

      {cycles.length > 0 && (
        <div className="sp-cycles">
          {cycles.map((c, i) => {
            const cl = (c.cycle || '').toLowerCase()
            const on = cycleFilter === cl
            return (
              <button key={i} className={'sp-cycle' + (on ? ' on' : '')} title={`Show only ${c.label || c.cycle} sectors`} onClick={() => setCycleFilter(on ? null : cl)}>
                <span className="sp-cycle__label">{c.label || c.cycle}</span>
                <span className="sp-cycle__val">{c.hot_count ?? 0} hot</span>
                <span className="sp-cycle__sub">{c.sector_count ?? 0} sectors · {c.stock_count ?? 0} stocks · avg {c.avg_buy_score ?? '—'}</span>
              </button>
            )
          })}
          {cycleFilter && <button className="sp-clear" onClick={() => setCycleFilter(null)}>✕ clear</button>}
        </div>
      )}

      <div className="spx-grid">
        {ranked.map((s) => <SectorCard key={s.sector} s={s} />)}
      </div>
    </section>
  )
}
