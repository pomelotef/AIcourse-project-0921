import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'

/**
 * Live refresh. One EventSource per tab listens on /api/stream. The server only says
 * "project N changed"; we then fire a window event and every useAsync() on the page re-fetches
 * quietly through the normal API (so permissions are always checked by the backend).
 */
export const LIVE_EVENT = 'labpulse:changed'
const DEBOUNCE_MS = 300

export type LiveStatus = 'connecting' | 'live' | 'offline'

const LiveContext = createContext<LiveStatus>('connecting')

export function LiveProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<LiveStatus>('connecting')

  useEffect(() => {
    const source = new EventSource('/api/stream')
    let timer: number | undefined
    let connectedBefore = false

    // Several writes in a row (e.g. an update plus its blockers) become one refresh.
    const announce = () => {
      window.clearTimeout(timer)
      timer = window.setTimeout(() => window.dispatchEvent(new Event(LIVE_EVENT)), DEBOUNCE_MS)
    }

    source.addEventListener('ready', () => {
      setStatus('live')
      // After a dropped connection we may have missed changes, so catch up once.
      if (connectedBefore) announce()
      connectedBefore = true
    })
    source.addEventListener('changed', announce)
    // EventSource reconnects by itself (server sends retry: 3000); just reflect the state.
    source.onerror = () => setStatus(source.readyState === EventSource.CLOSED ? 'offline' : 'connecting')

    return () => {
      window.clearTimeout(timer)
      source.close()
    }
  }, [])

  return <LiveContext.Provider value={status}>{children}</LiveContext.Provider>
}

export function useLiveStatus() {
  return useContext(LiveContext)
}

const LABEL: Record<LiveStatus, string> = {
  connecting: '連線中…',
  live: '即時更新',
  offline: '未連線，請重新整理',
}

export function LiveIndicator() {
  const status = useLiveStatus()
  return (
    <span className={`live-dot live-${status}`} role="status"
      title={status === 'live' ? '其他人儲存的內容會自動出現，不用重新整理' : LABEL[status]}>
      {LABEL[status]}
    </span>
  )
}
