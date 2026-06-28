import { createSlice } from '@reduxjs/toolkit'
import type { PayloadAction } from '@reduxjs/toolkit'
import type { ClientAlert, LiveState, Row, ServerAlert, Snapshot } from '../types'

const initialState: LiveState = {
  status: 'connecting',  // connecting | live | down
  data: null,            // full snapshot payload
  alerts: [],            // accumulated alert feed (newest first)
  seen: {},              // dedup keys for derived alerts
  lastGeneration: -1,
}

function hasSmartMoney(r: Row) {
  const sm = r?.metrics?.smart_money
  if (sm?.hits?.length) return true
  return (r?.alerts || []).some((a) => /LEGEND|WHALE|POLITICIAN|FOREIGN BUY|SMART MONEY/i.test(a))
}

// Derive client-side alerts from a snapshot's hot list (high conviction / smart money),
// mirroring the legacy behaviour so the Intelligence Feed populates live.
function deriveAlerts(state: LiveState, data: Snapshot) {
  const hot = [
    ...(data.hot || []),
    ...((data.hot_by_market && data.hot_by_market.us) || []),
    ...((data.hot_by_market && data.hot_by_market.india) || []),
    ...((data.hot_by_market && data.hot_by_market.uk) || []),
  ]
  const now = new Date().toISOString()
  for (const r of hot) {
    const score = Number(r.buy_score ?? r.score ?? (r.metrics && r.metrics.buy_score) ?? 0)
    const key = r.symbol
    if (!key) continue
    if (score >= 78 && !state.seen['high:' + key]) {
      state.seen['high:' + key] = true
      state.alerts.unshift({ type: 'high_score', symbol: key, msg: `Buy score ${Math.round(score)} — strong setup`, ts: now, score })
    }
    if (hasSmartMoney(r) && !state.seen['sm:' + key]) {
      state.seen['sm:' + key] = true
      const sm = r.metrics?.smart_money
      const primary = sm?.primary_alert || (r.alerts || []).find((a) => /LEGEND|WHALE|POLITICIAN|FOREIGN/i.test(a)) || 'Named smart money buy'
      state.alerts.unshift({ type: 'smart_money', symbol: key, msg: primary, ts: now, score })
    }
    if ((r.earnings_soon || r.metrics?.earnings_pre) && score > 55 && !state.seen['earn:' + key]) {
      state.seen['earn:' + key] = true
      state.alerts.unshift({ type: 'pre_earnings', symbol: key, msg: 'Pre-earnings setup + base/catalyst factors', ts: now, score })
    }
  }
  // Fold in server-pushed rich alerts from snapshot
  for (const sa of data.alerts || []) {
    const k = 'srv:' + sa.symbol + ':' + (sa.message || '')
    if (state.seen[k]) continue
    state.seen[k] = true
    state.alerts.unshift({ type: sa.rule_type || 'server', symbol: sa.symbol, msg: sa.message, ts: sa.triggered_at || now, score: sa.buy_score, server: true })
  }
  if (state.alerts.length > 40) state.alerts.length = 40
}

const liveSlice = createSlice({
  name: 'live',
  initialState,
  reducers: {
    wsStatus: (s, a: PayloadAction<LiveState['status']>) => { s.status = a.payload },
    snapshotReceived: (s, a: PayloadAction<Snapshot>) => {
      s.data = a.payload
      deriveAlerts(s, a.payload)
      s.lastGeneration = a.payload.scan_generation ?? s.lastGeneration
    },
    alertReceived: (s, a: PayloadAction<ServerAlert & Partial<ClientAlert>>) => {
      const al = a.payload
      const k = 'push:' + al.symbol + ':' + (al.message || al.msg || '')
      if (s.seen[k]) return
      s.seen[k] = true
      s.alerts.unshift({ type: al.rule_type || 'server', symbol: al.symbol, msg: al.message || al.msg, ts: al.triggered_at || al.ts || new Date().toISOString(), score: al.buy_score, server: true })
      if (s.alerts.length > 40) s.alerts.length = 40
    },
  },
})

export const { wsStatus, snapshotReceived, alertReceived } = liveSlice.actions
export default liveSlice.reducer
