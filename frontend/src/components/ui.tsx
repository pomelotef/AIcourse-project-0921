import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { ACTION_STATE, CATEGORY, GOAL_STATE, PRIORITY } from '../labels'
import type { ActionState, GoalState, Link as LinkT, MeetingCategory, Priority } from '../types'
import { LINK_TYPE } from '../labels'

export function Loading({ label = '載入中…' }: { label?: string }) {
  return <p className="muted" role="status">{label}</p>
}

export function ErrorBox({ error, onRetry }: { error: string | null; onRetry?: () => void }) {
  if (!error) return null
  return (
    <div className="error" role="alert">
      {error}
      {onRetry && <button className="link-btn" onClick={onRetry}>重試</button>}
    </div>
  )
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="empty">{children}</p>
}

export function Card({ title, actions, children, className = '' }:
  { title?: ReactNode; actions?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={`card ${className}`}>
      {(title || actions) && (
        <header className="card-head">
          {title && <h2>{title}</h2>}
          {actions && <div className="card-actions">{actions}</div>}
        </header>
      )}
      {children}
    </section>
  )
}

export function GoalStateBadge({ state }: { state: GoalState }) {
  return <span className={`badge goal-${state}`}>{GOAL_STATE[state]}</span>
}

export function ActionStateBadge({ state }: { state: ActionState }) {
  return <span className={`badge action-${state}`}>{ACTION_STATE[state]}</span>
}

export function PriorityBadge({ priority }: { priority: Priority }) {
  return <span className={`badge prio-${priority}`} title="優先度">{PRIORITY[priority]}</span>
}

export function CategoryBadge({ category }: { category: MeetingCategory }) {
  return <span className={`badge cat-${category}`}>{CATEGORY[category]}</span>
}

export function BlockedBadge({ count }: { count?: number }) {
  if (!count) return null
  return <span className="badge blocked">卡住 · {count}</span>
}

export function ExternalLinks({ links }: { links: LinkT[] }) {
  if (!links.length) return null
  return (
    <ul className="links">
      {links.map((l) => (
        <li key={l.id}>
          <a href={l.url} target="_blank" rel="noopener noreferrer">
            {l.label || l.url}
          </a>
          <span className="muted small"> · {LINK_TYPE[l.link_type]}</span>
        </li>
      ))}
    </ul>
  )
}

export function GoalLink({ goal }: { goal: { id: number; title: string } | null }) {
  if (!goal) return null
  return <Link to={`/goals/${goal.id}`} className="goal-link">{goal.title}</Link>
}

export function Multiline({ text }: { text: string }) {
  if (!text) return null
  return <p className="multiline">{text}</p>
}
