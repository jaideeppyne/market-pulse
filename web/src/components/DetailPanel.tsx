import { useAnalyzeQuery, useAddWatchMutation, useAddPositionMutation } from '../store/api'
import { openFactors, selectSymbol } from '../store/uiSlice'
import { useAppDispatch, useAppSelector } from '../store/hooks'
import { confTier, marketOf, factorsDisplay, displayName, companyName, whaleView, CURRENCY, researchOf } from '../lib/format'
import { useToast } from '../context/ToastContext'
import Sparkline from '../lib/Sparkline'
import BuyScorePill from './ui/BuyScorePill'
import MarketBadge from './ui/MarketBadge'
import GradeBadge from './ui/GradeBadge'

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
  const { data: fetched, isFetching } = useAnalyzeQuery(sym || '', { skip: !needFetch })
  const [addWatch] = useAddWatchMutation()
  const [addPosition] = useAddPositionMutation()
  const toast = useToast()

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
    const err = (row as { error?: string } | null)?.error || (fetched as { error?: string } | undefined)?.error
    const es = String(err || '').toLowerCase()
    const msg = err
      ? (es.includes('rate') || es.includes('429') ? `Too many searches just now — wait a few seconds and try ${sym} again.`
        : es.includes('invalid') ? `"${sym}" doesn't look like a valid ticker.`
        : es.includes('no data') ? `No market data found for ${sym} — it may be delisted, mistyped, or not covered.`
        : `Couldn't analyze ${sym}: ${err}`)
      : (isFetching ? `Analyzing ${sym}…` : `No data yet for ${sym}`)
    return (
      <div className="detail-panel">
        <h2 className="detail-panel__title">Stock detail</h2>
        <div className="detail-empty"><p>{msg}</p><p className="muted">{err ? 'Check the symbol, or try one from the Hot Movers table.' : 'Running the full engine'}</p></div>
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
  const research = researchOf(row)
  const passed = (row.factor_breakdown || []).filter((x) => x.status === 'pass')
  const risk = (row.factor_breakdown || []).filter((x) => x.status === 'risk')
  const failed = (row.factor_breakdown || []).filter((x) => x.status === 'fail')
  const smHits = (m.smart_money?.hits || []).map((h) => whaleView(h)).filter((w) => w.investor)

  const watch = () => { addWatch({ symbol: sym }); toast.push(`★ ${sym} added to My List`, 'success') }
  const paper = () => addPosition({ symbol: sym, qty: 100, entry_price: m.price, entry_score: buy }).unwrap()
    .then(() => toast.push(`📁 Paper buy logged: ${sym}`, 'success'))
    .catch(() => toast.push(`Paper buy failed for ${sym}`, 'error'))

  return (
    <div className="detail-panel">
      <h2 className="detail-panel__title">Stock detail</h2>
      <div className="detail">
        <h3 onClick={() => dispatch(openFactors(sym))} title={`${row.symbol}${companyName(row) ? ' — ' + companyName(row) : ''} · open factor breakdown`}>
          <MarketBadge market={mkt} /> {row.symbol}
        </h3>
        <div className="meta-line" title={companyName(row) || m.sector || ''}>{displayName(row)}{m.sector && companyName(row) ? ` · ${m.sector}` : ''}</div>
        <div className="meta-line"><span className="sym__ticker">{cur}{m.price}</span> <span className={'day ' + dayCls}>{day > 0 ? '+' : ''}{day}%</span> <span className="muted">· rel vol {m.rvol ?? '—'}×</span></div>

        <div className="detail-score-row">
          <BuyScorePill score={buy} quality={m.quality_score ?? '—'} onClick={() => dispatch(openFactors(sym))} />
          {m.confidence_score != null && <span className={'conf-pill conf-' + (cf === 'hi' ? 'high' : cf === 'mid' ? 'med' : 'low')}>Conf {m.confidence_score}</span>}
          {m.is_extended && <span className="ext-badge">Extended</span>}
        </div>

        {row.sparkline && row.sparkline.length > 1 && <div className="spark-large"><Sparkline values={row.sparkline} w={300} h={70} /></div>}

        <div className="factor-summary" style={{ cursor: 'pointer' }} title="Click to open the full factor breakdown" onClick={() => dispatch(openFactors(sym))}>
          <span className="fs pass">{passed.length} passed</span>
          {risk.length > 0 && <span className="fs risk">{risk.length} risk</span>}
          <span className="fs fail">{failed.length} failed</span>
        </div>

        {/* Primary value: graded multi-reason research card (grade + grouped reasons + tags) */}
        {research && (research.groups?.length || research.tags?.length) ? (
          <div className="research-card">
            <div className="research-head">
              <GradeBadge row={row} showTag={false} />
              <span className="research-head__txt">
                {research.fundamentally_strong ? 'Fundamentally strong on NSE/BSE' : 'Quality read'}
                {research.reason_count ? ` · ${research.reason_count} reasons` : ''}
              </span>
            </div>
            {research.tags && research.tags.length > 0 && (
              <div className="research-tags">
                {research.tags.map((t, i) => <span key={i} className="research-tag">{t}</span>)}
              </div>
            )}
            <p className="section-label">Why it stands out</p>
            <div className="research-groups">
              {(research.groups || []).map((g, gi) => (
                <div key={gi} className="research-group">
                  <div className="research-group__title">{g.title}</div>
                  <ul className="research-group__list">
                    {g.reasons.map((r, ri) => <li key={ri}>{r}</li>)}
                  </ul>
                </div>
              ))}
            </div>
          </div>
        ) : null}

        {/* Fallback thesis from backend reasons when no graded research is available */}
        {!research && (((row as any).why_good_reasons && (row as any).why_good_reasons.length > 0) || ((row as any).criteria && (row as any).criteria.length > 0)) ? (
          <>
            <p className="section-label">Why this stock stands out</p>
            <ul className="reasons-list">
              {((row as any).why_good_reasons || (row as any).criteria || []).slice(0, 5).map((r: any, i: number) => {
                const text = typeof r === 'string' ? r : (r.text || r.label || JSON.stringify(r));
                return <li key={i}>{text}</li>;
              })}
            </ul>
            {(row as any).thesis && <p className="thesis-summary muted">{(row as any).thesis}</p>}
          </>
        ) : passed.length > 0 && (
          <>
            <p className="section-label">Top passed checks</p>
            <div className="factor-chips">
              {passed.slice(0, 10).map((f, i) => <span key={i} className="chip-pass" title={f.description}>{f.name}</span>)}
              {passed.length > 10 && <span className="chip-more">+{passed.length - 10} more</span>}
            </div>
          </>
        )}

        {smHits.length > 0 && (
          <div className="detail-whales">
            <p className="section-label">Smart money</p>
            {smHits.slice(0, 4).map((w, i) => (
              <div key={i} className="whale-mini" title={w.blurb || w.investor}>
                <span className="whale-mini__name">{w.investor}</span>
                {w.typeLabel && <span className={'whale-type whale-type--' + w.typeLabel.toLowerCase()}>{w.typeLabel}</span>}
                {w.conviction && <span className="whale-conv">{w.conviction}</span>}
                {w.action && <span className="whale-action">{w.action}</span>}
                {w.recency && <span className="whale-mini__time muted">{w.recency}</span>}
                {w.blurb && <span className="whale-mini__blurb">{w.blurb}</span>}
              </div>
            ))}
          </div>
        )}

        {row.alerts && row.alerts.length > 0 && <ul className="alerts">{row.alerts.slice(0, 6).map((a, i) => <li key={i}>{a}</li>)}</ul>}

        <div className="thesis-head" style={{ marginTop: 12 }}>
          <button className="tiny" title="Open the full weighted factor checklist" onClick={() => dispatch(openFactors(sym))}>Factors {hit}/{total}</button>
          <button className="tiny" title="Add this stock to My List (watchlist)" onClick={watch}>★ Watch</button>
          <button className="tiny" title="Log a one-click paper buy (100 shares at current price)" onClick={paper}>📁 Paper</button>
          <button className="tiny" title="Close this detail panel" onClick={() => dispatch(selectSymbol(null))}>Close</button>
        </div>
      </div>
    </div>
  )
}
