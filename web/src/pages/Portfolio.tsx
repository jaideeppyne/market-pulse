import { useState } from 'react'
import { selectSymbol } from '../store/uiSlice'
import { useAppDispatch } from '../store/hooks'
import {
  usePortfolioQuery, useJournalQuery, useAddPositionMutation,
  useClosePositionMutation, useLazyAnalyzeQuery,
} from '../store/api'

interface PositionForm {
  symbol: string
  qty: number | string
  entry: string
  sl: string
  target: string
  notes: string
}

export default function Portfolio() {
  const dispatch = useAppDispatch()
  const { data: pf } = usePortfolioQuery()
  const { data: jr } = useJournalQuery()
  const [addPosition] = useAddPositionMutation()
  const [closePosition] = useClosePositionMutation()
  const [triggerAnalyze] = useLazyAnalyzeQuery()
  const [form, setForm] = useState<PositionForm>({ symbol: '', qty: 100, entry: '', sl: '', target: '', notes: '' })
  const [busy, setBusy] = useState(false)

  const positions = pf?.positions || []
  const journal = jr?.journal || []
  const summary = pf?.summary || {}

  const submit = async () => {
    const symbol = form.symbol.trim().toUpperCase()
    if (!symbol) return
    setBusy(true)
    try {
      // Backend requires an entry_price; if the user didn't type one, resolve the
      // live price via the same analyze engine (mirrors the close-position fallback).
      let entryPrice = Number(form.entry) || undefined
      if (!entryPrice) {
        const row = await triggerAnalyze(symbol).unwrap().catch(() => null)
        entryPrice = Number(row?.metrics?.price) || undefined
      }
      if (!entryPrice) {
        alert('Could not resolve a price for ' + symbol + '. Enter an Entry $ manually.')
        return
      }
      await addPosition({
        symbol, qty: Number(form.qty) || 1, entry_price: entryPrice,
        sl: form.sl ? Number(form.sl) : undefined,
        target: form.target ? Number(form.target) : undefined,
        notes: form.notes || undefined,
      }).unwrap()
      setForm({ symbol: '', qty: 100, entry: '', sl: '', target: '', notes: '' })
    } catch (e) {
      const err = e as { data?: { detail?: string }; error?: string }
      alert('Paper buy failed: ' + (err?.data?.detail || err?.error || 'error'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="panel pad">
      <h2 className="view-h">Portfolio <span className="view-h__sub">Paper Trading Journal (server-persisted)</span></h2>
      <p className="panel-hint">Track paper buys with entry thesis. Live Buy/Qual &amp; est P&amp;L. Close records realized PnL + outcome.</p>

      <div className="portfolio-summary">
        <div className="stat-row"><span className="label">Open Positions</span><span className="value">{positions.length}</span></div>
        <div className="stat-row"><span className="label">Est P&amp;L</span><span className={'value ' + ((summary.unrealized_pnl ?? 0) >= 0 ? 'pos' : 'neg')}>{summary.unrealized_pnl ?? 0}</span></div>
        <div className="stat-row"><span className="label">Realized</span><span className={'value ' + ((summary.realized_pnl ?? 0) >= 0 ? 'pos' : 'neg')}>{summary.realized_pnl ?? 0}</span></div>
      </div>

      <h3 className="view-h3">Open paper positions</h3>
      <div className="table-wrap">
        <table className="data-table">
          <thead><tr><th>Symbol</th><th>Entry</th><th>Qty</th><th>Est P&amp;L</th><th>SL / Target</th><th>Notes</th><th>Actions</th></tr></thead>
          <tbody>
            {positions.length === 0 && <tr><td colSpan={7} className="muted">No open positions. Log a paper buy below or 📁 from the Hot Movers table.</td></tr>}
            {positions.map((p) => (
              <tr key={p.symbol} title={`Open ${p.symbol}${p.name && p.name !== p.symbol ? ' (' + p.name + ')' : ''}`} onClick={() => dispatch(selectSymbol(p.symbol))}>
                <td className="symbol-cell">{p.symbol}{p.name && p.name !== p.symbol ? (<><br /><span className="sym__name">{p.name}</span></>) : null}</td>
                <td>{p.entry_price}</td>
                <td>{p.qty}</td>
                <td className={(p.est_pnl ?? 0) >= 0 ? 'pos' : 'neg'}>{p.est_pnl ?? '—'}</td>
                <td className="muted">{p.sl ?? '—'} / {p.target ?? '—'}</td>
                <td className="muted">{p.notes || ''}</td>
                <td><button className="btn-danger tiny" title={`Close the paper position in ${p.symbol} (records realized P&L)`} onClick={(e) => { e.stopPropagation(); closePosition({ symbol: p.symbol }) }}>Close</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="portfolio-form panel">
        <h3 className="view-h3">Log new paper buy</h3>
        <div className="port-form-row">
          <input type="text" placeholder="SYMBOL" title="Ticker symbol to log a paper buy for" value={form.symbol} onChange={(e) => setForm({ ...form, symbol: e.target.value })} />
          <input type="number" placeholder="Qty" title="Number of shares" value={form.qty} onChange={(e) => setForm({ ...form, qty: e.target.value })} />
          <input type="number" placeholder="Entry $ (auto)" title="Entry price — leave blank to auto-fill the live price" value={form.entry} onChange={(e) => setForm({ ...form, entry: e.target.value })} />
          <input type="number" placeholder="SL $" title="Stop-loss price (optional)" value={form.sl} onChange={(e) => setForm({ ...form, sl: e.target.value })} />
          <input type="number" placeholder="Target $" title="Target / take-profit price (optional)" value={form.target} onChange={(e) => setForm({ ...form, target: e.target.value })} />
          <input type="text" placeholder="Notes / thesis" title="Your entry thesis / notes (optional)" value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
          <button className="btn-primary" title="Log this paper buy to the journal" onClick={submit} disabled={busy}>{busy ? 'Logging…' : '📁 Log Paper Buy'}</button>
        </div>
        <p className="muted small-note">Entry price pulled from live state / analyze if omitted. One position per symbol.</p>
      </div>

      <h3 className="view-h3">Journal history</h3>
      <div className="journal-list">
        {journal.length === 0 && <div className="muted" style={{ padding: 8 }}>No journal entries yet.</div>}
        {journal.map((j, i) => (
          <div key={i} className="journal-row">
            <strong>{j.symbol}</strong> <span className="muted">{j.action}</span> @ {j.price} × {j.qty}
            {j.outcome_pnl != null && <span className={'realized ' + (j.outcome_pnl >= 0 ? 'pos' : 'neg')}> · PnL {j.outcome_pnl}</span>}
            {j.notes && <span className="muted"> · {j.notes}</span>}
          </div>
        ))}
      </div>
    </section>
  )
}
