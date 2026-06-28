import { selectSymbol, openFactors } from '../store/uiSlice'
import { useAppDispatch, useAppSelector } from '../store/hooks'
import { useAddWatchMutation, useAddPositionMutation, useAnalyzeQuery } from '../store/api'
import { getHotPool, filterAndSort, rankScore, confTier, rvolTier, marketOf, factorsDisplay, verdict, displayName, CURRENCY, DISPLAY_LIMIT } from '../lib/format'
import { useToast } from '../context/ToastContext'
import Sparkline from '../lib/Sparkline'
import MarketBadge from './ui/MarketBadge'
import BuyScorePill from './ui/BuyScorePill'
import GradeBadge from './ui/GradeBadge'
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
  const nm = displayName(row)
  // Prefer rich reasons/criteria from backend for valuable insights (fundamentals, catalysts) instead of generic sector or single alert.
  // This makes the constantly-visible table actually useful to end users.
  const richReasons = ((row as any).why_good_reasons || (m as any).reasons || (row as any).criteria || []).slice(0, 2)
  const qtag = (row.research?.tags || [])[0]
  const reason = richReasons.length > 0
    ? richReasons.map((r: any) => (typeof r === 'string' ? r : r.text || r)).join(' • ')
    : (m.smart_money?.primary_alert || qtag || (row.alerts || [])[0] || m.sector || '—')
  const vd = verdict(row)

  const watch = (e: React.MouseEvent) => { e.stopPropagation(); addWatch({ symbol: sym }); toast.push(`★ ${sym} added to My List`, 'success') }
  const paper = (e: React.MouseEvent) => {
    e.stopPropagation()
    addPosition({ symbol: sym, qty: 100, entry_price: m.price, entry_score: buy }).unwrap()
      .then(() => toast.push(`📁 Paper buy logged: ${sym}`, 'success'))
      .catch(() => toast.push(`Paper buy failed for ${sym}`, 'error'))
  }

  return (
    <tr className={selected ? 'selected' : ''} title={`Open full analysis for ${sym}${nm ? ' (' + nm + ')' : ''}`} onClick={() => dispatch(selectSymbol(sym))}>
      <td className="col-sym">
        <div className="sym">
          <MarketBadge market={mkt} />
          <button className="tiny tiny-watch" title="Add to My List" onClick={watch}>☆</button>
          <button className="tiny" title="One-click paper buy" onClick={paper}>📁</button>
          <span className="sym-main">
            <span className="sym__ticker" title={`${sym}${nm ? ' — ' + nm : ''}`}>{sym}</span>
            <GradeBadge row={row} />
            {m.price != null && <span className={'sym__price ' + dayCls} title="Last traded price">{cur}{m.price}</span>}
            <br /><span className="sym__name" title={nm}>{nm}</span>
          </span>
        </div>
      </td>
      <td className="col-trend">{row.sparkline && row.sparkline.length > 1 ? <Sparkline values={row.sparkline} /> : <span className="muted">—</span>}</td>
      <td className="col-cats">
        <div className="cats__badges">
          <CatalystBadges row={row} score={buy} />
          <button className="factor-pill" title={`${hit} of ${total} weighted factors passing — click for the full checklist`} onClick={(e) => { e.stopPropagation(); dispatch(openFactors(sym)) }}>{hit}/{total}</button>
        </div>
        <div className={'verdict verdict--' + vd.tone} title="Plain-English read of Buy vs Quality score">{vd.text}</div>
        {reason && <div className="cats__reason">{reason}</div>}
      </td>
      <td className="col-rvol"><span className={'rvol ' + rvolTier(m.rvol)} title="Relative volume vs its own average — &gt;2× means unusually active">{m.rvol != null ? m.rvol + '×' : '—'}</span></td>
      <td className="col-conf">{m.confidence_score == null ? <span className="muted">—</span> : <span className={'conf ' + confTier(m.confidence_score)} title="Confidence in the setup (data quality + signal agreement)">{m.confidence_score}</span>}</td>
      <td className="col-day"><span className={'day ' + dayCls} title="Change since previous close">{day > 0 ? '▲ +' : day < 0 ? '▼ ' : ''}{day}%</span></td>
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
