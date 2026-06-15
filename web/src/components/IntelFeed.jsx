import { useSelector, useDispatch } from 'react-redux'
import { selectSymbol } from '../store/uiSlice'
import { timeAgo } from '../lib/format'

const STYLE = {
  high_score: { accent: '#34D77F', iconbg: 'rgba(34,197,94,.14)', icon: '📈' },
  smart_money: { accent: '#FACC15', iconbg: 'rgba(250,204,21,.14)', icon: '💎' },
  pre_earnings: { accent: '#B49BF5', iconbg: 'rgba(139,92,246,.14)', icon: '📅' },
  risk: { accent: '#F08585', iconbg: 'rgba(239,68,68,.14)', icon: '⚠' },
  news: { accent: '#7DB4F7', iconbg: 'rgba(96,165,250,.14)', icon: '📰' },
}
const DEFAULT = { accent: '#38BDF8', iconbg: 'rgba(56,189,248,.14)', icon: '⚡' }

export default function IntelFeed() {
  const dispatch = useDispatch()
  const alerts = useSelector((s) => s.live.alerts)

  return (
    <div>
      <div className="intel__head">
        <h3>Intelligence Feed</h3>
        <span className="intel__viewall">{alerts.length} signals</span>
      </div>
      <div className="intel__feed">
        {alerts.slice(0, 14).map((a, i) => {
          const st = STYLE[a.type] || DEFAULT
          return (
            <div
              key={i}
              className="feed-alert"
              style={{ '--accent': st.accent, '--iconbg': st.iconbg }}
              onClick={() => a.symbol && dispatch(selectSymbol(a.symbol))}
            >
              <span className="fa-icon">{st.icon}</span>
              <span className="fa-main">
                <span className="fa-title">
                  {(a.msg || a.type || 'Signal').split(' — ')[0].slice(0, 40)}
                  {a.symbol && <span className="fa-sym">{a.symbol}</span>}
                </span>
                <span className="fa-text">{a.msg || ''}</span>
              </span>
              <span className="fa-time">{timeAgo(a.ts)}</span>
            </div>
          )
        })}
      </div>
    </div>
  )
}
