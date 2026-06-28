import { useAppDispatch, useAppSelector } from '../store/hooks'
import { selectSymbol } from '../store/uiSlice'
import {
  getHotPool, topPicks, flatReasons, researchOf, displayName, marketOf,
  rankScore, hasSmartMoney, isFundamentallyStrong, CURRENCY,
} from '../lib/format'
import GradeBadge from './ui/GradeBadge'
import MarketBadge from './ui/MarketBadge'
import type { Row } from '../types'

function PickCard({ row }: { row: Row }) {
  const dispatch = useAppDispatch()
  const m = row.metrics || {}
  const res = researchOf(row)
  const mkt = marketOf(row)
  const cur = CURRENCY[mkt] || '$'
  const day = Number(m.day_chg_pct ?? 0)
  const dayCls = day >= 0 ? 'pos' : 'neg'
  const reasons = flatReasons(row, 3)
  const tags = (res?.tags || []).slice(0, 3)
  const archetype = res?.archetype
  const watch = (res?.profile?.watch || [])[0]
  const buy = Math.round(rankScore(row))

  return (
    <button className="pick-card" title={`Open full analysis for ${row.symbol}`} onClick={() => dispatch(selectSymbol(row.symbol))}>
      <div className="pick-card__top">
        <GradeBadge row={row} />
        <MarketBadge market={mkt} />
        <span className="pick-card__buy" title="Buy score">{buy}</span>
      </div>
      {archetype && <div className="pick-card__arch" title="What kind of stock this is">{archetype}</div>}
      <div className="pick-card__name" title={displayName(row)}>{displayName(row)}</div>
      <div className="pick-card__sym">
        <span className="pick-card__ticker">{row.symbol}</span>
        {m.price != null ? <span className="pick-card__price">{cur}{m.price}</span> : <span className="pick-card__pending">live price pending</span>}
        <span className={'pick-card__day ' + dayCls}>{day > 0 ? '+' : ''}{day}%</span>
      </div>
      {tags.length > 0 && (
        <div className="pick-card__tags">
          {tags.map((t, i) => <span key={i} className="pick-tag">{t}</span>)}
        </div>
      )}
      <ul className="pick-card__reasons">
        {reasons.map((r, i) => (
          <li key={i}><span className="pick-reason__grp">{r.group}</span>{r.text}</li>
        ))}
      </ul>
      {watch && (
        <div className="pick-card__watch" title="A risk worth knowing before you buy">
          <span className="pick-watch__label">⚠ Watch</span>{watch}
        </div>
      )}
      {res?.reason_count && res.reason_count > reasons.length ? (
        <div className="pick-card__more">+{res.reason_count - reasons.length} more reasons →</div>
      ) : <div className="pick-card__more">See full breakdown →</div>}
    </button>
  )
}

export default function TopPicks() {
  const ui = useAppSelector((s) => s.ui)
  const data = useAppSelector((s) => s.live.data)
  const pool = getHotPool(data || {}, ui.marketFilter)
  const picks = topPicks(pool, 6)

  const strong = pool.filter(isFundamentallyStrong).length
  const whales = pool.filter(hasSmartMoney).length
  const movers = pool.filter((r) => Math.abs(Number((r.metrics || {}).day_chg_pct ?? 0)) >= 3).length

  if (picks.length === 0) {
    return (
      <section className="toppicks empty">
        <div className="toppicks__head">
          <h2>Today's Top Picks</h2>
          <span className="toppicks__sub">Scanning the market for high-quality setups…</span>
        </div>
        <p className="toppicks__placeholder">No strong setups surfaced yet for this market. Try “Scan More”, switch markets, or check back shortly — the scanner refreshes continuously.</p>
      </section>
    )
  }

  const lead = picks[0]
  const leadRes = researchOf(lead)
  const leadName = displayName(lead)

  return (
    <section className="toppicks">
      <div className="toppicks__head">
        <h2>Today's Top Picks</h2>
        <span className="toppicks__sub">Best-quality setups right now — with the reasons, not just a score</span>
      </div>
      <div className="market-read">
        <span className="market-read__lead">
          {leadRes?.grade ? <strong>{leadName}</strong> : <strong>{lead.symbol}</strong>}
          {' '}leads today{leadRes?.tags && leadRes.tags[0] ? ` — ${leadRes.tags[0].toLowerCase()}` : ''}.
        </span>
        <span className="market-read__stats">
          <b>{strong}</b> fundamentally strong · <b>{whales}</b> with smart-money buys · <b>{movers}</b> big movers
        </span>
      </div>
      <div className="picks-grid">
        {picks.map((r) => <PickCard key={r.symbol} row={r} />)}
      </div>
    </section>
  )
}
