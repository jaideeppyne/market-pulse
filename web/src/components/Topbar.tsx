import { useMemo, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { setSearch, selectSymbol } from '../store/uiSlice'
import { useAppDispatch, useAppSelector } from '../store/hooks'
import { getHotPool, rankScore, displayName, timeAgo } from '../lib/format'
import type { KeyboardEvent } from 'react'

const TITLES: Record<string, string> = {
  '/': 'Command Center', '/watchlist': 'Watchlist', '/portfolio': 'Portfolio',
  '/radar': 'S+ Radar', '/sectors': 'Sector Map', '/earnings': 'Earnings',
  '/news': 'Live News', '/edge': 'Edge & Guide',
}

export default function Topbar() {
  const dispatch = useAppDispatch()
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const search = useAppSelector((s) => s.ui.search)
  const status = useAppSelector((s) => s.live.status)
  const stats = useAppSelector((s) => s.live.data?.stats) || {}
  const alertN = useAppSelector((s) => s.live.alerts.length)
  const alerts = useAppSelector((s) => s.live.alerts)
  const liveData = useAppSelector((s) => s.live.data)
  const [open, setOpen] = useState(false)
  const [bellOpen, setBellOpen] = useState(false)

  const scanVal = stats.scan_in_progress
    ? 'live'
    : (stats.last_price_scan || stats.last_price_tick || '').slice(11, 19) || '—'

  // Live autocomplete over the current scanner pool (symbol + company name).
  const matches = useMemo(() => {
    const q = (search || '').trim().toUpperCase()
    if (q.length < 1) return []
    const pool = getHotPool(liveData || {}, 'all')
    const seen = new Set<string>()
    const out: typeof pool = []
    for (const r of pool) {
      const sym = String(r.symbol || '').toUpperCase()
      const nm = String((r.metrics?.name as string) || (r as { name?: string }).name || '').toUpperCase()
      if (!sym || seen.has(sym)) continue
      if (sym.includes(q) || (nm && nm.includes(q))) { out.push(r); seen.add(sym) }
    }
    out.sort((a, b) => rankScore(b) - rankScore(a))
    return out.slice(0, 8)
  }, [search, liveData])

  const go = (sym?: string) => {
    const s = String(sym || '').trim().toUpperCase()
    if (!s) return
    dispatch(selectSymbol(s)); setOpen(false); navigate('/')
  }

  const onKey = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') go(search)
    else if (e.key === 'Escape') setOpen(false)
  }

  return (
    <header className="topbar">
      <div className="topbar__title">
        <div className="topbar__eyebrow">Pulse Terminal</div>
        <div className="topbar__heading">{TITLES[pathname] || 'Command Center'}</div>
      </div>

      <label className="search">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><circle cx="11" cy="11" r="7" /><path d="M21 21l-4.3-4.3" /></svg>
        <input
          type="search"
          value={search}
          placeholder="Analyze any ticker — NVDA, RELIANCE, SBIN.NS, BP.L…"
          onChange={(e) => { dispatch(setSearch(e.target.value)); setOpen(true) }}
          onFocus={() => setOpen(true)}
          onBlur={() => setTimeout(() => setOpen(false), 160)}
          onKeyDown={onKey}
          autoComplete="off"
        />
        <kbd title="Press Enter to analyze the typed ticker">↵</kbd>
        {open && matches.length > 0 && (
          <div className="search-menu" role="listbox">
            {matches.map((r) => {
              const nm = displayName(r)
              return (
                <button
                  key={String(r.symbol)}
                  type="button"
                  className="search-menu__item"
                  title={`Analyze ${r.symbol}${nm ? ' — ' + nm : ''}`}
                  onMouseDown={(e) => { e.preventDefault(); go(String(r.symbol)) }}
                >
                  <span className="search-menu__ticker">{r.symbol}</span>
                  <span className="search-menu__meta">{nm}</span>
                  <span className="search-menu__score" title="Current buy score">{Math.round(rankScore(r))}</span>
                </button>
              )
            })}
          </div>
        )}
      </label>

      <div className="pills">
        <span className="pill" title="US market scanner status"><span className="pill__dot" style={{ background: '#15803D' }} /><span className="pill__label">US</span><span className="pill__value" style={{ color: '#15803D' }}>LIVE</span></span>
        <span className="pill" title="India market scanner status"><span className="pill__dot" style={{ background: '#C2410C' }} /><span className="pill__label">IN</span><span className="pill__value" style={{ color: '#C2410C' }}>LIVE</span></span>
        <span className="pill" title="UK market scanner status"><span className="pill__dot" style={{ background: '#7C3AED' }} /><span className="pill__label">UK</span><span className="pill__value" style={{ color: '#7C3AED' }}>LIVE</span></span>
        <span className="pill" title="Time of the last completed price scan (or “live” while a scan is running)"><span className="pill__dot" style={{ background: '#C15F3C' }} /><span className="pill__label">SCAN</span><span className="pill__value" style={{ color: '#A84A2C' }}>{scanVal}</span></span>
        <span
          className={'pill status-pill ' + (status === 'live' ? 'live' : status === 'down' ? 'down' : '')}
          title={status === 'live' ? 'Live WebSocket connected — data streams in real time' : status === 'down' ? 'WebSocket down — auto-refreshing via polling every 20s' : 'Connecting to the live feed…'}
        >
          {status === 'live' ? '● Live' : status === 'down' ? 'Reconnecting…' : 'Connecting…'}
        </span>
        <div className="bell-wrap" style={{ position: 'relative' }}>
          <button
            type="button"
            className="bell-btn"
            title={alertN ? `${alertN} live alert${alertN === 1 ? '' : 's'} — click to view` : 'Live alerts — none yet'}
            aria-haspopup="true"
            aria-expanded={bellOpen}
            onClick={() => setBellOpen((v) => !v)}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M18 8a6 6 0 10-12 0c0 7-3 9-3 9h18s-3-2-3-9M13.7 21a2 2 0 01-3.4 0" /></svg>
            <span className="bell-count">{alertN > 9 ? '9+' : alertN}</span>
          </button>
          {bellOpen && (
            <div className="bell-menu" role="menu">
              <div className="bell-menu__head">
                <strong>Live alerts</strong>
                <span className="muted">{alertN} signal{alertN === 1 ? '' : 's'}</span>
              </div>
              {alerts.length === 0 && <div className="bell-menu__empty muted">No alerts yet — they fire as new high-conviction setups appear.</div>}
              {alerts.slice(0, 12).map((a, i) => (
                <button
                  key={i}
                  type="button"
                  className="bell-menu__item"
                  title={a.msg || a.type}
                  onClick={() => { if (a.symbol) { dispatch(selectSymbol(a.symbol)); navigate('/') } setBellOpen(false) }}
                >
                  {a.symbol && <span className="bell-menu__sym">{a.symbol}</span>}
                  <span className="bell-menu__msg">{a.msg || a.type}</span>
                  <span className="bell-menu__time muted">{timeAgo(a.ts)}</span>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </header>
  )
}
