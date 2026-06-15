import { buyTier } from '../../lib/format'

// The glowing buy-score tier pill (S+/A/B/C/D) with optional quality sub-label.
// Reused in the Hot Movers table and the detail panel.
export default function BuyScorePill({
  score,
  quality,
  onClick,
}: {
  score: number
  quality?: number | string
  onClick?: (e: React.MouseEvent) => void
}) {
  const [tierCls, tierLbl] = buyTier(score)
  return (
    <div
      className={'buy ' + tierCls + (onClick ? ' clickable' : '')}
      onClick={onClick}
      title="Buy score — click for the weighted factor breakdown"
    >
      <span className="buy__meta">
        <span className="buy__tier">{tierLbl}</span>
        {quality != null && <div className="buy__q">Q {quality}</div>}
      </span>
      <span className="buy__pill"><span>{Math.round(score)}</span></span>
    </div>
  )
}
