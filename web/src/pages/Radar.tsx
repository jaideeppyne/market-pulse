import { selectSymbol } from '../store/uiSlice'
import { hasSmartMoney, getHotPool, whaleView, displayName } from '../lib/format'
import { useAppDispatch, useAppSelector } from '../store/hooks'
import type { WhaleView } from '../lib/format'

interface RadarItem extends WhaleView {
  symbol?: string
  name?: string // company display name for the ticker
}

const TYPE_ORDER = ['Legend', 'Politician', 'FII', 'Insider', 'Promoter']

export default function Radar() {
  const dispatch = useAppDispatch()
  const data = useAppSelector((s) => s.live.data)
  const events = data?.investor_events || []
  const pool = getHotPool(data || {}, 'all')
  const hot = pool.filter(hasSmartMoney)
  // quick symbol -> company name lookup so each whale row can show the company too
  const nameBySym = new Map<string, string>()
  for (const r of pool) if (r.symbol) nameBySym.set(r.symbol, displayName(r))

  const items: RadarItem[] = []
  // Investor events (richest source — backend may enrich these)
  for (const ev of events) {
    const w = whaleView(ev)
    items.push({ ...w, symbol: ev.symbol, name: ev.symbol ? nameBySym.get(ev.symbol) : undefined })
  }
  // Smart-money hits attached to hot rows
  for (const r of hot) {
    const sm = r.metrics?.smart_money
    const hits = sm?.hits?.length ? sm.hits : [{}]
    for (const h of hits) {
      const w = whaleView(h, sm?.primary_alert || (r.alerts || [])[0] || '')
      items.push({ ...w, symbol: r.symbol, name: r.symbol ? nameBySym.get(r.symbol) : undefined })
    }
  }

  // De-dupe by investor + symbol
  const seen = new Set<string>()
  const uniq = items.filter((it) => {
    const k = (it.symbol || '') + '|' + it.investor
    if (seen.has(k)) return false
    seen.add(k)
    return it.investor && it.investor !== 'Smart money' ? true : !!it.symbol
  })

  // Sort by conviction then recency (rank encodes both)
  uniq.sort((a, b) => b.rank - a.rank)

  // Group by investor type for prominent display
  const groups = new Map<string, RadarItem[]>()
  for (const it of uniq) {
    const g = it.typeLabel || 'Signal'
    if (!groups.has(g)) groups.set(g, [])
    groups.get(g)!.push(it)
  }
  const groupKeys = [...groups.keys()].sort((a, b) => {
    const ia = TYPE_ORDER.indexOf(a); const ib = TYPE_ORDER.indexOf(b)
    return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib)
  })

  const convClass = (c: string) =>
    c === 'S+' ? 'conv-sp' : c === 'S' ? 'conv-s' : c === 'A' ? 'conv-a' : 'conv-b'

  return (
    <section className="panel pad">
      <h2 className="view-h">S+ Radar <span className="view-h__sub">Named smart money &amp; politician activity</span></h2>
      <p className="panel-hint">Legends, politicians, FII flows, insiders &amp; promoters surfaced from news intel + the smart_money registry — grouped by type, sorted by conviction &amp; recency. Click any row to inspect.</p>

      {uniq.length === 0 && <p className="muted">No named smart-money activity in the current scan window.</p>}

      {groupKeys.map((g) => (
        <div key={g} className="radar-group">
          <div className="radar-group__head">
            <span className={'whale-type whale-type--' + g.toLowerCase()}>{g}</span>
            <span className="muted">{groups.get(g)!.length} signal{groups.get(g)!.length === 1 ? '' : 's'}</span>
          </div>
          <div className="radar-list">
            {groups.get(g)!.map((it, i) => (
              <div
                key={g + i}
                className="radar-row whale-card"
                title={it.blurb || `${it.investor} · ${it.symbol || ''}`}
                onClick={() => it.symbol && dispatch(selectSymbol(it.symbol))}
              >
                <div className="whale-card__top">
                  <span className="whale-card__investor">{it.investor}</span>
                  {it.typeLabel && <span className={'whale-type whale-type--' + it.typeLabel.toLowerCase()}>{it.typeLabel}</span>}
                  {it.conviction && <span className={'whale-conv ' + convClass(it.conviction)}>{it.conviction}</span>}
                  {it.action && <span className="whale-action">{it.action}</span>}
                  <span className="whale-card__spacer" />
                  {it.recency && <span className="whale-card__time muted" title="How recently this was seen">{it.recency}</span>}
                </div>
                <div className="whale-card__sub">
                  {it.symbol && (
                    <span className="whale-card__ticker">
                      {it.symbol}{it.name ? <span className="muted"> · {it.name}</span> : null}
                    </span>
                  )}
                </div>
                {it.blurb && <div className="whale-card__blurb">{it.blurb}</div>}
              </div>
            ))}
          </div>
        </div>
      ))}
    </section>
  )
}
