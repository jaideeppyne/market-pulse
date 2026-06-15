export default function Sparkline({ values = [], w = 128, h = 42 }) {
  const nums = values.map(Number).filter(Number.isFinite)
  if (nums.length < 2) return null
  const min = Math.min(...nums)
  const max = Math.max(...nums)
  const span = max - min || 1
  const step = w / Math.max(1, nums.length - 1)
  const points = nums.map((v, i) => {
    const x = i * step
    const y = h - ((v - min) / span) * (h - 6) - 3
    return `${x.toFixed(2)},${y.toFixed(2)}`
  }).join(' ')
  const up = nums[nums.length - 1] >= nums[0]
  return (
    <svg className={'spark ' + (up ? 'up' : 'down')} viewBox={`0 0 ${w} ${h}`} width={w} height={h} preserveAspectRatio="none" aria-hidden="true">
      <polyline points={points} fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}
