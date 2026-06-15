import { useSelector, useDispatch } from 'react-redux'
import { useLocation, useNavigate } from 'react-router-dom'
import { setSearch, selectSymbol } from '../store/uiSlice'

const TITLES = {
  '/': 'Command Center', '/watchlist': 'Watchlist', '/portfolio': 'Portfolio',
  '/radar': 'S+ Radar', '/sectors': 'Sector Map', '/earnings': 'Earnings',
  '/news': 'Live News', '/edge': 'Edge & Guide',
}

export default function Topbar() {
  const dispatch = useDispatch()
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const search = useSelector((s) => s.ui.search)
  const status = useSelector((s) => s.live.status)
  const stats = useSelector((s) => s.live.data?.stats) || {}
  const alertN = useSelector((s) => s.live.alerts.length)

  const scanVal = stats.scan_in_progress
    ? 'live'
    : (stats.last_price_scan || stats.last_price_tick || '').slice(11, 19) || '—'

  const onKey = (e) => {
    if (e.key === 'Enter') {
      const sym = (search || '').trim().toUpperCase()
      if (sym) { dispatch(selectSymbol(sym)); navigate('/') }
    }
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
          onChange={(e) => dispatch(setSearch(e.target.value))}
          onKeyDown={onKey}
          autoComplete="off"
        />
        <kbd>↵</kbd>
      </label>

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
