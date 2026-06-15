import { useSelector, useDispatch } from 'react-redux'
import { selectSymbol, openFactors } from '../store/uiSlice'
import { useAddWatchMutation, useAddPositionMutation } from '../store/api'
import { getHotPool, filterAndSort, rankScore, buyTier, confTier, rvolTier, marketOf, hasSmartMoney, factorsDisplay, DISPLAY_LIMIT } from '../lib/format'
import Sparkline from '../lib/Sparkline'

function catalystBadges(r, buy) {
  const out = []
  const sm = r.metrics?.smart_money
  if (sm?.hits?.length || hasSmartMoney(r)) {
    const sTier = (sm?.hits?.[0]?.tier || '').toUpperCase()
    if (sTier.includes('S') || buy >= 90) out.push(<span key="sp" className="cat-badge sp">S+</span>)
    else out.push(<span key="sm" className="cat-badge sm">Smart Money</span>)
  }
  if ((r.news && r.news.length) || r.metrics?.news_count || (r.alerts || []).some((a) => /news|headline/i.test(a)))
    out.push(<span key="news" className="cat-badge news">News</span>)
  if (r.earnings || r.metrics?.earnings_pre || r.earnings_soon || r.metrics?.days_until_earnings != null)
    out.push(<span key="earn" className="cat-badge earn">Earnings</span>)
  if (r.metrics?.is_extended) out.push(<span key="ext" className="cat-badge risk">Extended</span>)
  if (r.discovered) out.push(<span key="disc" className="cat-badge sm">DISC</span>)
  if (r.full_exhaustive) out.push(<span key="full" className="cat-badge news">FULL</span>)
  return out
}

export default function HotTable() {
  const dispatch = useDispatch()
  const data = useSelector((s) => s.live.data)
  const ui = useSelector((s) => s.ui)
  const selected = useSelector((s) => s.ui.selectedSymbol)
  const [addWatch] = useAddWatchMutation()
  const [addPosition] = useAddPositionMutation()

  const pool = getHotPool(data || {}, ui.marketFilter)
  const rows = filterAndSort(pool, ui).slice(0, DISPLAY_LIMIT)
  const marketLabel = ui.marketFilter === 'all' ? 'all markets' : ui.marketFilter.toUpperCase()

  return (
    <div className="table-wrap">
      <table className="grid-table">
        <thead>
          <tr>
            <th className="col-sym">Symbol</th>
            <th className="col-trend">Trend</th>
            <th className="col-cats">Catalysts &amp; Reasons</th>
            <th className="col-rvol">Rel Vol</th>
            <th className="col-conf">Conf</th>
            <th className="col-day">Day Δ</th>
            <th className="col-buy">Buy Score</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => {
            const m = r.metrics || {}
            const buy = rankScore(r)
            const [tierCls, tierLbl] = buyTier(buy)
            const day = Number(m.day_chg_pct ?? 0)
            const dayCls = day >= 0 ? 'pos' : 'neg'
            const mkt = marketOf(r)
            const cur = mkt === 'india' ? '₹' : '$'
            const cf = confTier(m.confidence_score)
            const watched = false
            const sym = r.symbol
            const { hit, total } = factorsDisplay(r)
            return (
              <tr key={sym} className={selected === sym ? 'selected' : ''} onClick={() => dispatch(selectSymbol(sym))}>
                <td className="col-sym">
                  <div className="sym">
                    <span className={'mkt ' + (mkt === 'india' ? 'in' : 'us')}>{mkt === 'india' ? 'IN' : 'US'}</span>
                    <button className="tiny tiny-watch" title="Add to My List" onClick={(e) => { e.stopPropagation(); addWatch({ symbol: sym }) }}>☆</button>
                    <button className="tiny" title="One-click paper buy" onClick={(e) => { e.stopPropagation(); addPosition({ symbol: sym, qty: 100, entry_price: m.price, entry_score: buy }).unwrap().catch(() => {}) }}>📁</button>
                    <span className="sym-main">
                      <span className="sym__ticker">{sym}</span>
                      {m.price != null && <span className={'sym__price ' + dayCls}>{cur}{m.price}</span>}
                      <br /><span className="sym__name">{m.name || m.sector || mkt.toUpperCase()}</span>
                    </span>
                  </div>
                </td>
                <td className="col-trend">{r.sparkline?.length > 1 ? <Sparkline values={r.sparkline} /> : <span className="muted">—</span>}</td>
                <td className="col-cats">
                  <div className="cats__badges">
                    {catalystBadges(r, buy)}
                    <button className="factor-pill" title="View factors" onClick={(e) => { e.stopPropagation(); dispatch(openFactors(sym)) }}>{hit}/{total}</button>
                  </div>
                  {(m.smart_money?.primary_alert || (r.alerts || [])[0] || m.sector) &&
                    <div className="cats__reason">{m.smart_money?.primary_alert || (r.alerts || [])[0] || m.sector}</div>}
                </td>
                <td className="col-rvol"><span className={'rvol ' + rvolTier(m.rvol)}>{m.rvol != null ? m.rvol + '×' : '—'}</span></td>
                <td className="col-conf">{m.confidence_score == null ? <span className="muted">—</span> : <span className={'conf ' + cf}>{m.confidence_score}</span>}</td>
                <td className="col-day"><span className={'day ' + dayCls}>{day > 0 ? '▲ +' : day < 0 ? '▼ ' : ''}{day}%</span></td>
                <td className="col-buy">
                  <div className={'buy ' + tierCls} onClick={(e) => { e.stopPropagation(); dispatch(openFactors(sym)) }} style={{ cursor: 'pointer' }}>
                    <span className="buy__meta"><span className="buy__tier">{tierLbl}</span><div className="buy__q">Q {m.quality_score ?? '—'}</div></span>
                    <span className="buy__pill"><span>{Math.round(buy)}</span></span>
                  </div>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
      {rows.length === 0 && <p className="panel-hint">No {marketLabel} names match the current filters — scanning, or clear filters.</p>}
    </div>
  )
}
