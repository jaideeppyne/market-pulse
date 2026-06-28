import { researchOf } from '../../lib/format'
import type { Row } from '../../types'

const GRADE_CLASS: Record<string, string> = {
  'A+': 'grade--aplus', 'A': 'grade--a', 'B': 'grade--b', 'C': 'grade--c', 'D': 'grade--d',
}

export default function GradeBadge({ row, showTag = false }: { row: Row; showTag?: boolean }) {
  const r = researchOf(row)
  if (!r || !r.grade) return null
  const cls = GRADE_CLASS[r.grade] || 'grade--c'
  const tag = (r.tags || [])[0]
  const title = r.summary || `Quality grade ${r.grade}`
  return (
    <span className="grade-wrap" title={title}>
      <span className={'grade-badge ' + cls}>{r.grade}</span>
      {r.fundamentally_strong && <span className="grade-star" title="Fundamentally strong on NSE/BSE">★</span>}
      {showTag && tag && <span className="grade-tag">{tag}</span>}
    </span>
  )
}
