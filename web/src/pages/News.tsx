import { useSelector } from 'react-redux'
import { timeAgo } from '../lib/format'

export default function News() {
  const news = useSelector((s) => s.live.data?.news) || []
  return (
    <section className="panel pad">
      <h2 className="view-h">Live News</h2>
      <p className="panel-hint">Headlines matched to tracked symbols across multiple sources.</p>
      <ul className="news-list">
        {news.length === 0 && <li className="muted">No headlines yet.</li>}
        {news.map((n, i) => (
          <li key={i}>
            {n.symbol && <span className="cat-badge news" style={{ marginRight: 8 }}>{n.symbol}</span>}
            {n.url ? <a href={n.url} target="_blank" rel="noreferrer">{n.title}</a> : (n.title || n.headline)}
            <span className="muted" style={{ marginLeft: 8, fontSize: 11 }}>{n.source || ''} {n.ts ? `· ${timeAgo(n.ts)}` : ''}</span>
          </li>
        ))}
      </ul>
    </section>
  )
}
