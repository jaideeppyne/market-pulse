// Small square market badge (US / IN / UK) — reused in tables, detail, etc.
const META = {
  india: ['in', 'IN'],
  uk: ['uk', 'UK'],
  us: ['us', 'US'],
}

export default function MarketBadge({ market }) {
  const [cls, label] = META[market] || META.us
  return <span className={'mkt ' + cls}>{label}</span>
}
