import { useSelector, useDispatch } from 'react-redux'
import StatCards from '../components/StatCards'
import HotTable from '../components/HotTable'
import IntelFeed from '../components/IntelFeed'
import DetailPanel from '../components/DetailPanel'
import { useLazyDiscoverQuery, useStartFullScanMutation } from '../store/api'
import {
  setMarketFilter, toggleEarly, toggleWhale, setSortBy, selectSymbol, setSearch,
} from '../store/uiSlice'
import { getHotPool, filterAndSort, DISPLAY_LIMIT, rankScore, hasSmartMoney } from '../lib/format'

const SORTS = [
  ['score', 'Buy score'], ['quality', 'Quality score'], ['factors', 'Factors hit'],
  ['day', 'Day %'], ['rvol', 'Volume'],
]

function exportCsv(rows) {
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
  const dispatch = useDispatch()
  const ui = useSelector((s) => s.ui)
  const data = useSelector((s) => s.live.data)
  const stats = data?.stats || {}
  const counts = useSelector((s) => {
    const d = s.live.data
    return { us: d?.hot_by_market?.us?.length || 0, india: d?.hot_by_market?.india?.length || 0 }
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
  const quickAnalyze = (sym) => {
    dispatch(setSearch(sym))
    dispatch(selectSymbol(sym))
  }

  return (
    <>
      <section className="command-brief">
        <div className="brief-copy">
          <div className="brief-kicker">GPT-style market workspace</div>
          <h1>Scan the tape, then drill into the exact reason.</h1>
          <p>Live US + India opportunities, S+ smart-money activity, earnings pressure, news bursts, and full factor explainability in one first screen.</p>
          <div className="brief-actions">
            <button className="btn-primary" onClick={onAnalyze} title="Analyze the symbol in the search box">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round"><path d="M21 12a9 9 0 11-6.2-8.5" /><path d="M21 3v6h-6" /></svg>
              Analyze typed ticker
            </button>
            {['MU', 'NVDA', 'RELIANCE', 'SBIN.NS'].map((sym) => (
              <button key={sym} className="btn-ghost small quick-chip" onClick={() => quickAnalyze(sym)}>{sym}</button>
            ))}
          </div>
        </div>
        <div className="brief-metrics">
          <div><span>Hot pool</span><strong>{pool.length}</strong></div>
          <div><span>70+ conviction</span><strong>{highConv}</strong></div>
          <div><span>S+ names</span><strong>{smartMoney}</strong></div>
          <div><span>News hits</span><strong>{data?.news?.length || 0}</strong></div>
          <div><span>Events</span><strong>{data?.events?.length || stats.market_events_count || 0}</strong></div>
          <div><span>Last scan</span><strong>{(stats.last_price_scan || stats.last_price_tick || '—').slice(11, 19) || '—'}</strong></div>
        </div>
      </section>
      <StatCards />
      <div className="cc-layout">
        <div className="cc-main">
          <div className="toolbar">
            <button className="btn-secondary small" onClick={() => triggerDiscover()} disabled={discoverState.isFetching} title="Aggressive multi-website discovery scan">
              {discoverState.isFetching ? '🔍 Discovering…' : '🔍 Scan More'}
            </button>
            <button className="btn-secondary small accent-violet" onClick={() => startFullScan()} disabled={fullScanState.isLoading} title="Exhaustive full scan across all listed stocks">
              {fullScanState.isLoading ? '🔬 Starting…' : '🔬 Full Exhaustive Scan'}
            </button>
            <span className="toolbar__spacer" />
            <select value={ui.sortBy} onChange={(e) => dispatch(setSortBy(e.target.value))} aria-label="Sort by">
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
                {[['all', 'All', null], ['us', 'US', '#60A5FA'], ['india', 'India', '#FB923C']].map(([v, l, dot]) => (
                  <button key={v} className={'tab2' + (ui.marketFilter === v ? ' active' : '')} onClick={() => dispatch(setMarketFilter(v))}>
                    {dot && <span className="tab__dot" style={{ background: dot }} />}{l}
                    {v === 'us' && counts.us ? <span className="tab__count">{counts.us}</span> : null}
                    {v === 'india' && counts.india ? <span className="tab__count">{counts.india}</span> : null}
                  </button>
                ))}
              </div>
              <div className="panel__filters">
                <button className="chip filter-chip" data-early={ui.earlyOnly ? '1' : '0'} onClick={() => dispatch(toggleEarly())}>Early buys only</button>
                <button className="chip filter-chip" data-whale={ui.whaleOnly ? '1' : '0'} onClick={() => dispatch(toggleWhale())}>Whale / Politician</button>
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
