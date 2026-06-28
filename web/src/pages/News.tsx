import { timeAgo } from '../lib/format'
import { useAppSelector } from '../store/hooks'
import { useNewsQuery } from '../store/api'

type RawNews = {
  title?: string; headline?: string; url?: string; link?: string
  source?: string; ts?: string; published_at?: string
  symbol?: string; symbols?: string[]
}

export default function News() {
  const wsNews = (useAppSelector((s) => s.live.data?.news) as RawNews[] | undefined) || []
  const { data } = useNewsQuery(undefined, { pollingInterval: 30000 })

  // Merge WS snapshot + API live + stored (DB) headlines, newest-first, deduped.
  const all: RawNews[] = [...wsNews, ...(data?.live || []), ...(data?.stored || [])]
  const seen = new Set<string>()
  const news = all
    .filter((n) => {
      const k = n.link || n.url || n.title || ''
      if (!k || seen.has(k)) return false
      seen.add(k); return true
    })
    .sort((a, b) => String(b.published_at || b.ts || '').localeCompare(String(a.published_at || a.ts || '')))
    .slice(0, 100)

  return (
    <section className="panel pad">
      <h2 className="view-h">Live News</h2>
      <p className="panel-hint">Headlines from Google News + Yahoo, matched to tracked symbols. Updates every ~90s.</p>
      <ul className="news-list">
        {news.length === 0 && <li className="muted">No headlines yet — the news crawler runs every ~90s.</li>}
        {news.map((n, i) => {
          const url = n.link || n.url
          const sym = n.symbol || (Array.isArray(n.symbols) ? n.symbols[0] : '')
          const ts = n.published_at || n.ts
          return (
            <li key={i}>
              {sym && <span className="cat-badge news" style={{ marginRight: 8 }}>{sym}</span>}
              {url
                ? <a href={url} target="_blank" rel="noreferrer" title="Open the full article in a new tab">{n.title || n.headline}</a>
                : (n.title || n.headline)}
              <span className="muted" style={{ marginLeft: 8, fontSize: 11 }}>{n.source || ''}{ts ? ` · ${timeAgo(ts)}` : ''}</span>
            </li>
          )
        })}
      </ul>
    </section>
  )
}
