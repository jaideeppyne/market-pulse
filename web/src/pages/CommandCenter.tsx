import { useEffect, useRef, useState } from 'react'
import StatCards from '../components/StatCards'
import TopPicks from '../components/TopPicks'
import ScanActivity from '../components/ScanActivity'
import HotTable from '../components/HotTable'
import IntelFeed from '../components/IntelFeed'
import DetailPanel from '../components/DetailPanel'
import { useLazyDiscoverQuery, useStartFullScanMutation, useLazyJobStatusQuery } from '../store/api'
import { useAppDispatch, useAppSelector } from '../store/hooks'
import {
  setMarketFilter, toggleEarly, toggleWhale, toggleQuality, setSortBy, selectSymbol, setSearch,
} from '../store/uiSlice'
import { getHotPool, filterAndSort, DISPLAY_LIMIT, rankScore, hasSmartMoney, isFundamentallyStrong } from '../lib/format'
import type { MarketFilter, Row, SortBy } from '../types'

const SORTS = [
  ['score', 'Buy score'], ['grade', 'Quality grade'], ['quality', 'Quality score'], ['factors', 'Factors hit'],
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
  const [pollJob] = useLazyJobStatusQuery()
  const [fullJob, setFullJob] = useState<{ id?: string; status: string; progress: number } | null>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const runFullScan = async () => {
    try {
      const res: any = await startFullScan().unwrap()
      const id = res?.job_id || res?.id
      if (!id) return
      setFullJob({ id, status: 'running', progress: 5 })
      if (pollRef.current) clearInterval(pollRef.current)
      pollRef.current = setInterval(async () => {
        try {
          const j: any = await pollJob(id).unwrap()
          const status = String(j?.status || 'running')
          const progress = Number(j?.progress || 0)
          setFullJob({ id, status, progress })
          if (status === 'done' || status === 'error') {
            if (pollRef.current) clearInterval(pollRef.current)
            setTimeout(() => setFullJob(null), 4000)
          }
        } catch { /* keep polling */ }
      }, 2500)
    } catch { /* ignore */ }
  }
  useEffect(() => () => { if (pollRef.current) clearInterval(pollRef.current) }, [])

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
  const strongCount = pool.filter(isFundamentallyStrong).length
  const quickAnalyze = (sym: string) => {
    dispatch(setSearch(sym))
    dispatch(selectSymbol(sym))
  }

  return (
    <>
      <TopPicks />
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
            <button className="btn-secondary small accent-violet" onClick={() => runFullScan()} disabled={fullScanState.isLoading || fullJob?.status === 'running'} title="Exhaustive full scan across all listed stocks">
              {fullJob?.status === 'running' ? `🔬 Scanning… ${fullJob.progress}%` : fullScanState.isLoading ? '🔬 Starting…' : '🔬 Full Exhaustive Scan'}
            </button>
            <span className="toolbar__spacer" />
            <select value={ui.sortBy} onChange={(e) => dispatch(setSortBy(e.target.value as SortBy))} aria-label="Sort by" title="Sort the Hot Movers table">
              {SORTS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
            <button className="btn-ghost small" onClick={onCsv} title="Export current hot list as CSV">CSV</button>
          </div>

          <ScanActivity discovering={discoverState.isFetching} fullJob={fullJob} />

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
                <button className="chip filter-chip" data-quality={ui.qualityOnly ? '1' : '0'} title="Show only fundamentally strong NSE/BSE names — good promoters, cash flow, valuations, FII backing, dividends" aria-pressed={ui.qualityOnly} onClick={() => dispatch(toggleQuality())}>★ Fundamentally strong{strongCount ? ` (${strongCount})` : ''}</button>
              </div>
            </div>
            <p className="panel-hint">Live ranking — click any score or row for the full 100+ factor checklist. Scan More runs aggressive multi-site discovery.</p>

            {/* Valuable insights on homepage so end users immediately see why to use the site.
                Constantly showing high-signal info: count of quality setups, key catalysts, focus on fundamentals for India. */}
            {(() => {
              const indiaPool = (data?.hot_by_market?.india || pool).filter((r: any) => (r.market || '').toLowerCase() === 'india');
              const highFund = indiaPool.filter((r: any) => (r.fundamental_reasons_count || (r.metrics && r.metrics.fundamental_reasons_count) || 0) >= 2).length;
              const catalysts = indiaPool.flatMap((r: any) => (r.why_good_reasons || (r.metrics && r.metrics.reasons) || []).map((rr: any) => (typeof rr === 'string' ? rr : rr.text || '')));
              const topCat = catalysts.length ? [...new Set(catalysts)].slice(0,3).join(', ') : '—';
              return highFund > 0 || catalysts.length > 0 ? (
                <div className="insights-bar" style={{margin: '8px 0', padding: '8px', background: '#f8fafc', borderRadius: '6px', fontSize: '0.9em'}}>
                  <strong>Insights:</strong> {highFund} India stocks with multiple fundamental strengths (promoter/FII/FCF/growth). 
                  Key catalysts spotted: {topCat}. Click rows for full thesis + reasons.
                </div>
              ) : null;
            })()}

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
