import { useSelector, useDispatch } from 'react-redux'
import { useNavigate } from 'react-router-dom'
import { getHotPool, rankScore, hasSmartMoney } from '../lib/format'
import { toggleWhale, resetFilters } from '../store/uiSlice'

const CARDS = [
  { key: 'hot', label: 'Hot Movers', accent: '#38BDF8', iconBg: 'rgba(56,189,248,.12)', icon: 'M3 17l6-6 4 4 8-8M21 7v6', subColor: '#34D77F' },
  { key: 'sm', label: 'S+ / Smart Money', accent: '#FACC15', iconBg: 'rgba(250,204,21,.12)', icon: 'M3 7l4 12h10l4-12-5 4-4-7-4 7z', subColor: '#E5C158' },
  { key: 'news', label: 'News Activity', accent: '#60A5FA', iconBg: 'rgba(96,165,250,.12)', icon: 'M4 5h16v14H4zM8 9h8M8 13h5', subColor: '#7DB4F7' },
  { key: 'earn', label: 'Earnings', accent: '#8B5CF6', iconBg: 'rgba(139,92,246,.12)', icon: 'M3 4h18v17H3zM3 9h18M8 2v4M16 2v4', subColor: '#B49BF5' },
  { key: 'health', label: 'Scan Health', accent: '#22C55E', iconBg: 'rgba(34,197,94,.12)', icon: 'M3 12h4l2.5 7 5-14L17 12h4', subColor: '#E8B873' },
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
  const got = Number(stats.last_full_price_scan_result_count ?? stats.last_price_batch_result_count ?? 0)
  const tried = Number(stats.last_full_price_scan_attempted ?? stats.last_price_batch_attempted ?? 0)
  const health = tried > 0 ? `${Math.round((got / tried) * 1000) / 10}%` : (stats.symbols_tracked ? `${stats.symbols_tracked}` : '—')

  const values = {
    hot: [pool.length, `${highConv} high-conviction`],
    sm: [smCount, 'named investor signals'],
    news: [newsBurst, 'headlines tracked'],
    earn: [earningsCnt, 'reporting soon'],
    health: [health, stats.scan_in_progress ? `scanning ${stats.scan_batch || '?'}/${stats.scan_batches_total || '?'}` : 'live coverage'],
  }

  const onClick = (key) => {
    if (key === 'sm') dispatch(toggleWhale())
    else if (key === 'news') navigate('/news')
    else if (key === 'earn') navigate('/earnings')
    else if (key === 'health') navigate('/edge')
    else dispatch(resetFilters())
  }

  return (
    <section className="stats">
      {CARDS.map((c) => {
        const [value, sub] = values[c.key]
        return (
          <div key={c.key} className="stat-card clickable" onClick={() => onClick(c.key)} title="Click to filter / open">
            <span className="accent" style={{ background: c.accent }} />
            <div className="stat-head">
              <span className="label">{c.label}</span>
              <span className="stat-icon" style={{ background: c.iconBg, color: c.accent }}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round"><path d={c.icon} /></svg>
              </span>
            </div>
            <div className="value">{value}</div>
            <div className="sub" style={{ color: c.subColor }}>{sub}</div>
          </div>
        )
      })}
    </section>
  )
}
