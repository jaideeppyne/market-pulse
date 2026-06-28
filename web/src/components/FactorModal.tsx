import { useAnalyzeQuery } from '../store/api'
import { closeFactors, setFactorFilter } from '../store/uiSlice'
import { factorsDisplay } from '../lib/format'
import { useAppDispatch, useAppSelector } from '../store/hooks'
import type { FactorBreakdownItem, FactorFilter, Row } from '../types'

const CAT_ORDER = ['momentum', 'technicals', 'fundamentals', 'catalyst', 'smart_money', 'risk', 'other']

export default function FactorModal() {
  const dispatch = useAppDispatch()
  const sym = useAppSelector((s) => s.ui.factorSymbol)
  const filter = useAppSelector((s) => s.ui.factorFilter)
  const liveRow = useAppSelector((s) => {
    if (!sym || !s.live.data) return null
    const pools = [...(s.live.data.hot || []), ...((s.live.data.hot_by_market?.us) || []), ...((s.live.data.hot_by_market?.india) || []), ...((s.live.data.hot_by_market?.uk) || [])]
    return pools.find((r) => r.symbol === sym) || null
  })
  const needFetch = !!sym && (!liveRow || !liveRow.factor_breakdown)
  const { data: fetched, isFetching } = useAnalyzeQuery(sym || '', { skip: !needFetch })
  if (!sym) return null

  const row: Row | null = (fetched && fetched.symbol) ? fetched : liveRow
  const breakdown = row?.factor_breakdown || row?.metrics?.factor_breakdown || []
  const passed = breakdown.filter((x) => x.status === 'pass')
  const failed = breakdown.filter((x) => x.status === 'fail')
  const risk = breakdown.filter((x) => x.status === 'risk')
  const { hit, total } = factorsDisplay(row || { symbol: sym })

  let list = breakdown
  if (filter === 'pass') list = passed
  else if (filter === 'fail') list = failed
  else if (filter === 'risk') list = risk

  const byCat: Record<string, FactorBreakdownItem[]> = {}
  for (const f of list) (byCat[f.category || 'other'] ||= []).push(f)
  const cats = Object.keys(byCat).sort((a, b) => {
    const ia = CAT_ORDER.indexOf(a); const ib = CAT_ORDER.indexOf(b)
    return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib)
  })

  return (
    <div className="modal" aria-hidden="false">
      <div className="modal-backdrop" onClick={() => dispatch(closeFactors())} />
      <div className="modal-panel factors" role="dialog" aria-label="Factor breakdown">
        <header className="modal-header">
          <div>
            <h2>Factor breakdown <span style={{ color: '#C15F3C', fontFamily: 'var(--mono)', fontSize: 13 }}>{sym}</span></h2>
            <p className="modal-sub">
              <span style={{ color: '#15803D' }}>{passed.length} passed</span> · <span style={{ color: '#B45309' }}>{risk.length} risk</span> · <span style={{ color: '#DC2626' }}>{failed.length} failed</span> · {hit}/{total} applicable
            </p>
          </div>
          <button type="button" className="modal-close" title="Close factor breakdown" onClick={() => dispatch(closeFactors())} aria-label="Close">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round"><path d="M6 6l12 12M18 6L6 18" /></svg>
          </button>
        </header>
        <div className="modal-toolbar">
          {['all', 'pass', 'fail', 'risk'].map((f) => (
            <button
              key={f}
              type="button"
              className={'filter-pill' + (filter === f ? ' active' : '')}
              title={f === 'all' ? 'Show every factor' : f === 'pass' ? 'Show only passing factors' : f === 'fail' ? 'Show only failing factors' : 'Show only risk flags'}
              aria-pressed={filter === f}
              onClick={() => dispatch(setFactorFilter(f as FactorFilter))}
            >
              {f === 'all' ? 'All' : f === 'pass' ? 'Passed' : f === 'fail' ? 'Failed' : 'Risk flags'}
            </button>
          ))}
        </div>
        <div className="modal-body">
          {isFetching && !breakdown.length && <p className="muted">Loading weighted checklist…</p>}
          {!isFetching && !breakdown.length && <p className="muted">No factor data available for {sym}.</p>}
          {cats.map((cat) => (
            <div key={cat}>
              <div className="factor-cat">
                <span style={{ textTransform: 'capitalize' }}>{cat.replace('_', ' ')}</span>
                <span className="fgroup__summary muted" style={{ marginLeft: 'auto', fontFamily: 'var(--mono)', fontSize: 11.5 }}>
                  {byCat[cat].filter((f) => f.status === 'pass').length}/{byCat[cat].length} pass
                </span>
              </div>
              <ul className="factor-checklist">
                {byCat[cat].map((f, i) => (
                  <li key={i} className={'factor-item ' + (f.status || 'fail')}>
                    <span className="factor-status" />
                    <div className="factor-info">
                      <strong>{f.name || f.id || 'Factor'}</strong>
                      {f.tier && <span className={'tier-badge tier-' + f.tier}>{f.tier}</span>}
                      <span className="factor-desc">{f.description || ''}</span>
                      {f.label && <span className="factor-hit-label">{f.label}</span>}
                    </div>
                    {f.status === 'pass' && Number(f.weighted_points) > 0 && <span className="factor-pts">+{f.weighted_points}</span>}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
