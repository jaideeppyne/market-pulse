import { useSelector, useDispatch } from 'react-redux'
import { useNavigate } from 'react-router-dom'
import { getHotPool, rankScore, hasSmartMoney } from '../lib/format'
import { toggleWhale, resetFilters } from '../store/uiSlice'

const CARDS = [
  { key: 'hot', label: 'Hot', accent: '#2563EB', iconBg: 'rgba(37,99,235,.10)', icon: 'M3 17l6-6 4 4 8-8M21 7v6', subColor: '#15803D' },
  { key: 'high', label: 'High Conv', accent: '#16A34A', iconBg: 'rgba(22,163,74,.10)', icon: 'M5 13l4 4L19 7', subColor: '#15803D' },
  { key: 'sm', label: 'S+ Radar', accent: '#D97706', iconBg: 'rgba(217,119,6,.10)', icon: 'M3 7l4 12h10l4-12-5 4-4-7-4 7z', subColor: '#B45309' },
  { key: 'news', label: 'News', accent: '#0F766E', iconBg: 'rgba(15,118,110,.10)', icon: 'M4 5h16v14H4zM8 9h8M8 13h5', subColor: '#0F766E' },
  { key: 'earn', label: 'Earnings', accent: '#7C3AED', iconBg: 'rgba(124,58,237,.10)', icon: 'M3 4h18v17H3zM3 9h18M8 2v4M16 2v4', subColor: '#6D28D9' },
  { key: 'events', label: 'Events', accent: '#BE123C', iconBg: 'rgba(190,18,60,.10)', icon: 'M12 3v18M5 8h14M7 16h10', subColor: '#BE123C' },
  { key: 'tracked', label: 'Tracked', accent: '#475569', iconBg: 'rgba(71,85,105,.10)', icon: 'M4 7h16M4 12h16M4 17h16', subColor: '#475569' },
  { key: 'health', label: 'Coverage', accent: '#0891B2', iconBg: 'rgba(8,145,178,.10)', icon: 'M3 12h4l2.5 7 5-14L17 12h4', subColor: '#0E7490' },
]

export default function StatCards() {
  const dispatch = useDispatch()
  const navigate = useNavigate()
  const data = useSelector((s) => s.live.data)
  const marketFilter = useSelector((s) => s.ui.marketFilter)
  const stats = data?.stats || {}

  const pool = getHotPool(data || {}, marketFilter)
  const highConv = pool.filter((r) => rankScore(r) >= 70).length
  const smCount = pool.filter((r) => hasSmartMoney(r)).length
  const newsBurst = (data?.news || []).length
  const earningsCnt = (data?.earnings || []).length
  const eventCnt = (data?.events || []).length || Number(stats.market_events_count || 0)
  const tracked = Number(stats.symbols_tracked || 0)
  const got = Number(stats.last_full_price_scan_result_count ?? stats.last_price_batch_result_count ?? 0)
  const tried = Number(stats.last_full_price_scan_attempted ?? stats.last_price_batch_attempted ?? 0)
  const health = tried > 0 ? `${Math.round((got / tried) * 1000) / 10}%` : (stats.symbols_tracked ? `${stats.symbols_tracked}` : '—')

  const values = {
    hot: [pool.length, `${highConv} high-conviction`],
    high: [highConv, 'buy score 70+'],
    sm: [smCount, 'named investor signals'],
    news: [newsBurst, 'headlines tracked'],
    earn: [earningsCnt, 'reporting soon'],
    events: [eventCnt, 'filings + catalysts'],
    tracked: [tracked || '—', 'symbols processed'],
    health: [health, stats.scan_in_progress ? `scanning ${stats.scan_batch || '?'}/${stats.scan_batches_total || '?'}` : 'live coverage'],
  }

  const onClick = (key) => {
    if (key === 'sm') dispatch(toggleWhale())
    else if (key === 'high') dispatch(resetFilters())
    else if (key === 'news') navigate('/news')
    else if (key === 'earn') navigate('/earnings')
    else if (key === 'events') navigate('/radar')
    else if (key === 'health') navigate('/edge')
    else dispatch(resetFilters())
  }

  return (
    <section className="stats">
      {CARDS.map((c) => {
        const [value, sub] = values[c.key]
        return (
          <button key={c.key} type="button" className="stat-card clickable" onClick={() => onClick(c.key)} title="Click to filter / open">
            <span className="accent" style={{ background: c.accent }} />
            <div className="stat-head">
              <span className="label">{c.label}</span>
              <span className="stat-icon" style={{ background: c.iconBg, color: c.accent }}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round"><path d={c.icon} /></svg>
              </span>
            </div>
            <div className="value">{value}</div>
            <div className="sub" style={{ color: c.subColor }}>{sub}</div>
          </button>
        )
      })}
    </section>
  )
}
