import { useState } from 'react'
import { useSelector, useDispatch } from 'react-redux'
import { selectSymbol } from '../store/uiSlice'

export default function Sectors() {
  const dispatch = useDispatch()
  const data = useSelector((s) => s.live.data)
  const sectors = data?.sectors || []
  const cycle = data?.cycle_overview || data?.cycle || {}
  const [sel, setSel] = useState(null)

  const active = sectors.find((x) => (x.name || x.sector) === sel) || null

  return (
    <section className="panel pad">
      <h2 className="view-h">Sector Map</h2>
      <p className="panel-hint">Stocks grouped by sector · cyclical / defensive / growth · top early buys per sector.</p>

      {Object.keys(cycle).length > 0 && (
        <div className="cycle-strip">
          {Object.entries(cycle).map(([k, v]) => (
            <div key={k} className="cycle-card">
              <div className="cycle-title">{k}</div>
              <div className="cycle-stats">{typeof v === 'object' ? (v.count ?? v.total ?? '') : v}</div>
              {typeof v === 'object' && v.tag && <div className="cycle-tag">{v.tag}</div>}
            </div>
          ))}
        </div>
      )}

      <div className="sector-layout">
        <div className="sector-list">
          {sectors.length === 0 && <p className="muted">No sector data yet — waiting for scan.</p>}
          {sectors.map((s) => {
            const name = s.name || s.sector
            return (
              <div key={name} className={'sector-row' + (sel === name ? ' active' : '')} onClick={() => setSel(name)}>
                <div className="sector-name">{name}</div>
                <div className="sector-counts">{s.count ?? s.total ?? 0} stocks · {s.hot_count ?? s.hot ?? 0} hot · {s.early_count ?? s.early ?? 0} early</div>
                {(s.rotation || s.cycle) && <div className="sector-badges"><span className="rotation-tag">{s.rotation || s.cycle}</span></div>}
              </div>
            )
          })}
        </div>
        <aside className="sector-detail panel">
          {!active && <p className="muted">Select a sector to see top picks.</p>}
          {active && (
            <>
              <h3 className="view-h3" style={{ marginTop: 0 }}>{active.name || active.sector}</h3>
              <table className="sector-picks-table">
                <thead><tr><th>Symbol</th><th>Buy</th><th>Day%</th></tr></thead>
                <tbody>
                  {(active.picks || active.stocks || []).slice(0, 20).map((p, i) => (
                    <tr key={i} onClick={() => dispatch(selectSymbol(p.symbol))} className="sector-hot-btn">
                      <td className={!p.metrics?.is_extended ? 'pick-early' : ''}>{p.symbol}</td>
                      <td>{p.metrics?.buy_score ?? p.buy_score ?? p.score ?? '—'}</td>
                      <td>{p.metrics?.day_chg_pct ?? p.day_chg_pct ?? '—'}%</td>
                    </tr>
                  ))}
                  {(!active.picks && !active.stocks) && <tr><td colSpan={3} className="muted">No picks listed.</td></tr>}
                </tbody>
              </table>
            </>
          )}
        </aside>
      </div>
    </section>
  )
}
