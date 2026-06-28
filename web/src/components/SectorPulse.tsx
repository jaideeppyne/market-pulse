import { useAppDispatch, useAppSelector } from '../store/hooks'
import { setSectorFilter, selectSymbol } from '../store/uiSlice'
import { researchOf, displayName } from '../lib/format'

type Sector = {
  sector?: string
  stock_count?: number
  hot_count?: number
  early_buy_count?: number
  rotation?: string
  cycle_label?: string
  top_picks?: any[]
  stocks?: any[]
}

function heat(s: Sector): string {
  const total = s.stock_count || 0
  const hot = s.hot_count || 0
  const ratio = total > 0 ? hot / total : 0
  if (hot >= 3 || ratio >= 0.4) return 'hot'
  if (hot >= 1 || ratio >= 0.15) return 'warm'
  return 'cool'
}

export default function SectorPulse() {
  const dispatch = useAppDispatch()
  const data = useAppSelector((s) => s.live.data)
  const sectorFilter = useAppSelector((s) => s.ui.sectorFilter)
  const sectors: Sector[] = (data?.sectors || []) as Sector[]
  const cycles: any[] = (data?.cycle_overview || []) as any[]

  const ranked = [...sectors]
    .filter((s) => s.sector && (s.stock_count || 0) > 0)
    .sort((a, b) => (b.hot_count || 0) - (a.hot_count || 0) || (b.stock_count || 0) - (a.stock_count || 0))
    .slice(0, 12)

  if (ranked.length === 0) {
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
        <span className="sp-sub">Where the money is rotating right now · click a sector to filter</span>
      </div>

      {cycles.length > 0 && (
        <div className="sp-cycles">
          {cycles.map((c, i) => (
            <div key={i} className="sp-cycle">
              <span className="sp-cycle__label">{c.label || c.cycle}</span>
              <span className="sp-cycle__val">{c.hot_count ?? 0} hot</span>
              <span className="sp-cycle__sub">{c.stock_count ?? 0} stocks · avg {c.avg_buy_score ?? '—'}</span>
            </div>
          ))}
        </div>
      )}

      <div className="sp-grid">
        {ranked.map((s) => {
          const pick = (s.top_picks || s.stocks || [])[0]
          const pickGrade = pick ? researchOf(pick)?.grade : null
          const active = sectorFilter === s.sector
          return (
            <div
              key={s.sector}
              className={'sp-card heat-' + heat(s) + (active ? ' active' : '')}
              title={`Filter Hot Movers to ${s.sector}`}
              onClick={() => dispatch(setSectorFilter(active ? null : s.sector || null))}
            >
              <div className="sp-card__top">
                <span className="sp-card__name">{s.sector}</span>
                {(s.rotation || s.cycle_label) && <span className="sp-rot">{s.rotation || s.cycle_label}</span>}
              </div>
              <div className="sp-card__counts">
                <span className="sp-num">{s.stock_count ?? 0}</span><span className="sp-lbl">stocks</span>
                <span className="sp-num hot">{s.hot_count ?? 0}</span><span className="sp-lbl">hot</span>
                <span className="sp-num early">{s.early_buy_count ?? 0}</span><span className="sp-lbl">early</span>
              </div>
              {pick && (
                <button
                  className="sp-pick"
                  title={`Open ${pick.symbol}`}
                  onClick={(e) => { e.stopPropagation(); dispatch(selectSymbol(pick.symbol)) }}
                >
                  {pickGrade && <span className={'sp-pick__grade g-' + pickGrade.replace('+', 'p')}>{pickGrade}</span>}
                  <span className="sp-pick__name">{displayName(pick) || pick.symbol}</span>
                </button>
              )}
            </div>
          )
        })}
      </div>
    </section>
  )
}
