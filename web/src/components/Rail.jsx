import { NavLink } from 'react-router-dom'

const ICONS = {
  cc: 'M4 4h7v7H4zM13 4h7v7h-7zM4 13h7v7H4zM13 13h7v7h-7z',
  star: 'M12 3l2.6 5.3 5.8.8-4.2 4.1 1 5.8L12 16.3 6.9 19l1-5.8L3.7 9.1l5.8-.8z',
  folder: 'M3 8h18v12H3zM8 8V6a2 2 0 012-2h4a2 2 0 012 2v2M3 13h18',
  radar: null,
  pie: 'M12 3v9l8 4M12 3a9 9 0 109 9',
  cal: 'M3 4h18v17H3zM3 9h18M8 2v4M16 2v4',
  news: 'M4 5h16v14H4zM8 9h8M8 13h5',
  chart: 'M4 19V5m0 14h16M8 16l3-4 3 2 4-6',
}

const NAV = [
  { to: '/', icon: 'cc', label: 'Command Center', end: true },
  { to: '/watchlist', icon: 'star', label: 'Watchlist' },
  { to: '/portfolio', icon: 'folder', label: 'Portfolio' },
  { to: '/radar', icon: 'radar', label: 'S+ Radar' },
  { to: '/sectors', icon: 'pie', label: 'Sector Map' },
  { to: '/earnings', icon: 'cal', label: 'Earnings' },
  { to: '/news', icon: 'news', label: 'Live News' },
  { to: '/edge', icon: 'chart', label: 'Edge & Guide' },
]

function Icon({ name }) {
  if (name === 'radar') {
    return (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
        <circle cx="12" cy="12" r="9" /><circle cx="12" cy="12" r="4.5" /><circle cx="12" cy="12" r="1" />
      </svg>
    )
  }
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d={ICONS[name]} /></svg>
  )
}

export default function Rail() {
  return (
    <nav className="rail" aria-label="Primary">
      <NavLink to="/" end className="rail__logo" title="Pulse Terminal">
        <svg viewBox="0 0 24 24" fill="none" stroke="#06121f" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" width="20" height="20"><path d="M3 12h4l2.5 7 5-14L17 12h4" /></svg>
      </NavLink>
      <div className="rail__nav">
        {NAV.map((n) => (
          <NavLink key={n.to} to={n.to} end={n.end} className="rail__btn" title={n.label} aria-label={n.label}>
            <span className="rail__bar" />
            <Icon name={n.icon} />
          </NavLink>
        ))}
      </div>
      <div className="rail__avatar" title="Market Pulse">MP</div>
    </nav>
  )
}
