import { createContext, useCallback, useContext, useRef, useState } from 'react'
import type { ReactNode } from 'react'

type ToastKind = 'info' | 'success' | 'error'
interface Toast { id: number; kind: ToastKind; msg: string }
interface ToastApi { push: (msg: string, kind?: ToastKind) => void }

const ToastContext = createContext<ToastApi>({ push: () => {} })

// App-wide ephemeral notifications. Idiomatic React Context (complements Redux,
// which holds durable state) — used for mutation feedback instead of alert().
export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])
  const seq = useRef(0)

  const push = useCallback((msg: string, kind: ToastKind = 'info') => {
    const id = ++seq.current
    setToasts((t) => [...t, { id, kind, msg }])
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 3200)
  }, [])

  return (
    <ToastContext.Provider value={{ push }}>
      {children}
      <div className="toast-stack">
        {toasts.map((t) => (
          <div key={t.id} className={'toast toast--' + t.kind}>{t.msg}</div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast() {
  return useContext(ToastContext)
}
