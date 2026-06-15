import { useSelector, useDispatch } from 'react-redux'
import { selectSymbol } from '../store/uiSlice'
import { hasSmartMoney, getHotPool } from '../lib/format'

export default function Radar() {
  const dispatch = useDispatch()
  const data = useSelector((s) => s.live.data)
  const events = data?.investor_events || []
  const hot = getHotPool(data || {}, 'all').filter(hasSmartMoney)

  const items = []
  for (const ev of events.slice(-40).reverse()) {
    items.push({ symbol: ev.symbol, name: ev.investor_name || ev.actor_name || ev.name || 'Smart money', kind: ev.kind || ev.event_type, text: ev.details || ev.headline || '' })
  }
  for (const r of hot) {
    const sm = r.metrics?.smart_money
    const hit = sm?.hits?.[0]
    items.push({ symbol: r.symbol, name: hit?.name || sm?.primary_alert || 'Smart money', kind: hit?.kind || 'signal', text: sm?.primary_alert || (r.alerts || [])[0] || '' })
  }
  const seen = new Set()
  const uniq = items.filter((it) => { const k = it.symbol + it.name; if (seen.has(k)) return false; seen.add(k); return true })

  return (
    <section className="panel pad">
      <h2 className="view-h">S+ Radar <span className="view-h__sub">Named smart money &amp; politician activity</span></h2>
      <p className="panel-hint">Legends, politicians, and FII flows surfaced from news intel + the smart_money registry. Click any row to inspect.</p>
      <div className="radar-list">
        {uniq.length === 0 && <p className="muted">No named smart-money activity in the current scan window.</p>}
        {uniq.map((it, i) => (
          <div key={i} className="radar-row" onClick={() => dispatch(selectSymbol(it.symbol))}>
            <div className="whale-hit">{it.name} <span className="muted">· {it.symbol}</span> {it.kind && <span className="cat-badge sm" style={{ marginLeft: 6 }}>{String(it.kind).replace('_', ' ')}</span>}</div>
            {it.text && <div className="whale-intel">{it.text}</div>}
          </div>
        ))}
      </div>
    </section>
  )
}
