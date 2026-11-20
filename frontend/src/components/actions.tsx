import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { ACTION_STATE, PRIORITY } from '../labels'
import type { Action, ActionState, Member, Priority, Ref, UserRef } from '../types'
import { fmtDate, useSubmit } from '../util'
import { ActionStateBadge, Empty, ErrorBox, GoalLink, PriorityBadge } from './ui'

interface ListProps {
  actions: Action[]
  me: UserRef
  isAdvisor: boolean
  onChanged: () => void
  showAssignee?: boolean
  showGoal?: boolean
  emptyText?: string
}

export function ActionList({ actions, me, isAdvisor, onChanged, showAssignee = true, showGoal = true,
  emptyText = '沒有待辦事項' }: ListProps) {
  if (!actions.length) return <Empty>{emptyText}</Empty>
  return (
    <ul className="action-list">
      {actions.map((a) => (
        <ActionRow key={a.id} a={a} canEdit={isAdvisor || a.assignee.id === me.id || a.created_by.id === me.id}
          onChanged={onChanged} showAssignee={showAssignee} showGoal={showGoal} />
      ))}
    </ul>
  )
}

function ActionRow({ a, canEdit, onChanged, showAssignee, showGoal }:
  { a: Action; canEdit: boolean; onChanged: () => void; showAssignee: boolean; showGoal: boolean }) {
  const [editing, setEditing] = useState(false)
  const closed = a.state === 'done' || a.state === 'canceled'
  const { busy, error, run } = useSubmit()

  const quick = (state: ActionState) => run(async () => {
    await api.patch(`/api/actions/${a.id}`, { state })
    onChanged()
  })

  return (
    <li className={`action ${closed ? 'closed' : ''}`} data-testid="action-row">
      <div className="action-main">
        <span className="check" aria-hidden>{a.state === 'done' ? '✓' : a.state === 'canceled' ? '✕' : '○'}</span>
        <div className="grow">
          <div className="action-title">
            <PriorityBadge priority={a.priority} /> {a.title}
          </div>
          <div className="meta">
            <ActionStateBadge state={a.state} />
            {showAssignee && <span>負責：{a.assignee.name}</span>}
            {a.due_date && <span className={a.overdue ? 'overdue' : ''}>期限 {fmtDate(a.due_date)}{a.overdue ? '（已過期）' : ''}</span>}
            {showGoal && a.goal && <span>目標：<GoalLink goal={a.goal} /></span>}
            {a.source_meeting && <span>來源：<Link to={`/meetings/${a.source_meeting.id}`}>{a.source_meeting.title}</Link></span>}
          </div>
          {a.note && <div className="note">備註：{a.note}</div>}
        </div>
        {canEdit && !editing && (
          <div className="row-actions">
            {a.state === 'open' && <button className="small" disabled={busy} onClick={() => quick('in_progress')}>開始</button>}
            {!closed && <button className="small" disabled={busy} onClick={() => quick('done')}>完成</button>}
            <button className="small ghost" onClick={() => setEditing(true)}>編輯</button>
          </div>
        )}
      </div>
      <ErrorBox error={error} />
      {editing && <ActionEdit a={a} onDone={() => { setEditing(false); onChanged() }} onCancel={() => setEditing(false)} />}
    </li>
  )
}

