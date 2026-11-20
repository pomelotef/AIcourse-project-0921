import { useState } from 'react'
import { api } from '../api'
import { CATEGORY, EVENT_KIND, eventKind } from '../labels'
import type { Ref, TimelineEvent } from '../types'
import { fmtDateTime, useAsync } from '../util'
import { Empty, ErrorBox, GoalLink, Loading } from './ui'

export function Timeline({ projectId, goals, fixedGoalId }: { projectId: number; goals?: Ref[]; fixedGoalId?: number }) {
  const [goalId, setGoalId] = useState<number | ''>(fixedGoalId ?? '')
  const [category, setCategory] = useState('')
  const [kind, setKind] = useState('')
  const params = new URLSearchParams()
  if (goalId) params.set('goal_id', String(goalId))
  if (category) params.set('category', category)
  if (kind) params.set('kind', kind)
  const qs = params.toString()
  const { data, error, loading, reload } = useAsync(
    () => api.get<TimelineEvent[]>(`/api/projects/${projectId}/timeline${qs ? `?${qs}` : ''}`), [projectId, qs])

  // group by local date
  const groups: [string, TimelineEvent[]][] = []
  for (const e of data ?? []) {
    const day = new Date(e.created_at).toLocaleDateString('zh-TW', { year: 'numeric', month: 'long', day: 'numeric', weekday: 'short' })
    const last = groups[groups.length - 1]
    if (last && last[0] === day) last[1].push(e)
    else groups.push([day, [e]])
  }

  return (
    <div className="timeline">
      <div className="filters">
        {goals && fixedGoalId === undefined && (
          <select value={goalId} onChange={(e) => setGoalId(e.target.value ? Number(e.target.value) : '')} aria-label="依目標篩選">
            <option value="">全部目標</option>
            {goals.map((g) => <option key={g.id} value={g.id}>{g.title}</option>)}
          </select>
        )}
        <select value={kind} onChange={(e) => setKind(e.target.value)} aria-label="依類型篩選">
          <option value="">全部類型</option>
          {Object.entries(EVENT_KIND).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
        <select value={category} onChange={(e) => setCategory(e.target.value)} aria-label="依 Meeting 分類篩選">
          <option value="">全部 Meeting 分類</option>
          {Object.entries(CATEGORY).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
      </div>
      <ErrorBox error={error} onRetry={reload} />
      {loading && !data ? <Loading /> : groups.length === 0 ? <Empty>沒有符合條件的研究紀錄</Empty> : (
        groups.map(([day, events]) => (
          <section key={day} className="tl-day">
            <h3>{day}</h3>
            <ul>
              {events.map((e) => (
                <li key={e.id} className={`tl-item kind-${eventKind(e.event_type)}`} data-testid="timeline-item">
                  <span className="tl-kind">{EVENT_KIND[eventKind(e.event_type)] ?? '專案'}</span>
                  <div className="grow">
                    <div>{e.summary}</div>
                    <div className="meta">
                      <span>{e.actor.name}</span>
                      <span>{fmtDateTime(e.created_at)}</span>
                      {e.goal && fixedGoalId !== e.goal.id && <span><GoalLink goal={e.goal} /></span>}
                      {e.meeting_category && <span>{CATEGORY[e.meeting_category]}</span>}
                      {e.private && <span className="badge draft">私人</span>}
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          </section>
        ))
      )}
    </div>
  )
}
