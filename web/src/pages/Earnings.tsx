import { useSelector, useDispatch } from 'react-redux'
import { selectSymbol } from '../store/uiSlice'

export default function Earnings() {
  const dispatch = useDispatch()
  const rows = useSelector((s) => s.live.data?.earnings) || []

  return (
    <section className="panel pad">
      <h2 className="view-h">Earnings &amp; results <span className="hint">{rows.length ? `(${rows.length})` : ''}</span></h2>
      <p className="panel-hint">Stocks reporting soon (calendar + news buzz). Click a row for full analysis.</p>
      <div className="table-wrap">
        <table className="data-table">
          <thead><tr><th>Symbol</th><th>Date</th><th>In</th><th>EPS est</th><th>Score</th><th>Day%</th></tr></thead>
          <tbody>
            {rows.length === 0 && <tr><td colSpan={6} className="muted">No upcoming earnings loaded yet.</td></tr>}
            {rows.map((e, i) => {
              const di = e.days_until
              const inTxt = di === 0 ? 'TODAY' : di != null ? `${di}d` : '—'
              return (
                <tr key={(e.symbol || '') + i} onClick={() => dispatch(selectSymbol(e.symbol))}>
                  <td className="symbol-cell">{e.symbol}</td>
                  <td className="muted">{e.date || e.report_date || '—'}</td>
                  <td>{inTxt}</td>
                  <td>{e.eps_est ?? e.eps_estimate ?? '—'}</td>
                  <td>{e.score ?? e.buy_score ?? '—'}</td>
                  <td className={(e.day_chg_pct ?? 0) >= 0 ? 'pos' : 'neg'}>{e.day_chg_pct != null ? e.day_chg_pct + '%' : '—'}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </section>
  )
}
