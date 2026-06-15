import { useSelector, useDispatch } from 'react-redux'
import { useAnalyzeQuery } from '../store/api'
import { openFactors, selectSymbol } from '../store/uiSlice'
import { useAddWatchMutation, useAddPositionMutation } from '../store/api'
import { buyTier, confTier, marketOf, factorsDisplay } from '../lib/format'
import Sparkline from '../lib/Sparkline'

export default function DetailPanel() {
  const dispatch = useDispatch()
  const sym = useSelector((s) => s.ui.selectedSymbol)
  // try to find it already in the live snapshot first
  const liveRow = useSelector((s) => {
    if (!sym || !s.live.data) return null
    const pools = [...(s.live.data.hot || []), ...((s.live.data.hot_by_market?.us) || []), ...((s.live.data.hot_by_market?.india) || [])]
    return pools.find((r) => r.symbol === sym) || null
  })
  const needFetch = !!sym && (!liveRow || !liveRow.factor_breakdown)
  const { data: fetched, isFetching } = useAnalyzeQuery(sym, { skip: !needFetch })
  const [addWatch] = useAddWatchMutation()
  const [addPosition] = useAddPositionMutation()

  const row = (fetched && fetched.symbol) ? fetched : liveRow

  if (!sym) {
    return (
      <div className="detail-panel">
        <h2 className="detail-panel__title">Stock detail</h2>
        <div className="detail-empty"><p>Pick a stock from the table</p><p className="muted">Score, factor checklist, alerts, chart</p></div>
      </div>
    )
  }
  if (!row || !row.metrics) {
    return (
      <div className="detail-panel">
        <h2 className="detail-panel__title">Stock detail</h2>
        <div className="detail-empty"><p>{isFetching ? `Analyzing ${sym}…` : `No data yet for ${sym}`}</p><p className="muted">Running the full engine</p></div>
      </div>
    )
  }

  const m = row.metrics
  const buy = Number(m.buy_score ?? row.score ?? 0)
  const [tierCls, tierLbl] = buyTier(buy)
  const cf = confTier(m.confidence_score)
  const day = Number(m.day_chg_pct ?? 0)
  const dayCls = day >= 0 ? 'pos' : 'neg'
  const cur = marketOf(row) === 'india' ? '₹' : '$'
  const { hit, total } = factorsDisplay(row)
  const passed = (row.factor_breakdown || []).filter((x) => x.status === 'pass')
  const risk = (row.factor_breakdown || []).filter((x) => x.status === 'risk')
  const failed = (row.factor_breakdown || []).filter((x) => x.status === 'fail')

  return (
    <div className="detail-panel">
      <h2 className="detail-panel__title">Stock detail</h2>
      <div className="detail">
        <h3 onClick={() => dispatch(openFactors(sym))} title="Open factor breakdown">{row.symbol}</h3>
        <div className="meta-line">{m.name || ''}{m.sector ? ` · ${m.sector}` : ''} · {marketOf(row).toUpperCase()}</div>
        <div className="meta-line"><span className="sym__ticker">{cur}{m.price}</span> <span className={'day ' + dayCls}>{day > 0 ? '+' : ''}{day}%</span> <span className="muted">· rel vol {m.rvol ?? '—'}×</span></div>

        <div className="detail-score-row">
          <span className={'buy ' + tierCls} onClick={() => dispatch(openFactors(sym))} title="Click for factor breakdown" style={{ cursor: 'pointer' }}>
            <span className="buy__meta"><span className="buy__tier">{tierLbl}</span><div className="buy__q">Q {m.quality_score ?? '—'}</div></span>
            <span className="buy__pill"><span>{Math.round(buy)}</span></span>
          </span>
          {m.confidence_score != null && <span className={'conf-pill conf-' + (cf === 'hi' ? 'high' : cf === 'mid' ? 'med' : 'low')}>Conf {m.confidence_score}</span>}
          {m.is_extended && <span className="ext-badge">Extended</span>}
        </div>

        {row.sparkline?.length > 1 && <div className="spark-large"><Sparkline values={row.sparkline} w={300} h={70} /></div>}

        <div className="factor-summary" style={{ cursor: 'pointer' }} onClick={() => dispatch(openFactors(sym))}>
          <span className="fs pass">{passed.length} passed</span>
          {risk.length > 0 && <span className="fs risk">{risk.length} risk</span>}
          <span className="fs fail">{failed.length} failed</span>
        </div>

        {passed.length > 0 && (
          <>
            <p className="section-label">Top passed checks</p>
            <div className="factor-chips">
              {passed.slice(0, 10).map((f, i) => <span key={i} className="chip-pass" title={f.description}>{f.name}</span>)}
              {passed.length > 10 && <span className="chip-more">+{passed.length - 10} more</span>}
            </div>
          </>
        )}

        {row.alerts?.length > 0 && <ul className="alerts">{row.alerts.slice(0, 6).map((a, i) => <li key={i}>{a}</li>)}</ul>}

        <div className="thesis-head" style={{ marginTop: 12 }}>
          <button className="tiny" onClick={() => dispatch(openFactors(sym))}>Factors {hit}/{total}</button>
          <button className="tiny" onClick={() => addWatch({ symbol: sym })}>★ Watch</button>
          <button className="tiny" onClick={() => addPosition({ symbol: sym, qty: 100, entry_price: m.price, entry_score: buy }).unwrap().catch(() => {})}>📁 Paper</button>
          <button className="tiny" onClick={() => dispatch(selectSymbol(null))}>Close</button>
        </div>
      </div>
    </div>
  )
}
