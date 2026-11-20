import { useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../auth'
import { ActionForm, ActionList } from '../components/actions'
import { Timeline } from '../components/Timeline'
import { BlockedBadge, Card, CategoryBadge, Empty, ErrorBox, GoalStateBadge, Loading } from '../components/ui'
import { CATEGORY, GOAL_STATE, ROLE } from '../labels'
import type { Action, Goal, GoalState, Meeting, MeetingCategory, Member, Project, Role } from '../types'
import { daysAgo, fmtDateTime, toLocalInput, useAsync, useSubmit } from '../util'

const TABS = { goals: '研究目標', meetings: 'Meetings', actions: '待辦', timeline: '時間軸', members: '成員' } as const
type Tab = keyof typeof TABS

export default function ProjectPage() {
  const id = Number(useParams().id)
  const [params, setParams] = useSearchParams()
  const tab = (params.get('tab') as Tab) || 'goals'
  const project = useAsync(() => api.get<Project>(`/api/projects/${id}`), [id])
  const goals = useAsync(() => api.get<Goal[]>(`/api/projects/${id}/goals`), [id])

  if (project.loading && !project.data) return <Loading />
  if (!project.data) return <ErrorBox error={project.error} onRetry={project.reload} />
  const p = project.data
  const isAdvisor = p.my_role === 'advisor'

  return (
    <div className="stack">
      <div className="page-head">
        <div>
          <h1>{p.title}</h1>
          {p.description && <p className="muted">{p.description}</p>}
        </div>
        <span className="badge">{ROLE[p.my_role]}</span>
      </div>
      <nav className="tabs" role="tablist">
        {(Object.keys(TABS) as Tab[]).map((t) => (
          <button key={t} role="tab" aria-selected={tab === t} className={tab === t ? 'active' : ''}
            onClick={() => setParams({ tab: t })}>{TABS[t]}</button>
        ))}
      </nav>
      {tab === 'goals' && <GoalsTab project={p} goals={goals.data} error={goals.error} reload={goals.reload} />}
      {tab === 'meetings' && <MeetingsTab project={p} />}
      {tab === 'actions' && <ActionsTab project={p} goals={(goals.data ?? []).filter((g) => g.visibility === 'shared')} />}
      {tab === 'timeline' && <Card><Timeline projectId={id} goals={goals.data ?? []} /></Card>}
      {tab === 'members' && <MembersTab project={p} isAdvisor={isAdvisor} onChanged={project.reload} />}
    </div>
  )
}

// ---------------- goals tree ----------------
function GoalsTab({ project, goals, error, reload }:
  { project: Project; goals: Goal[] | null; error: string | null; reload: () => void }) {
  const [adding, setAdding] = useState(false)
  if (!goals) return error ? <ErrorBox error={error} onRetry={reload} /> : <Loading />
  const children = (pid: number | null) => goals.filter((g) => g.parent_id === pid)
  const ids = new Set(goals.map((g) => g.id))
  const roots = goals.filter((g) => g.parent_id === null || !ids.has(g.parent_id))

  const render = (g: Goal, depth: number): React.ReactNode => (
    <li key={g.id}>
      <div className="tree-row" style={{ paddingLeft: depth * 20 }}>
        <Link to={`/goals/${g.id}`} className="goal-title">{g.title}</Link>
        <GoalStateBadge state={g.research_state} />
        <BlockedBadge count={g.open_blocker_count} />
        {g.visibility === 'private' && <span className="badge draft">私人</span>}
        <span className="muted small">{g.assignee?.name ?? '未指派'} · 最近更新 {daysAgo(g.last_update_at)}</span>
      </div>
      {children(g.id).length > 0 && <ul className="tree">{children(g.id).map((c) => render(c, depth + 1))}</ul>}
    </li>
  )

  return (
    <Card title="研究目標" actions={!adding && <button onClick={() => setAdding(true)}>新增目標</button>}>
      {adding && <GoalForm project={project} goals={goals} onDone={() => { setAdding(false); reload() }} onCancel={() => setAdding(false)} />}
      {goals.length === 0 ? <Empty>還沒有研究目標。{project.my_role === 'advisor' ? '建立第一個研究問題並指派給學生。' : ''}</Empty> : (
        <ul className="tree">{roots.map((g) => render(g, 0))}</ul>
      )}
    </Card>
  )
}

function GoalForm({ project, goals, onDone, onCancel }:
  { project: Project; goals: Goal[]; onDone: () => void; onCancel: () => void }) {
  const { user } = useAuth()
  const isAdvisor = project.my_role === 'advisor'
  const [title, setTitle] = useState('')
  const [question, setQuestion] = useState('')
  const [parent, setParent] = useState<number | ''>('')
  const [assignee, setAssignee] = useState<number | ''>(isAdvisor ? '' : user!.id)
  const [state, setState] = useState<GoalState>('planned')
  const [visibility, setVisibility] = useState<'shared' | 'private'>('shared')
  const { busy, error, run } = useSubmit()
  const assignable = isAdvisor ? project.members : project.members.filter((m) => m.id === user!.id)

  return (
    <form className="inline-form" aria-label="新增研究目標" onSubmit={(e) => {
      e.preventDefault()
      void run(async () => {
        await api.post(`/api/projects/${project.id}/goals`, {
          title, research_question: question, parent_id: parent || null,
          assignee_id: assignee || null, research_state: state, visibility,
        })
        onDone()
      })
    }}>
      <label>目標名稱<input value={title} onChange={(e) => setTitle(e.target.value)} required maxLength={200} /></label>
      <label>研究問題<textarea value={question} onChange={(e) => setQuestion(e.target.value)} rows={2} /></label>
      <div className="form-row">
        <label>上層目標
          <select value={parent} onChange={(e) => setParent(e.target.value ? Number(e.target.value) : '')}>
            <option value="">（無，最上層）</option>
            {goals.filter((g) => g.visibility === 'shared' || visibility === 'private').map((g) => <option key={g.id} value={g.id}>{g.title}</option>)}
          </select>
        </label>
        <label>負責人
          <select value={assignee} onChange={(e) => setAssignee(e.target.value ? Number(e.target.value) : '')}>
            <option value="">未指派</option>
            {assignable.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
          </select>
        </label>
        <label>研究狀態
          <select value={state} onChange={(e) => setState(e.target.value as GoalState)}>
            {Object.entries(GOAL_STATE).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </label>
      </div>
      <label>可見範圍
        <select value={visibility} onChange={(e) => setVisibility(e.target.value as 'shared' | 'private')}>
          <option value="shared">專案共享（成員都看得到）</option>
          <option value="private">只有我自己（私人規劃，不能指派給他人）</option>
        </select>
      </label>
      <ErrorBox error={error} />
      <div className="buttons">
        <button type="submit" disabled={busy}>建立目標</button>
        <button type="button" className="ghost" onClick={onCancel}>取消</button>
      </div>
    </form>
  )
}

// ---------------- meetings ----------------
function MeetingsTab({ project }: { project: Project }) {
  const [category, setCategory] = useState('')
  const [adding, setAdding] = useState(false)
  const { data, error, loading, reload } = useAsync(
    () => api.get<Meeting[]>(`/api/projects/${project.id}/meetings${category ? `?category=${category}` : ''}`),
    [project.id, category])

  return (
    <Card title="Meetings" actions={!adding && <button onClick={() => setAdding(true)}>新增 Meeting</button>}>
      {adding && <MeetingForm project={project} onCancel={() => setAdding(false)} />}
      <div className="filters">
        <select value={category} onChange={(e) => setCategory(e.target.value)} aria-label="Meeting 分類">
          <option value="">全部分類</option>
          {Object.entries(CATEGORY).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
      </div>
      <ErrorBox error={error} onRetry={reload} />
      {loading && !data ? <Loading /> : !data?.length ? <Empty>還沒有 meeting 紀錄</Empty> : (
        <ul className="plain meeting-list">
          {data.map((m) => (
            <li key={m.id}>
              <CategoryBadge category={m.category} />
              <Link to={`/meetings/${m.id}`}>{m.title}</Link>
              <span className="muted small">{fmtDateTime(m.occurred_at)} · {m.outcome_count} 項決策
                {m.pending_outcome_count ? ` · ${m.pending_outcome_count} 項待確認` : ''}</span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}

function MeetingForm({ project, onCancel }: { project: Project; onCancel: () => void }) {
  const navigate = useNavigate()
  const { user } = useAuth()
  const [title, setTitle] = useState('')
  const [category, setCategory] = useState<MeetingCategory>('lab')
  const [when, setWhen] = useState(toLocalInput(new Date()))
  const [agenda, setAgenda] = useState('')
  const [participants, setParticipants] = useState<number[]>(project.members.map((m) => m.id))
  const { busy, error, run } = useSubmit()
  return (
    <form className="inline-form" aria-label="新增 Meeting" onSubmit={(e) => {
      e.preventDefault()
      void run(async () => {
        const m = await api.post<Meeting>(`/api/projects/${project.id}/meetings`, {
          title, category, occurred_at: new Date(when).toISOString(), agenda,
          participant_ids: participants.length ? participants : [user!.id],
        })
        navigate(`/meetings/${m.id}`)
      })
    }}>
      <div className="form-row">
        <label>標題<input value={title} onChange={(e) => setTitle(e.target.value)} required maxLength={200}
          placeholder="例如：Lab Meeting 11/20" /></label>
        <label>分類
          <select value={category} onChange={(e) => setCategory(e.target.value as MeetingCategory)}>
            {Object.entries(CATEGORY).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </label>
        <label>時間<input type="datetime-local" value={when} onChange={(e) => setWhen(e.target.value)} required /></label>
      </div>
      <label>待討論問題（可選）<textarea value={agenda} onChange={(e) => setAgenda(e.target.value)} rows={2} /></label>
      <fieldset>
        <legend>參與者</legend>
        {project.members.map((m) => (
          <label key={m.id} className="check-label">
            <input type="checkbox" checked={participants.includes(m.id)}
              onChange={(e) => setParticipants(e.target.checked ? [...participants, m.id] : participants.filter((x) => x !== m.id))} />
            {m.name}
          </label>
        ))}
      </fieldset>
      <ErrorBox error={error} />
      <div className="buttons">
        <button type="submit" disabled={busy}>建立並開啟 Brief</button>
        <button type="button" className="ghost" onClick={onCancel}>取消</button>
      </div>
    </form>
  )
}

// ---------------- actions ----------------
function ActionsTab({ project, goals }: { project: Project; goals: Goal[] }) {
  const { user } = useAuth()
  const [assignee, setAssignee] = useState<number | ''>('')
  const [state, setState] = useState('open')
  const [adding, setAdding] = useState(false)
  const qs = new URLSearchParams()
  if (assignee) qs.set('assignee_id', String(assignee))
  if (state) qs.set('state', state)
  const q = qs.toString()
  const { data, error, loading, reload } = useAsync(
    () => api.get<Action[]>(`/api/projects/${project.id}/actions${q ? `?${q}` : ''}`), [project.id, q])
  const isAdvisor = project.my_role === 'advisor'

  return (
    <Card title="待辦（依優先度與期限排序）" actions={!adding && <button onClick={() => setAdding(true)}>新增待辦</button>}>
      {adding && (
        <ActionForm projectId={project.id} members={project.members} me={user!} isAdvisor={isAdvisor}
          goals={goals} onCreated={() => { setAdding(false); reload() }} onCancel={() => setAdding(false)} />
      )}
      <div className="filters">
        <select value={assignee} onChange={(e) => setAssignee(e.target.value ? Number(e.target.value) : '')} aria-label="負責人">
          <option value="">所有人</option>
          {project.members.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
        </select>
        <select value={state} onChange={(e) => setState(e.target.value)} aria-label="狀態">
          <option value="open">未完成</option>
          <option value="done">已完成</option>
          <option value="canceled">已取消</option>
          <option value="">全部</option>
        </select>
      </div>
      <ErrorBox error={error} onRetry={reload} />
      {loading && !data ? <Loading /> : <ActionList actions={data ?? []} me={user!} isAdvisor={isAdvisor} onChanged={reload} />}
    </Card>
  )
}

// ---------------- members ----------------
function MembersTab({ project, isAdvisor, onChanged }: { project: Project; isAdvisor: boolean; onChanged: () => void }) {
  const [email, setEmail] = useState('')
  const [role, setRole] = useState<Role>('student')
  const { busy, error, run } = useSubmit()
  const change = (m: Member, body: { role: Role } | null) => run(async () => {
    if (body) await api.patch(`/api/projects/${project.id}/members/${m.id}`, body)
    else await api.del(`/api/projects/${project.id}/members/${m.id}`)
    onChanged()
  })
  return (
    <Card title="成員">
      <ul className="plain">
        {project.members.map((m) => (
          <li key={m.id} className="member-row">
            <strong>{m.name}</strong> <span className="muted small">{m.email}</span> <span className="badge">{ROLE[m.role]}</span>
            {isAdvisor && (
              <span className="row-actions">
                <button className="small ghost" disabled={busy}
                  onClick={() => void change(m, { role: m.role === 'advisor' ? 'student' : 'advisor' })}>
                  改為{m.role === 'advisor' ? '學生' : '指導者'}
                </button>
                <button className="small ghost" disabled={busy} onClick={() => void change(m, null)}>移除</button>
              </span>
            )}
          </li>
        ))}
      </ul>
      {isAdvisor ? (
        <form className="inline-form" aria-label="加入成員" onSubmit={(e) => {
          e.preventDefault()
          void run(async () => {
            await api.post(`/api/projects/${project.id}/members`, { email, role })
            setEmail('')
            onChanged()
          })
        }}>
          <div className="form-row">
            <label>Email（對方需先註冊）<input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required /></label>
            <label>角色
              <select value={role} onChange={(e) => setRole(e.target.value as Role)}>
                <option value="student">學生</option>
                <option value="advisor">指導者</option>
              </select>
            </label>
          </div>
          <div className="buttons"><button type="submit" disabled={busy}>加入成員</button></div>
        </form>
      ) : <p className="muted small">只有指導者可以管理成員。</p>}
      <ErrorBox error={error} />
    </Card>
  )
}
