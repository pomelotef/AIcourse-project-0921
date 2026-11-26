import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'
import { fmtDateTime, useAsync } from '../util'

interface NotificationItem {
  id: number
  event_type: string
  summary: string
  actor: { id: number; name: string } | null
  project: { id: number; title: string }
  link: string
  read: boolean
  created_at: string
}

interface Bell {
  items: NotificationItem[]
  unread: number
}

/** Bell in the top bar. Refreshes itself on live updates (useAsync listens for them). */
export function NotificationBell() {
  const { data, reload } = useAsync(() => api.get<Bell>('/api/notifications'), [])
  const [open, setOpen] = useState(false)
  const box = useRef<HTMLDivElement>(null)
  const navigate = useNavigate()

  // Close when clicking anywhere else or pressing Escape.
  useEffect(() => {
    if (!open) return
    const onClick = (e: MouseEvent) => {
      if (box.current && !box.current.contains(e.target as Node)) setOpen(false)
    }
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false) }
    document.addEventListener('mousedown', onClick)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onClick)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  const unread = data?.unread ?? 0

  const openItem = async (n: NotificationItem) => {
    setOpen(false)
    if (!n.read) {
      try { await api.post(`/api/notifications/${n.id}/read`) } catch { /* still navigate */ }
      void reload({ silent: true })
    }
    navigate(n.link)
  }

  const readAll = async () => {
    await api.post('/api/notifications/read-all')
    void reload({ silent: true })
  }

  return (
    <div className="bell" ref={box}>
      <button
        className="ghost small bell-button"
        aria-label={unread ? `通知（${unread} 則未讀）` : '通知'}
        aria-expanded={open}
        onClick={() => setOpen(o => !o)}
      >
        <span aria-hidden>🔔</span>
        {unread > 0 && <span className="bell-count">{unread > 99 ? '99+' : unread}</span>}
      </button>
      {open && (
        <div className="bell-panel" role="dialog" aria-label="通知">
          <div className="bell-head">
            <strong>通知</strong>
            {unread > 0 && <button className="ghost small" onClick={() => void readAll()}>全部標為已讀</button>}
          </div>
          {!data || data.items.length === 0 ? (
            <p className="muted small bell-empty">目前沒有通知</p>
          ) : (
            <ul className="bell-list">
              {data.items.map(n => (
                <li key={n.id}>
                  <button className={`bell-item${n.read ? '' : ' unread'}`} onClick={() => void openItem(n)}>
                    <span className="bell-summary">
                      <strong>{n.actor?.name ?? '有人'}</strong>：{n.summary}
                    </span>
                    <span className="muted small">{n.project.title} · {fmtDateTime(n.created_at)}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}
