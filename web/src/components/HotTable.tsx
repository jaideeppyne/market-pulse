import { selectSymbol, openFactors } from '../store/uiSlice'
import { useAppDispatch, useAppSelector } from '../store/hooks'
import { useAddWatchMutation, useAddPositionMutation, useAnalyzeQuery } from '../store/api'
import { getHotPool, filterAndSort, rankScore, confTier, rvolTier, marketOf, factorsDisplay, CURRENCY, DISPLAY_LIMIT } from '../lib/format'
import { useToast } from '../context/ToastContext'
import Sparkline from '../lib/Sparkline'
import MarketBadge from './ui/MarketBadge'
import BuyScorePill from './ui/BuyScorePill'
import CatalystBadges from './ui/CatalystBadges'
import type { Row } from '../types'

const COLS = [
  ['col-sym', 'Symbol'], ['col-trend', 'Trend'], ['col-cats', 'Catalysts & Reasons'],
  ['col-rvol', 'Rel Vol'], ['col-conf', 'Conf'], ['col-day', 'Day Δ'], ['col-buy', 'Buy Score'],
] as const

function HotRow({ row, selected }: { row: Row; selected: boolean }) {
  const dispatch = useAppDispatch()
  const [addWatch] = useAddWatchMutation()
  const [addPosition] = useAddPositionMutation()
  const toast = useToast()
  const m = row.metrics || {}
  const sym = row.symbol
  const buy = rankScore(row)
  const day = Number(m.day_chg_pct ?? 0)
  const dayCls = day >= 0 ? 'pos' : 'neg'
  const mkt = marketOf(row)
  const cur = CURRENCY[mkt] || '$'
  const { hit, total } = factorsDisplay(row)
  const reason = m.smart_money?.primary_alert || (row.alerts || [])[0] || m.sector

  const watch = (e: React.MouseEvent) => { e.stopPropagation(); addWatch({ symbol: sym }); toast.push(`★ ${sym} added to My List`, 'success') }
  const paper = (e: React.MouseEvent) => {
    e.stopPropagation()
    addPosition({ symbol: sym, qty: 100, entry_price: m.price, entry_score: buy }).unwrap()
      .then(() => toast.push(`📁 Paper buy logged: ${sym}`, 'success'))
      .catch(() => toast.push(`Paper buy failed for ${sym}`, 'error'))
  }

  return (
    <tr className={selected ? 'selected' : ''} onClick={() => dispatch(selectSymbol(sym))}>
      <td className="col-sym">
        <div className="sym">
          <MarketBadge market={mkt} />
          <button className="tiny tiny-watch" title="Add to My List" onClick={watch}>☆</button>
          <button className="tiny" title="One-click paper buy" onClick={paper}>📁</button>
          <span className="sym-main">
            <span className="sym__ticker">{sym}</span>
            {m.price != null && <span className={'sym__price ' + dayCls}>{cur}{m.price}</span>}
            <br /><span className="sym__name">{m.name || m.sector || mkt.toUpperCase()}</span>
          </span>
        </div>
      </td>
      <td className="col-trend">{row.sparkline && row.sparkline.length > 1 ? <Sparkline values={row.sparkline} /> : <span className="muted">—</span>}</td>
      <td className="col-cats">
        <div className="cats__badges">
          <CatalystBadges row={row} score={buy} />
          <button className="factor-pill" title="View factors" onClick={(e) => { e.stopPropagation(); dispatch(openFactors(sym)) }}>{hit}/{total}</button>
        </div>
        {reason && <div className="cats__reason">{reason}</div>}
      </td>
      <td className="col-rvol"><span className={'rvol ' + rvolTier(m.rvol)}>{m.rvol != null ? m.rvol + '×' : '—'}</span></td>
      <td className="col-conf">{m.confidence_score == null ? <span className="muted">—</span> : <span className={'conf ' + confTier(m.confidence_score)}>{m.confidence_score}</span>}</td>
      <td className="col-day"><span className={'day ' + dayCls}>{day > 0 ? '▲ +' : day < 0 ? '▼ ' : ''}{day}%</span></td>
      <td className="col-buy">
        <BuyScorePill score={buy} quality={m.quality_score ?? '—'} onClick={(e) => { e.stopPropagation(); dispatch(openFactors(sym)) }} />
      </td>
    </tr>
  )
}

export default function HotTable() {
  const data = useAppSelector((s) => s.live.data)
  const ui = useAppSelector((s) => s.ui)
  const selected = useAppSelector((s) => s.ui.selectedSymbol)

  const pool = getHotPool(data || {}, ui.marketFilter as any)
  const selectedInPool = selected && pool.some((r) => r.symbol === selected)
  const { data: analyzed } = useAnalyzeQuery(selected, { skip: !selected || selectedInPool })
  const filteredRows = filterAndSort(pool, ui)
  const analyzedRow = analyzed?.symbol && analyzed?.metrics && !analyzed?.error ? analyzed : null
  const rows = [
    ...(analyzedRow && !filteredRows.some((r) => r.symbol === analyzedRow.symbol) ? [analyzedRow] : []),
    ...filteredRows,
  ].slice(0, DISPLAY_LIMIT)
  const marketLabel = ui.marketFilter === 'all' ? 'all markets' : ui.marketFilter.toUpperCase()

  return (
    <div className="table-wrap">
      <table className="grid-table">
        <thead>
          <tr>{COLS.map(([cls, label]) => <th key={cls} className={cls}>{label}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((r) => <HotRow key={r.symbol} row={r} selected={selected === r.symbol} />)}
        </tbody>
      </table>
      {rows.length === 0 && <p className="panel-hint">No {marketLabel} names match the current filters — scanning, or clear filters.</p>}
    </div>
  )
}
