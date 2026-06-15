import { hasSmartMoney } from '../../lib/format'
import type { Row } from '../../types'

// Catalyst / reason badges (S+, Smart Money, News, Earnings, Extended, DISC, FULL).
// Reused wherever a row's catalysts are summarised.
export default function CatalystBadges({ row, score }: { row: Row; score: number }) {
  const out: JSX.Element[] = []
  const sm = row.metrics?.smart_money
  if (sm?.hits?.length || hasSmartMoney(row)) {
    const sTier = (sm?.hits?.[0]?.tier || '').toUpperCase()
    if (sTier.includes('S') || score >= 90) out.push(<span key="sp" className="cat-badge sp">S+</span>)
    else out.push(<span key="sm" className="cat-badge sm">Smart Money</span>)
  }
  if ((row.news && row.news.length) || row.metrics?.news_count || (row.alerts || []).some((a) => /news|headline/i.test(a)))
    out.push(<span key="news" className="cat-badge news">News</span>)
  if (row.earnings || row.metrics?.earnings_pre || row.earnings_soon || row.metrics?.days_until_earnings != null)
    out.push(<span key="earn" className="cat-badge earn">Earnings</span>)
  if (row.metrics?.is_extended) out.push(<span key="ext" className="cat-badge risk">Extended</span>)
  if (row.discovered) out.push(<span key="disc" className="cat-badge sm">DISC</span>)
  if (row.full_exhaustive) out.push(<span key="full" className="cat-badge news">FULL</span>)
  return <>{out}</>
}
