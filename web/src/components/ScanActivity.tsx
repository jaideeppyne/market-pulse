import { useEffect, useMemo, useRef, useState } from 'react'
import { useAppSelector } from '../store/hooks'
import { getHotPool, researchOf, displayName, timeAgo } from '../lib/format'
import type { Row } from '../types'

const PHASES = [
  'Pulling candidates from multiple sources…',
  'Fetching live prices & volume…',
  'Scoring 105+ technical & fundamental factors…',
  'Grading fundamentals & publishing research…',
]

type FullJob = { id?: string; status: string; progress: number } | null
type Feed = { sym: string; name: string; grade: string; facs: string[]; hit?: number; total?: number }

function useCountUp(target: number, ms = 600) {
  const [val, setVal] = useState(target)
  const from = useRef(target)
  const start = useRef(0)
  const raf = useRef(0)
  useEffect(() => {
    cancelAnimationFrame(raf.current)
    from.current = val
    start.current = performance.now()
    const step = (t: number) => {
      const k = Math.min(1, (t - start.current) / ms)
      const eased = 1 - Math.pow(1 - k, 3)
      setVal(Math.round(from.current + (target - from.current) * eased))
      if (k < 1) raf.current = requestAnimationFrame(step)
    }
    raf.current = requestAnimationFrame(step)
    return () => cancelAnimationFrame(raf.current)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [target])
  return val
}

function factorsOf(r: Row): { facs: string[]; hit?: number; total?: number } {
  const tf = ((r as any).top_factors || (r.metrics as any)?.top_weighted_factors || []) as any[]
  const facs = tf.map((f) => f?.label || f?.id).filter(Boolean).slice(0, 6)
  const hit = (r as any).factors_hit ?? (r.metrics as any)?.factors_hit
  const total = (r as any).factors_total ?? (r.metrics as any)?.factors_total
  return { facs, hit, total }
}

export default function ScanActivity({ discovering = false, fullJob = null }: { discovering?: boolean; fullJob?: FullJob }) {
  const data = useAppSelector((s) => s.live.data)
  const stats: any = data?.stats || {}
  const pool = useAppSelector((s) => getHotPool(s.live.data || {}, 'all'))

  const fullActive = fullJob?.status === 'running'
  const bgScanning = !!stats.scan_in_progress
  const active = discovering || fullActive || bgScanning

  const batch = Number(stats.scan_batch || 0)
  const batchTotal = Number(stats.scan_batches_total || 0)
  const pct = fullActive
    ? Math.max(5, Math.min(99, fullJob?.progress || 0))
    : batchTotal > 0 ? Math.round((batch / batchTotal) * 100) : (active ? 8 : 0)

  const symbols = useCountUp(Number(stats.symbols_tracked || 0))
  const candidates = useCountUp(Number(stats.last_price_batch_result_count || 0))
  const hot = useCountUp(Number(stats.hot_count || 0))
  const strong = useCountUp(useMemo(() => pool.filter((r) => researchOf(r)?.fundamentally_strong).length, [pool]))

  const analyzing: string[] = stats.analyzing_symbols || []

  const [phaseIdx, setPhaseIdx] = useState(0)
  useEffect(() => {
    if (!active) return
    const t = setInterval(() => setPhaseIdx((i) => (i + 1) % PHASES.length), 2600)
    return () => clearInterval(t)
  }, [active])

  // live find-feed with REAL factors for each scored stock
  const [feed, setFeed] = useState<Feed[]>([])
  const seenRef = useRef<Set<string>>(new Set())
  const tick = stats.live_tick
  useEffect(() => {
    if (!active) return
    const fresh: Feed[] = []
    for (const r of pool as Row[]) {
      if (seenRef.current.has(r.symbol)) continue
      seenRef.current.add(r.symbol)
      const res = researchOf(r)
      const { facs, hit, total } = factorsOf(r)
      fresh.push({
        sym: r.symbol,
        name: displayName(r) || r.symbol,
        grade: res?.grade ? `Grade ${res.grade}` : `score ${Math.round(Number((r.metrics || {}).buy_score ?? r.score ?? 0))}`,
        facs, hit, total,
      })
    }
    if (fresh.length) setFeed((f) => [...fresh.reverse(), ...f].slice(0, 6))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tick, active, pool.length])

  useEffect(() => {
    if (discovering || fullActive) { seenRef.current = new Set(); setFeed([]) }
  }, [discovering, fullActive])

  // Always-on heartbeat: even when no scan is mid-flight, show a slim live bar
  if (!active && feed.length === 0) {
    const lastTick = stats.last_price_tick || stats.last_price_scan
    return (
      <section className="scan-activity is-idle">
        <div className="scan-activity__top">
          <span className="scan-dot live" />
          <span className="scan-phase">Live · {Number(stats.symbols_tracked || 0)} symbols tracked{stats.hot_count ? ` · ${stats.hot_count} hot setups` : ''}</span>
          <span className="scan-batch">{lastTick ? `updated ${timeAgo(lastTick)}` : 'connecting…'}</span>
        </div>
      </section>
    )
  }

  const phaseText = fullActive ? `Exhaustive scan — ${PHASES[phaseIdx]}`
    : discovering ? `Discovering — ${PHASES[phaseIdx]}`
    : active ? PHASES[phaseIdx] : 'Scan complete'

  // factors currently being checked = factors of the most recent scored stock (real labels)
  const checking = feed[0]?.facs || []

  return (
    <section className={'scan-activity' + (active ? ' is-active' : ' is-done')}>
      <div className="scan-activity__top">
        <span className="scan-dot" />
        <span className="scan-phase">{active ? phaseText : 'Latest scan complete — results below'}</span>
        <span className="scan-batch">{fullActive ? `${pct}%` : batchTotal > 0 ? `batch ${batch}/${batchTotal}` : active ? 'starting…' : ''}</span>
      </div>

      <div className="scan-bar"><div className="scan-bar__fill" style={{ width: pct + '%' }}><span className="scan-bar__shimmer" /></div></div>

      <div className="scan-stats">
        <div className="scan-chip"><b>{symbols}</b><span>symbols processed</span></div>
        <div className="scan-chip"><b>{candidates}</b><span>candidates this batch</span></div>
        <div className="scan-chip"><b>{hot}</b><span>hot setups</span></div>
        <div className="scan-chip accent"><b>★ {strong}</b><span>fundamentally strong</span></div>
      </div>

      {analyzing.length > 0 && (
        <div className="scan-now">
          <span className="scan-now__label">Analyzing now</span>
          <div className="scan-now__chips">
            {analyzing.slice(0, 14).map((s) => <span key={s} className="scan-now__chip">{s}</span>)}
          </div>
        </div>
      )}

      {checking.length > 0 && (
        <div className="scan-checking">
          <span className="scan-checking__label">Checking factors</span>
          <div className="scan-checking__pills">
            {checking.map((c, i) => <span key={i} className="scan-fac">✓ {c}</span>)}
          </div>
        </div>
      )}

      {feed.length > 0 && (
        <div className="scan-feed">
          {feed.map((f, i) => (
            <div key={f.sym + i} className={'scan-feed__row' + (i === 0 ? ' fresh' : '')}>
              <span className="scan-feed__arrow">▲</span>
              <span className="scan-feed__sym">{f.sym}</span>
              <span className="scan-feed__grade">{f.grade}</span>
              {f.hit != null && f.total != null && <span className="scan-feed__count">{f.hit}/{f.total} factors</span>}
              <div className="scan-feed__facs">
                {f.facs.slice(0, 4).map((c, j) => <span key={j} className="scan-fac sm">{c}</span>)}
                {f.facs.length > 4 && <span className="scan-fac sm more">+{f.facs.length - 4}</span>}
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  )
}
