import { useAnalyzeQuery, useAddWatchMutation, useAddPositionMutation } from '../store/api'
import { openFactors, selectSymbol } from '../store/uiSlice'
import { useAppDispatch, useAppSelector } from '../store/hooks'
import { confTier, marketOf, factorsDisplay, CURRENCY } from '../lib/format'
import { useToast } from '../context/ToastContext'
import Sparkline from '../lib/Sparkline'
import BuyScorePill from './ui/BuyScorePill'
import MarketBadge from './ui/MarketBadge'

export default function DetailPanel() {
  const dispatch = useAppDispatch()
  const sym = useAppSelector((s) => s.ui.selectedSymbol)
  const liveRow = useAppSelector((s) => {
    if (!sym || !s.live.data) return null
    const hbm = s.live.data.hot_by_market || {}
    const pools = [...(s.live.data.hot || []), ...(hbm.us || []), ...(hbm.india || []), ...(hbm.uk || [])]
    return pools.find((r) => r.symbol === sym) || null
  })
  const needFetch = !!sym && (!liveRow || !liveRow.factor_breakdown)
  const { data: fetched, isFetching, isError, error } = useAnalyzeQuery(sym, { skip: !needFetch })
  const [addWatch] = useAddWatchMutation()
  const [addPosition] = useAddPositionMutation()
  const toast = useToast()

  const row = (fetched && fetched.symbol) ? fetched : liveRow
  const queryError = error as any
  const errorText = fetched?.error || queryError?.error || queryError?.data?.detail || 'No market data returned for this symbol.'

  if (!sym) {
    return (
      <div className="detail-panel">
        <h2 className="detail-panel__title">Stock detail</h2>
        <div className="detail-empty"><p>Pick a stock from the table</p><p className="muted">Score, factor checklist, alerts, chart</p></div>
      </div>
    )
  }
  if (fetched?.error || isError) {
    return (
      <div className="detail-panel">
        <h2 className="detail-panel__title">Stock detail</h2>
        <div className="detail-empty detail-empty--error">
          <p>Could not analyze {sym}</p>
          <p className="muted">{errorText}</p>
        </div>
      </div>
    )
  }
  if (!row || !row.metrics) {
    return (
      <div className="detail-panel">
        <h2 className="detail-panel__title">Stock detail</h2>
        <div className="detail-empty"><p>{isFetching ? `Analyzing ${sym}…` : `No data yet for ${sym}`}</p><p className="muted">{isFetching ? 'Running yfinance history, fundamentals, news, smart money, and factor engine.' : 'Press Enter in search or use Analyze again.'}</p></div>
      </div>
    )
  }

  const m = row.metrics
  const buy = Number(m.buy_score ?? row.score ?? 0)
  const cf = confTier(m.confidence_score)
  const day = Number(m.day_chg_pct ?? 0)
  const dayCls = day >= 0 ? 'pos' : 'neg'
  const mkt = marketOf(row)
  const cur = CURRENCY[mkt] || '$'
  const { hit, total } = factorsDisplay(row)
  const passed = (row.factor_breakdown || []).filter((x) => x.status === 'pass')
  const risk = (row.factor_breakdown || []).filter((x) => x.status === 'risk')
  const failed = (row.factor_breakdown || []).filter((x) => x.status === 'fail')

  const watch = () => { addWatch({ symbol: sym }); toast.push(`★ ${sym} added to My List`, 'success') }
  const paper = () => addPosition({ symbol: sym, qty: 100, entry_price: m.price, entry_score: buy }).unwrap()
    .then(() => toast.push(`📁 Paper buy logged: ${sym}`, 'success'))
    .catch(() => toast.push(`Paper buy failed for ${sym}`, 'error'))

  return (
    <div className="detail-panel">
      <h2 className="detail-panel__title">Stock detail</h2>
      <div className="detail">
        <h3 onClick={() => dispatch(openFactors(sym))} title="Open factor breakdown">
          <MarketBadge market={mkt} /> {row.symbol}
        </h3>
        <div className="meta-line">{m.name || ''}{m.sector ? ` · ${m.sector}` : ''}</div>
        <div className="meta-line"><span className="sym__ticker">{cur}{m.price}</span> <span className={'day ' + dayCls}>{day > 0 ? '+' : ''}{day}%</span> <span className="muted">· rel vol {m.rvol ?? '—'}×</span></div>

        <div className="detail-score-row">
          <BuyScorePill score={buy} quality={m.quality_score ?? '—'} onClick={() => dispatch(openFactors(sym))} />
          {m.confidence_score != null && <span className={'conf-pill conf-' + (cf === 'hi' ? 'high' : cf === 'mid' ? 'med' : 'low')}>Conf {m.confidence_score}</span>}
          {m.is_extended && <span className="ext-badge">Extended</span>}
        </div>

        {row.sparkline && row.sparkline.length > 1 && <div className="spark-large"><Sparkline values={row.sparkline} w={300} h={70} /></div>}

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

        {row.alerts && row.alerts.length > 0 && <ul className="alerts">{row.alerts.slice(0, 6).map((a, i) => <li key={i}>{a}</li>)}</ul>}

        <div className="thesis-head" style={{ marginTop: 12 }}>
          <button className="tiny" onClick={() => dispatch(openFactors(sym))}>Factors {hit}/{total}</button>
          <button className="tiny" onClick={watch}>★ Watch</button>
          <button className="tiny" onClick={paper}>📁 Paper</button>
          <button className="tiny" onClick={() => dispatch(selectSymbol(null))}>Close</button>
        </div>
      </div>
    </div>
  )
}
