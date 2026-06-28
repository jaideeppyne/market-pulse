import { wsStatus, snapshotReceived, alertReceived } from './liveSlice'
import type { Middleware, MiddlewareAPI, Dispatch, AnyAction } from '@reduxjs/toolkit'
import type { Snapshot } from '../types'

// Maintains a single WebSocket to /ws, dispatching live snapshot + alert updates.
// Auto-reconnects with backoff. Started by dispatching { type: 'ws/connect' }.
//
// POLLING FALLBACK: whenever the socket is not OPEN (down / connecting / blocked),
// we poll GET /api/snapshot?light=true every ~20s and feed it into the SAME live
// state via snapshotReceived, so the UI keeps updating even if the WS never comes
// up (e.g. proxies that strip Upgrade, serverless hosts without WS support).
const POLL_INTERVAL_MS = 20000

export function createWsMiddleware(): Middleware {
  let socket: WebSocket | null = null
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  let pollTimer: ReturnType<typeof setInterval> | null = null
  let polling = false
  let stopped = false

  const mw: Middleware = (store: MiddlewareAPI<Dispatch, unknown>) => (next: Dispatch) => (action: AnyAction) => {
    if (action.type === 'ws/connect') {
      stopped = false
      connect(store)
      startPolling(store)
      return undefined
    }
    if (action.type === 'ws/disconnect') {
      stopped = true
      stopPolling()
      if (socket) socket.close()
      return undefined
    }
    return next(action)
  }
  return mw

  function socketIsOpen() {
    return !!socket && socket.readyState === WebSocket.OPEN
  }

  function connect(store: MiddlewareAPI<Dispatch, unknown>) {
    if (socket && (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)) return
    const proto = location.protocol === 'https:' ? 'wss' : 'ws'
    try {
      socket = new WebSocket(`${proto}://${location.host}/ws`)
    } catch (e) {
      scheduleReconnect(store)
      return
    }
    socket.onopen = () => store.dispatch(wsStatus('live'))
    socket.onclose = () => {
      store.dispatch(wsStatus('down'))
      if (!stopped) scheduleReconnect(store)
    }
    socket.onerror = () => { try { socket?.close() } catch (_) {} }
    socket.onmessage = (ev: MessageEvent) => {
      let msg: { type?: string; data?: Snapshot; alert?: unknown }
      try { msg = JSON.parse(ev.data) } catch (_) { return }
      if (msg.type === 'update' && msg.data) store.dispatch(snapshotReceived(msg.data))
      else if (msg.type === 'alert' && msg.alert) store.dispatch(alertReceived(msg.alert as any))
      // type 'ping' → ignore (keepalive)
    }
  }

  function scheduleReconnect(store: MiddlewareAPI<Dispatch, unknown>) {
    if (reconnectTimer || stopped) return
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null
      connect(store)
    }, 2000)
  }

  // ----- Polling fallback -------------------------------------------------
  function startPolling(store: MiddlewareAPI<Dispatch, unknown>) {
    if (pollTimer) return
    // Kick an immediate fetch so the UI has data even before the WS handshake
    // completes (or if WS is unavailable on this host). The guard in pollOnce
    // skips it once the socket is actually OPEN.
    setTimeout(() => { void pollOnce(store) }, 600)
    pollTimer = setInterval(() => { void pollOnce(store) }, POLL_INTERVAL_MS)
  }

  function stopPolling() {
    if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
  }

  async function pollOnce(store: MiddlewareAPI<Dispatch, unknown>) {
    // Only poll when the live socket isn't delivering data, and skip while a
    // request is already in flight or the tab is hidden (save bandwidth).
    if (stopped || polling || socketIsOpen()) return
    if (typeof document !== 'undefined' && document.hidden) return
    polling = true
    try {
      const res = await fetch('/api/snapshot?light=true', { headers: { Accept: 'application/json' } })
      if (!res.ok) return
      const data = (await res.json()) as Snapshot
      if (data && typeof data === 'object') store.dispatch(snapshotReceived(data))
    } catch (_) {
      // network error — leave status as-is, next tick retries
    } finally {
      polling = false
    }
  }
}
