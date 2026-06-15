import { wsStatus, snapshotReceived, alertReceived } from './liveSlice'

// Maintains a single WebSocket to /ws, dispatching live snapshot + alert updates.
// Auto-reconnects with backoff. Started by dispatching { type: 'ws/connect' }.
export function createWsMiddleware() {
  let socket = null
  let reconnectTimer = null
  let stopped = false

  return (store) => (next) => (action) => {
    if (action.type === 'ws/connect') {
      connect(store)
      return
    }
    if (action.type === 'ws/disconnect') {
      stopped = true
      if (socket) socket.close()
      return
    }
    return next(action)
  }

  function connect(store) {
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
    socket.onerror = () => { try { socket.close() } catch (_) {} }
    socket.onmessage = (ev) => {
      let msg
      try { msg = JSON.parse(ev.data) } catch (_) { return }
      if (msg.type === 'update' && msg.data) store.dispatch(snapshotReceived(msg.data))
      else if (msg.type === 'alert' && msg.alert) store.dispatch(alertReceived(msg.alert))
      // type 'ping' → ignore (keepalive)
    }
  }

  function scheduleReconnect(store) {
    if (reconnectTimer) return
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null
      connect(store)
    }, 2000)
  }
}