function ActionEdit({ a, onDone, onCancel }: { a: Action; onDone: () => void; onCancel: () => void }) {
  const [state, setState] = useState<ActionState>(a.state)
  const [priority, setPriority] = useState<Priority>(a.priority)
  const [due, setDue] = useState(a.due_date ?? '')
  const [note, setNote] = useState(a.note)
  const [reason, setReason] = useState('')
  const { busy, error, run } = useSubmit()
  const dueChanged = (a.due_date ?? '') !== due
  const needsReason = (state === 'canceled' && a.state !== 'canceled') || (dueChanged && !!a.due_date)

  const save = () => run(async () => {
    await api.patch(`/api/actions/${a.id}`, {
      state, priority, note,
      due_date: due || null,
      clear_due_date: !due && !!a.due_date,
      reason,
    })
    onDone()
  })

  return (
    <div className="inline-form">
      <div className="form-row">
        <label>狀態
          <select value={state} onChange={(e) => setState(e.target.value as ActionState)}>
            {Object.entries(ACTION_STATE).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </label>
        <label>優先度
          <select value={priority} onChange={(e) => setPriority(e.target.value as Priority)}>
            {Object.entries(PRIORITY).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </label>
        <label>期限
          <input type="date" value={due} onChange={(e) => setDue(e.target.value)} />
        </label>
      </div>
      <label>備註 / 完成說明
        <input value={note} onChange={(e) => setNote(e.target.value)} />
      </label>
      {needsReason && (
        <label>原因（取消或改期必填，會保留在時間軸）
          <input value={reason} onChange={(e) => setReason(e.target.value)} required />
        </label>
      )}
      <ErrorBox error={error} />
      <div className="buttons">
        <button onClick={save} disabled={busy}>儲存</button>
        <button className="ghost" onClick={onCancel}>取消</button>
      </div>
    </div>
  )
}

interface FormProps {
  projectId: number
  members: Member[]
  me: UserRef
  isAdvisor: boolean
  goals?: Ref[]
  defaultGoalId?: number | null
  defaultAssigneeId?: number
  sourceMeetingId?: number
  sourceUpdateId?: number
  defaultTitle?: string
  onCreated: () => void
  onCancel?: () => void
}

export function ActionForm(p: FormProps) {
  const assignable = p.isAdvisor ? p.members : p.members.filter((m) => m.id === p.me.id)
  const [title, setTitle] = useState(p.defaultTitle ?? '')
  const [assignee, setAssignee] = useState<number>(p.defaultAssigneeId ?? assignable.find((m) => m.role === 'student')?.id ?? p.me.id)
  const [goalId, setGoalId] = useState<number | ''>(p.defaultGoalId ?? '')
  const [priority, setPriority] = useState<Priority>('medium')
  const [due, setDue] = useState('')
  const { busy, error, run } = useSubmit()

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    void run(async () => {
      await api.post(`/api/projects/${p.projectId}/actions`, {
        title, assignee_id: assignee, goal_id: goalId || null, priority, due_date: due || null,
        source_meeting_id: p.sourceMeetingId ?? null, source_update_id: p.sourceUpdateId ?? null,
      })
      setTitle('')
      setDue('')
      p.onCreated()
    })
  }

  return (
    <form className="inline-form" onSubmit={submit} aria-label="新增待辦">
      <label>待辦事項
        <input value={title} onChange={(e) => setTitle(e.target.value)} required maxLength={300}
          placeholder="例如：重新執行 profiling" />
      </label>
      <div className="form-row">
        <label>負責人
          <select value={assignee} onChange={(e) => setAssignee(Number(e.target.value))}>
            {assignable.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
          </select>
        </label>
        <label>優先度
          <select value={priority} onChange={(e) => setPriority(e.target.value as Priority)}>
            {Object.entries(PRIORITY).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </label>
        <label>期限（可選）
          <input type="date" value={due} onChange={(e) => setDue(e.target.value)} />
        </label>
      </div>
      {p.goals && (
        <label>關聯研究目標（可選）
          <select value={goalId} onChange={(e) => setGoalId(e.target.value ? Number(e.target.value) : '')}>
            <option value="">不關聯</option>
            {p.goals.map((g) => <option key={g.id} value={g.id}>{g.title}</option>)}
          </select>
        </label>
      )}
      <ErrorBox error={error} />
      <div className="buttons">
        <button type="submit" disabled={busy}>新增待辦</button>
        {p.onCancel && <button type="button" className="ghost" onClick={p.onCancel}>取消</button>}
      </div>
    </form>
  )
}
