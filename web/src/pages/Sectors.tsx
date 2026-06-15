import { useState } from 'react'
import { selectSymbol } from '../store/uiSlice'
import { useAppDispatch, useAppSelector } from '../store/hooks'

export default function Sectors() {
  const dispatch = useAppDispatch()
  const data = useAppSelector((s) => s.live.data)
  const sectors = data?.sectors || []
  const cycles = data?.cycle_overview || []
  const [sel, setSel] = useState<string | null>(null)

  const active = sectors.find((x: any) => x.sector === sel) || null

  return (
    <section className="panel pad">
      <h2 className="view-h">Sector Map</h2>
      <p className="panel-hint">Stocks grouped by sector · cyclical / defensive / growth · top early buys per sector.</p>

      {cycles.length > 0 && (
        <div className="cycle-strip">
          {cycles.map((c: any) => (
            <div key={c.cycle || c.label} className="cycle-card">
              <div className="cycle-title">{c.label || c.cycle}</div>
              <div className="cycle-stats">{c.stock_count ?? 0}</div>
              <div className="cycle-tag">{c.hot_count ?? 0} hot · {c.sector_count ?? 0} sectors · avg {c.avg_buy_score ?? '—'}</div>
            </div>
          ))}
        </div>
      )}

      <div className="sector-layout">
        <div className="sector-list">
          {sectors.length === 0 && <p className="muted">No sector data yet — waiting for scan.</p>}
          {sectors.map((s: any) => (
            <div key={s.sector} className={'sector-row' + (sel === s.sector ? ' active' : '')} onClick={() => setSel(s.sector)}>
              <div className="sector-name">{s.sector}</div>
              <div className="sector-counts">{s.stock_count ?? 0} stocks · {s.hot_count ?? 0} hot · {s.early_buy_count ?? 0} early</div>
              {(s.rotation || s.cycle_label) && <div className="sector-badges"><span className="rotation-tag">{s.rotation || s.cycle_label}</span></div>}
            </div>
          ))}
        </div>
        <aside className="sector-detail panel">
          {!active && <p className="muted">Select a sector to see top picks.</p>}
          {active && (
            <>
              <h3 className="view-h3" style={{ marginTop: 0 }}>{active.sector} <span className="muted" style={{ fontSize: 12 }}>· {active.cycle_label}</span></h3>
              <table className="sector-picks-table">
                <thead><tr><th>Symbol</th><th>Buy</th><th>Day%</th></tr></thead>
                <tbody>
                  {(active.top_picks || active.stocks || []).slice(0, 20).map((p: any, i: number) => (
                    <tr key={i} onClick={() => dispatch(selectSymbol(p.symbol))} className="sector-hot-btn">
                      <td className={!p.metrics?.is_extended ? 'pick-early' : ''}>{p.symbol}</td>
                      <td>{p.metrics?.buy_score ?? p.buy_score ?? p.score ?? '—'}</td>
                      <td>{p.metrics?.day_chg_pct ?? p.day_chg_pct ?? '—'}%</td>
                    </tr>
                  ))}
                  {(!active.top_picks?.length && !active.stocks?.length) && <tr><td colSpan={3} className="muted">No picks listed.</td></tr>}
                </tbody>
              </table>
            </>
          )}
        </aside>
      </div>
    </section>
  )
}
