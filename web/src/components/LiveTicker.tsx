import { useAppSelector } from '../store/hooks'
import { useAppDispatch } from '../store/hooks'
import { selectSymbol } from '../store/uiSlice'
import { getHotPool, researchOf, marketOf, CURRENCY } from '../lib/format'
import type { Row } from '../types'

function Item({ row }: { row: Row }) {
  const dispatch = useAppDispatch()
  const m = row.metrics || {}
  const mkt = marketOf(row)
  const cur = CURRENCY[mkt] || '$'
  const day = Number(m.day_chg_pct ?? 0)
  const cls = day >= 0 ? 'pos' : 'neg'
  const grade = researchOf(row)?.grade
  return (
    <button className="tick-item" title={`Open ${row.symbol}`} onClick={() => dispatch(selectSymbol(row.symbol))}>
      <span className="tick-sym">{row.symbol}</span>
      {m.price != null && <span className="tick-price">{cur}{m.price}</span>}
      <span className={'tick-day ' + cls}>{day > 0 ? '▲' : day < 0 ? '▼' : '·'}{Math.abs(day)}%</span>
      {grade && <span className={'tick-grade g-' + grade.replace('+', 'p')}>{grade}</span>}
    </button>
  )
}

export default function LiveTicker() {
  const data = useAppSelector((s) => s.live.data)
  const pool = getHotPool(data || {}, 'all')
  // sort: graded/strong first, then by absolute day move, cap for a tidy tape
  const items = [...pool]
    .sort((a, b) => {
      const ga = researchOf(a)?.grade ? 1 : 0
      const gb = researchOf(b)?.grade ? 1 : 0
      if (ga !== gb) return gb - ga
      return Math.abs(Number((b.metrics || {}).day_chg_pct ?? 0)) - Math.abs(Number((a.metrics || {}).day_chg_pct ?? 0))
    })
    .slice(0, 28)

  if (items.length === 0) {
    return (
      <div className="live-ticker live-ticker--empty">
        <span className="tick-live"><span className="tick-dot" />LIVE</span>
        <span className="tick-warming">Markets warming up — first prices streaming in…</span>
      </div>
    )
  }

  // duplicate the list for a seamless infinite scroll
  const loop = [...items, ...items]
  return (
    <div className="live-ticker">
      <span className="tick-live"><span className="tick-dot" />LIVE</span>
      <div className="tick-track-wrap">
        <div className="tick-track">
          {loop.map((r, i) => <Item key={r.symbol + i} row={r} />)}
        </div>
      </div>
    </div>
  )
}
