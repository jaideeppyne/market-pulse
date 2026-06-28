import StatCards from '../components/StatCards'
import HotTable from '../components/HotTable'
import IntelFeed from '../components/IntelFeed'
import DetailPanel from '../components/DetailPanel'
import { useLazyDiscoverQuery, useStartFullScanMutation } from '../store/api'
import { useAppDispatch, useAppSelector } from '../store/hooks'
import {
  setMarketFilter, toggleEarly, toggleWhale, setSortBy, selectSymbol, setSearch,
} from '../store/uiSlice'
import { getHotPool, filterAndSort, DISPLAY_LIMIT, rankScore, hasSmartMoney } from '../lib/format'
import type { MarketFilter, Row, SortBy } from '../types'

const SORTS = [
  ['score', 'Buy score'], ['quality', 'Quality score'], ['factors', 'Factors hit'],
  ['day', 'Day %'], ['rvol', 'Volume'],
]

function exportCsv(rows: Row[]) {
  const head = ['symbol', 'buy_score', 'quality', 'day_pct', 'rvol', 'confidence', 'market']
  const lines = [head.join(',')]
  for (const r of rows) {
    const m = r.metrics || {}
    lines.push([r.symbol, m.buy_score ?? r.score ?? '', m.quality_score ?? '', m.day_chg_pct ?? '', m.rvol ?? '', m.confidence_score ?? '', r.market ?? ''].join(','))
  }
  const blob = new Blob([lines.join('\n')], { type: 'text/csv' })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = 'hot-movers.csv'
  a.click()
  URL.revokeObjectURL(a.href)
}

export default function CommandCenter() {
  const dispatch = useAppDispatch()
  const ui = useAppSelector((s) => s.ui)
  const data = useAppSelector((s) => s.live.data)
  const stats = data?.stats || {}
  const counts = useAppSelector((s) => {
    const d = s.live.data
    return { us: d?.hot_by_market?.us?.length || 0, india: d?.hot_by_market?.india?.length || 0, uk: d?.hot_by_market?.uk?.length || 0 }
  })
  const [triggerDiscover, discoverState] = useLazyDiscoverQuery()
  const [startFullScan, fullScanState] = useStartFullScanMutation()

  const onAnalyze = () => {
    const sym = (ui.search || '').trim().toUpperCase()
    if (sym) dispatch(selectSymbol(sym))
  }
  const onCsv = () => {
    const pool = getHotPool(data || {}, ui.marketFilter)
    exportCsv(filterAndSort(pool, ui).slice(0, DISPLAY_LIMIT))
  }
  const pool = getHotPool(data || {}, ui.marketFilter)
  const highConv = pool.filter((r) => rankScore(r) >= 70).length
  const smartMoney = pool.filter(hasSmartMoney).length
  const quickAnalyze = (sym: string) => {
    dispatch(setSearch(sym))
    dispatch(selectSymbol(sym))
  }

  return (
    <>
      <StatCards />
      <div className="cc-layout">
        <div className="cc-main">
          <div className="toolbar">
            <button className="btn-primary" onClick={onAnalyze} title="Analyze the ticker in the top search box">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round"><path d="M21 12a9 9 0 11-6.2-8.5" /><path d="M21 3v6h-6" /></svg>
              Analyze
            </button>
            {['NVDA', 'RELIANCE', 'BP.L'].map((sym) => (
              <button key={sym} className="btn-ghost small quick-chip" title={`Quick-analyze ${sym}`} onClick={() => quickAnalyze(sym)}>{sym}</button>
            ))}
            <button className="btn-secondary small" onClick={() => triggerDiscover()} disabled={discoverState.isFetching} title="Aggressive multi-website discovery scan">
              {discoverState.isFetching ? '🔍 Discovering…' : '🔍 Scan More'}
            </button>
            <button className="btn-secondary small accent-violet" onClick={() => startFullScan()} disabled={fullScanState.isLoading} title="Exhaustive full scan across all listed stocks">
              {fullScanState.isLoading ? '🔬 Starting…' : '🔬 Full Exhaustive Scan'}
            </button>
            <span className="toolbar__spacer" />
            <select value={ui.sortBy} onChange={(e) => dispatch(setSortBy(e.target.value as SortBy))} aria-label="Sort by" title="Sort the Hot Movers table">
              {SORTS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
            <button className="btn-ghost small" onClick={onCsv} title="Export current hot list as CSV">CSV</button>
          </div>

          <section className="panel table-panel">
            <div className="panel__head">
              <span className="panel__pulse" />
              <h2>Hot Movers</h2>
              <span className="panel__sub">ranked by buy score</span>
              <div className="tabs market-filters">
                {([['all', 'All', null], ['us', 'US', '#60A5FA'], ['india', 'India', '#FB923C'], ['uk', 'UK', '#A78BFA']] as const).map(([v, l, dot]) => (
                  <button
                    key={v}
                    className={'tab2' + (ui.marketFilter === v ? ' active' : '')}
                    title={v === 'all' ? 'Show stocks from all markets' : `Show only ${l} stocks`}
                    onClick={() => dispatch(setMarketFilter(v as MarketFilter))}
                  >
                    {dot && <span className="tab__dot" style={{ background: dot }} />}{l}
                    {counts[v] ? <span className="tab__count">{counts[v]}</span> : null}
                  </button>
                ))}
              </div>
              <div className="panel__filters">
                <button className="chip filter-chip" data-early={ui.earlyOnly ? '1' : '0'} title="Hide extended names — show only early/base entries" aria-pressed={ui.earlyOnly} onClick={() => dispatch(toggleEarly())}>Early buys only</button>
                <button className="chip filter-chip" data-whale={ui.whaleOnly ? '1' : '0'} title="Show only stocks with a named whale / politician / smart-money buy" aria-pressed={ui.whaleOnly} onClick={() => dispatch(toggleWhale())}>Whale / Politician</button>
              </div>
            </div>
            <p className="panel-hint">Live ranking — click any score or row for the full 100+ factor checklist. Scan More runs aggressive multi-site discovery.</p>
            <HotTable />
          </section>
        </div>

        <aside className="intel">
          <IntelFeed />
          <DetailPanel />
        </aside>
      </div>
    </>
  )
}
