import { useLazyEdgeQuery } from '../store/api'

const GUIDE = [
  ['1. Hot Movers', 'Buy score = next-entry rank (bases, room to run, news). Quality = full checklist. Use Early buys only to hide extended names.'],
  ['2. Whale / Politician (S+)', 'Gold badges = named buy in news: Kela, Kacholia, Buffett, Pelosi, FII flows. Scored at S+ (6.5× weight).'],
  ['3. Catalysts column', 'S+, Smart Money, News, Earnings, Extended badges summarize why a name is hot. Click the factor pill for the full 100+ checklist.'],
  ['4. Earnings', 'Who reports in the next 7 days. “TODAY” = results today.'],
  ['5. Sectors', 'Cyclical strip = growth / cyclical / defensive. Each sector shows counts, rotation tag, and ranked picks.'],
  ['6. Live updates', 'Green “Live” pill = WebSocket connected. Rankings refresh automatically each scan batch.'],
  ['7. My List + Alerts', 'Watch any ticker. Alert rules (buy_score + rvol + has S+) push live notifications and auto-add high-conviction names.'],
  ['8. Analyze', 'Type a ticker in the top search + Enter to run the full deep engine and open its detail + factor breakdown.'],
]

export default function Edge() {
  // Edge query is lazily triggered so the historical backtest only loads on demand.
  return <EdgeInner />
}

function EdgeInner() {
  const [trigger, { data, isFetching, isUninitialized }] = useLazyEdgeQuery()
  const buckets = data?.buckets || data?.score_buckets || []

  return (
    <section className="panel pad guide">
      <h2 className="view-h">Edge &amp; Guide</h2>
      <div className="guide-grid">
        {GUIDE.map(([h, p]) => (
          <div key={h} className="guide-card"><h3>{h}</h3><p>{p}</p></div>
        ))}
        <div className="guide-card span-2">
          <h3>Backtest Edge / Historical Performance</h3>
          <p>Real backtesting from scan snapshots + forward returns (1d/3d/7d/14d). Hit rates by score bucket + confidence breakdowns + factor performance.</p>
          <button className="btn-secondary small" title="Load / refresh historical backtest edge statistics" onClick={() => trigger()} disabled={isFetching} style={{ marginTop: 8 }}>
            {isFetching ? 'Loading…' : 'Load / Refresh live Edge stats'}
          </button>
          <div className="edge-results">
            {isUninitialized && <span className="muted">Click to load backtest edge.</span>}
            {data && buckets.length === 0 && <pre style={{ whiteSpace: 'pre-wrap', fontFamily: 'var(--mono)', fontSize: 11.5, color: 'var(--text-2)' }}>{JSON.stringify(data, null, 2).slice(0, 4000)}</pre>}
            {buckets.length > 0 && (
              <table className="data-table" style={{ marginTop: 8 }}>
                <thead><tr><th>Bucket</th><th>Samples</th><th>Avg 7d</th><th>Hit rate</th></tr></thead>
                <tbody>
                  {buckets.map((b, i) => (
                    <tr key={i}><td>{b.bucket || b.label}</td><td>{b.samples ?? b.n}</td><td className={(b.avg_7d ?? 0) >= 0 ? 'pos' : 'neg'}>{b.avg_7d ?? b.avg_return ?? '—'}</td><td>{b.hit_rate ?? '—'}</td></tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      </div>
      <p className="muted">Not financial advice. Verify on NSE/BSE or SEC before trading.</p>
    </section>
  )
}
