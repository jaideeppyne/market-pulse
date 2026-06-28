import { useState } from 'react'
import type { KeyboardEvent } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { setSearch, selectSymbol } from '../store/uiSlice'
import { useAppDispatch, useAppSelector } from '../store/hooks'
import { getHotPool, rankScore, marketOf } from '../lib/format'

const TITLES = {
  '/': 'Command Center', '/watchlist': 'Watchlist', '/portfolio': 'Portfolio',
  '/radar': 'S+ Radar', '/sectors': 'Sector Map', '/earnings': 'Earnings',
  '/news': 'Live News', '/edge': 'Edge & Guide',
}

export default function Topbar() {
  const dispatch = useAppDispatch()
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const [menuOpen, setMenuOpen] = useState(false)
  const search = useAppSelector((s) => s.ui.search)
  const data = useAppSelector((s) => s.live.data)
  const status = useAppSelector((s) => s.live.status)
  const stats = useAppSelector((s) => s.live.data?.stats) || {}
  const alertN = useAppSelector((s) => s.live.alerts.length)
  const q = (search || '').trim().toUpperCase()
  const pool = getHotPool(data || {}, 'all')
  const matches = q
    ? pool
      .filter((r) => {
        const m = r.metrics || {}
        return `${r.symbol || ''} ${m.name || ''} ${m.sector || ''}`.toUpperCase().includes(q)
      })
      .sort((a, b) => rankScore(b) - rankScore(a))
      .slice(0, 6)
    : []

  const scanVal = stats.scan_in_progress
    ? 'live'
    : (stats.last_price_scan || stats.last_price_tick || '').slice(11, 19) || '—'

  const submitSearch = (raw = q) => {
    const sym = String(raw || '').trim().toUpperCase()
    if (!sym) return
    dispatch(setSearch(sym))
    dispatch(selectSymbol(sym))
    setMenuOpen(false)
    navigate('/')
  }

  const onKey = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      submitSearch()
    } else if (e.key === 'Escape') {
      setMenuOpen(false)
    }
  }

  return (
    <header className="topbar">
      <div className="topbar__title">
        <div className="topbar__eyebrow">Pulse Terminal</div>
        <div className="topbar__heading">{TITLES[pathname] || 'Command Center'}</div>
      </div>

      <div className="search">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><circle cx="11" cy="11" r="7" /><path d="M21 21l-4.3-4.3" /></svg>
        <input
          type="search"
          value={search}
          aria-label="Search or analyze ticker"
          placeholder="Analyze any ticker — NVDA, RELIANCE, SBIN.NS, BP.L…"
          onChange={(e) => { dispatch(setSearch(e.target.value)); setMenuOpen(true) }}
          onFocus={() => q && setMenuOpen(true)}
          onKeyDown={onKey}
          autoComplete="off"
        />
        {q && (
          <button
            type="button"
            className="search__go"
            onMouseDown={(e) => { e.preventDefault(); submitSearch(q) }}
            title={`Analyze ${q}`}
          >
            Analyze
          </button>
        )}
        {!q && <kbd>↵</kbd>}
        {q && menuOpen && (
          <div className="search-menu">
            <button type="button" className="search-menu__item primary" onMouseDown={(e) => { e.preventDefault(); submitSearch(q) }}>
              <span className="search-menu__ticker">{q}</span>
              <span className="search-menu__meta">Run full 100+ factor analysis</span>
            </button>
            {matches.map((r) => {
              const m = r.metrics || {}
              return (
                <button key={r.symbol} type="button" className="search-menu__item" onMouseDown={(e) => { e.preventDefault(); submitSearch(r.symbol) }}>
                  <span className="search-menu__ticker">{r.symbol}</span>
                  <span className="search-menu__meta">{m.name || m.sector || marketOf(r).toUpperCase()}</span>
                  <span className="search-menu__score">{Math.round(rankScore(r))}</span>
                </button>
              )
            })}
          </div>
        )}
      </div>

      <div className="pills">
        <span className="pill"><span className="pill__dot" style={{ background: '#34D77F' }} /><span className="pill__label">US</span><span className="pill__value" style={{ color: '#34D77F' }}>LIVE</span></span>
        <span className="pill"><span className="pill__dot" style={{ background: '#FB923C' }} /><span className="pill__label">IN</span><span className="pill__value" style={{ color: '#FB923C' }}>LIVE</span></span>
        <span className="pill"><span className="pill__dot" style={{ background: '#A78BFA' }} /><span className="pill__label">UK</span><span className="pill__value" style={{ color: '#A78BFA' }}>LIVE</span></span>
        <span className="pill"><span className="pill__dot" style={{ background: '#38BDF8' }} /><span className="pill__label">SCAN</span><span className="pill__value" style={{ color: '#56C6F5' }}>{scanVal}</span></span>
        <span className={'pill status-pill ' + (status === 'live' ? 'live' : status === 'down' ? 'down' : '')}>
          {status === 'live' ? '● Live' : status === 'down' ? 'Reconnecting…' : 'Connecting…'}
        </span>
        <button type="button" className="bell-btn" title="Alerts">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M18 8a6 6 0 10-12 0c0 7-3 9-3 9h18s-3-2-3-9M13.7 21a2 2 0 01-3.4 0" /></svg>
          <span className="bell-count">{alertN > 9 ? '9+' : alertN}</span>
        </button>
      </div>
    </header>
  )
}
