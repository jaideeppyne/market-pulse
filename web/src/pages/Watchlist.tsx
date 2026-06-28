import { useState } from 'react'
import { selectSymbol } from '../store/uiSlice'
import { useAppDispatch } from '../store/hooks'
import {
  useWatchlistQuery, useRemoveWatchMutation, useAlertRulesQuery,
  useAddAlertRuleMutation, useDeleteAlertRuleMutation,
} from '../store/api'

interface RuleForm {
  rule_type: string
  min_buy_score: number | string
  min_rvol: number | string
  has_investor: boolean
}

export default function Watchlist() {
  const dispatch = useAppDispatch()
  const { data: wl, isLoading } = useWatchlistQuery()
  const [removeWatch] = useRemoveWatchMutation()
  const { data: rulesData } = useAlertRulesQuery()
  const [addRule] = useAddAlertRuleMutation()
  const [delRule] = useDeleteAlertRuleMutation()
  const [showRules, setShowRules] = useState(false)
  const [form, setForm] = useState<RuleForm>({ rule_type: 'score', min_buy_score: 65, min_rvol: 2, has_investor: true })

  const watches = wl?.watches || []
  const rules = rulesData?.rules || []

  const submitRule = () => {
    const condition: Record<string, unknown> = {}
    if (form.min_buy_score) condition.min_buy_score = Number(form.min_buy_score)
    if (form.min_rvol) condition.min_rvol = Number(form.min_rvol)
    if (form.has_investor) condition.has_investor = true
    addRule({ rule_type: form.rule_type, condition, enabled: true })
  }

  return (
    <section className="panel pad">
      <h2 className="view-h">My List <span className="view-h__sub">server-persisted + personalized alert rules</span></h2>
      <p className="panel-hint">Server-backed (multi-device / restart safe). Add from Hot / Detail. Alert Rules trigger in-app + browser notifications.</p>
      <div className="toolbar">
        <button className="btn-secondary small" title="Show / hide personalized alert rules (server-persisted)" aria-expanded={showRules} onClick={() => setShowRules((v) => !v)}>🔔 Manage Alert Rules</button>
        <span className="muted">{watches.length} symbols</span>
      </div>
      <div className="table-wrap">
        <table className="data-table">
          <thead><tr><th>Symbol</th><th>Buy</th><th>Qual</th><th>Notes</th><th>Added</th><th>Actions</th></tr></thead>
          <tbody>
            {isLoading && <tr><td colSpan={6} className="muted">Loading…</td></tr>}
            {!isLoading && watches.length === 0 && <tr><td colSpan={6} className="muted">No symbols yet. Add from the Hot Movers table or detail view.</td></tr>}
            {watches.map((w) => (
              <tr key={w.symbol} title={`Open ${w.symbol}${w.name && w.name !== w.symbol ? ' (' + w.name + ')' : ''}`} onClick={() => dispatch(selectSymbol(w.symbol))}>
                <td className="symbol-cell">{w.symbol}{w.name && w.name !== w.symbol ? (<><br /><span className="sym__name">{w.name}</span></>) : null}</td>
                <td>{w.buy_score ?? w.last_score ?? '—'}</td>
                <td>{w.quality_score ?? '—'}</td>
                <td className="muted">{w.notes || ''}</td>
                <td className="muted">{w.added_at ? new Date(w.added_at).toLocaleDateString() : ''}</td>
                <td><button className="btn-danger tiny" title={`Remove ${w.symbol} from My List`} onClick={(e) => { e.stopPropagation(); removeWatch(w.symbol) }}>Remove</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {showRules && (
        <div className="rules-section">
          <h4>Active Alert Rules (server)</h4>
          <div className="rules-list">
            {rules.length === 0 && <span className="muted">No rules yet.</span>}
            {rules.map((r) => (
              <div key={r.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span><strong>#{r.id}</strong> {r.rule_type}: {Object.entries(r.condition || {}).map(([k, v]) => `${k}:${v}`).join(' & ') || 'default'} {r.enabled ? '✓' : '(off)'}</span>
                <button className="btn-danger tiny" title={`Delete alert rule #${r.id}`} onClick={() => delRule(r.id)}>del</button>
              </div>
            ))}
          </div>
          <div className="toolbar rules-form">
            <select value={form.rule_type} title="Type of alert rule to create" onChange={(e) => setForm({ ...form, rule_type: e.target.value })}>
              <option value="score">score (buy_score + rvol)</option>
              <option value="smart_money">smart_money</option>
              <option value="earnings">earnings</option>
              <option value="custom">custom</option>
            </select>
            <input type="number" value={form.min_buy_score} title="Minimum buy score to trigger the alert" onChange={(e) => setForm({ ...form, min_buy_score: e.target.value })} placeholder="min buy_score" />
            <input type="number" step="0.5" value={form.min_rvol} title="Minimum relative volume to trigger the alert" onChange={(e) => setForm({ ...form, min_rvol: e.target.value })} placeholder="min rvol" />
            <label className="rule-check" title="Only alert when a named whale / S+ investor is present"><input type="checkbox" checked={form.has_investor} onChange={(e) => setForm({ ...form, has_investor: e.target.checked })} /> has S+/whale</label>
            <button className="btn-secondary tiny" title="Create this alert rule" onClick={submitRule}>Add Rule</button>
          </div>
        </div>
      )}
    </section>
  )
}
