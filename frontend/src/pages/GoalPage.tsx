import { useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../auth'
import { ActionForm, ActionList } from '../components/actions'
import { BlockerList, LinkEditor, OutcomeCard, UpdateCard, type LinkDraft } from '../components/records'
import { Timeline } from '../components/Timeline'
import { UpdateForm } from '../components/UpdateForm'
import {
  BlockedBadge, Card, Empty, ErrorBox, ExternalLinks, GoalStateBadge, Loading, Multiline,
} from '../components/ui'
import { GOAL_STATE } from '../labels'
import type { Action, Blocker, Goal, GoalState, Link as LinkT, Note, Outcome, Project, Ref, Update } from '../types'
import { daysAgo, fmtDate, fmtDateTime, useAsync, useSubmit } from '../util'

interface GoalDetail {
  goal: Goal
  my_role: 'advisor' | 'student'
  parent: Ref | null
  summary: {
    latest_update: Update | null
    open_blockers: Blocker[]
    next_steps_text: string
    open_actions: Action[]
    latest_decision: Outcome | null
  }
  children: Goal[]
  updates: Update[]
  my_drafts: Update[]
  blockers: Blocker[]
  actions: Action[]
  outcomes: Outcome[]
  links: LinkT[]
  private_notes: Note[]
}

export default function GoalPage() {
  const id = Number(useParams().id)
  const { user } = useAuth()
  const me = user!
  const [params, setParams] = useSearchParams()
  const { data, error, loading, reload } = useAsync(() => api.get<GoalDetail>(`/api/goals/${id}`), [id])
  const projectId = data?.goal.project_id
  const project = useAsync(() => (projectId ? api.get<Project>(`/api/projects/${projectId}`) : Promise.resolve(null)), [projectId])
  const [convertFrom, setConvertFrom] = useState<Update | null>(null)
  const [addingAction, setAddingAction] = useState(false)

  if (loading && !data) return <Loading />
  if (!data) return <ErrorBox error={error} onRetry={reload} />
  const { goal, summary } = data
  const isAdvisor = data.my_role === 'advisor'
  const canEditGoal = isAdvisor || goal.created_by.id === me.id || goal.assignee?.id === me.id
  const draftId = Number(params.get('draft')) || null
  const editingDraft = draftId ? data.my_drafts.find((d) => d.id === draftId) : undefined
  const showForm = params.get('update') === '1' || !!editingDraft
  const closeForm = () => setParams({})
  const canResolve = (b: Blocker) => isAdvisor || b.reported_by.id === me.id || goal.assignee?.id === me.id
  const shared = goal.visibility === 'shared'

  return (
    <div className="stack">
      <div className="breadcrumb">
        <Link to={`/projects/${goal.project_id}`}>{project.data?.title ?? '專案'}</Link>
        {data.parent && <> / <Link to={`/goals/${data.parent.id}`}>{data.parent.title}</Link></>}
      </div>
      <div className="page-head">
        <div>
          <h1>{goal.title}</h1>
          <div className="meta">
            <GoalStateBadge state={goal.research_state} />
            <BlockedBadge count={goal.open_blocker_count} />
            <span>負責人：{goal.assignee?.name ?? '未指派'}</span>
            {goal.visibility === 'private' && <span className="badge draft">私人目標（只有你看得到）</span>}
          </div>
        </div>
        {shared && !showForm && <button onClick={() => setParams({ update: '1' })}>新增進度</button>}
      </div>
      {goal.research_question && <p className="question">研究問題：{goal.research_question}</p>}
      <ErrorBox error={error} onRetry={reload} />

      {showForm && (
        <Card title={editingDraft ? '編輯草稿' : '新增進度更新'}>
          <UpdateForm goalId={goal.id} openBlockers={summary.open_blockers} draft={editingDraft}
            onSaved={() => { closeForm(); reload() }} onCancel={closeForm} />
        </Card>
      )}

      {/* The four facts CP1's evaluation asks people to find within two minutes. */}
      <section className="summary" aria-label="目前狀態摘要">
        <div className="summary-item">
          <h3>最新進度</h3>
          {summary.latest_update ? (
            <>
              <div className="muted small">{summary.latest_update.author.name} · {fmtDateTime(summary.latest_update.published_at)}</div>
              <Multiline text={summary.latest_update.completed || summary.latest_update.findings} />
            </>
          ) : <Empty>尚無進度更新</Empty>}
        </div>
        <div className="summary-item">
          <h3>主要阻礙</h3>
          {summary.open_blockers.length ? (
            <ul className="plain">{summary.open_blockers.map((b) => <li key={b.id}><strong>#{b.id} {b.title}</strong> <span className="muted small">（{daysAgo(b.opened_at)}提出）</span></li>)}</ul>
          ) : <Empty>沒有未解決的 blocker</Empty>}
        </div>
        <div className="summary-item">
          <h3>下一步</h3>
          {summary.open_actions.length > 0 && (
            <ul className="plain">{summary.open_actions.slice(0, 4).map((a) => <li key={a.id}>□ {a.title} <span className="muted small">（{a.assignee.name}{a.due_date ? `，${fmtDate(a.due_date)}` : ''}）</span></li>)}</ul>
          )}
          {summary.next_steps_text && <div className="muted small">最新更新寫的下一步：{summary.next_steps_text}</div>}
          {!summary.open_actions.length && !summary.next_steps_text && <Empty>尚未設定下一步</Empty>}
        </div>
        <div className="summary-item">
          <h3>最近一次 Meeting 決定</h3>
          {summary.latest_decision ? (
            <>
              <div className="muted small">
                <Link to={`/meetings/${summary.latest_decision.meeting.id}`}>{summary.latest_decision.meeting.title}</Link>
                {' · '}{fmtDate(summary.latest_decision.meeting.occurred_at)}
                {summary.latest_decision.confirmation_state === 'pending' && ' · 待確認'}
              </div>
              <Multiline text={summary.latest_decision.decision} />
            </>
          ) : <Empty>尚無 meeting 決策</Empty>}
        </div>
      </section>

      {canEditGoal && <GoalSettings goal={goal} project={project.data} onSaved={reload} />}

      {data.children.length > 0 && (
        <Card title="子目標">
          <ul className="plain">
            {data.children.map((c) => (
              <li key={c.id}>
                <Link to={`/goals/${c.id}`}>{c.title}</Link> <GoalStateBadge state={c.research_state} /> <BlockedBadge count={c.open_blocker_count} />
                <span className="muted small"> {c.assignee?.name ?? '未指派'}</span>
              </li>
            ))}
          </ul>
        </Card>
      )}

      <div className="grid-2">
        <Card title="待辦 / 下一步" actions={shared && project.data && !addingAction && !convertFrom &&
          <button className="small" onClick={() => setAddingAction(true)}>新增待辦</button>}>
          {project.data && (addingAction || convertFrom) && (
            <ActionForm key={convertFrom?.id ?? 'new'} projectId={goal.project_id} members={project.data.members} me={me}
              isAdvisor={isAdvisor} defaultGoalId={goal.id} defaultAssigneeId={goal.assignee?.id}
              defaultTitle={convertFrom?.next_steps.split('\n')[0] ?? ''} sourceUpdateId={convertFrom?.id}
              onCreated={() => { setConvertFrom(null); setAddingAction(false); reload() }}
              onCancel={() => { setConvertFrom(null); setAddingAction(false) }} />
          )}
          <ActionList actions={data.actions} me={me} isAdvisor={isAdvisor} onChanged={reload} showGoal={false} />
        </Card>
        <Card title="Blockers">
          <BlockerList blockers={data.blockers} canResolve={canResolve} onChanged={reload} emptyText="沒有 blocker 紀錄" />
        </Card>
      </div>

      <Card title="研究進度">
        {data.my_drafts.length > 0 && (
          <div className="drafts">
            <strong className="small">我的草稿</strong>
            {data.my_drafts.map((d) => (
              <div key={d.id} className="draft-row">
                <UpdateCard u={d} showGoal={false} />
                <button className="small" onClick={() => setParams({ draft: String(d.id) })}>繼續編輯</button>
              </div>
            ))}
          </div>
        )}
        {data.updates.length === 0 ? <Empty>還沒有發布的進度更新</Empty> :
          data.updates.map((u) => (
            <UpdateCard key={u.id} u={u} showGoal={false}
              onConvert={project.data ? (x) => { setAddingAction(false); setConvertFrom(x) } : undefined} />
          ))}
      </Card>

      <Card title="Meeting 決策（新到舊，舊決策不會被覆蓋）">
        {data.outcomes.length === 0 ? <Empty>還沒有與此目標相關的 meeting 決策</Empty> :
          data.outcomes.map((o) => <OutcomeCard key={o.id} o={o} isAdvisor={isAdvisor} me={me} onChanged={reload} showMeeting />)}
      </Card>

      <div className="grid-2">
        <Card title="相關連結"><GoalLinks goalId={goal.id} links={data.links} onChanged={reload} /></Card>
        <Card title="我的私人筆記"><PrivateNotes projectId={goal.project_id} goalId={goal.id} notes={data.private_notes} onChanged={reload} /></Card>
      </div>

      <Card title="此目標的研究歷程"><Timeline projectId={goal.project_id} fixedGoalId={goal.id} /></Card>
    </div>
  )
}

function GoalSettings({ goal, project, onSaved }: { goal: Goal; project: Project | null; onSaved: () => void }) {
  const [open, setOpen] = useState(false)
  const [state, setState] = useState<GoalState>(goal.research_state)
  const [assignee, setAssignee] = useState<number | ''>(goal.assignee?.id ?? '')
  const [title, setTitle] = useState(goal.title)
  const [question, setQuestion] = useState(goal.research_question)
  const [visibility, setVisibility] = useState(goal.visibility)
  const { busy, error, run } = useSubmit()
  if (!open) return <button className="ghost small self-start" onClick={() => setOpen(true)}>調整目標（狀態、負責人…）</button>
  return (
    <Card title="調整研究目標">
      <form className="inline-form" onSubmit={(e) => {
        e.preventDefault()
        void run(async () => {
          await api.patch(`/api/goals/${goal.id}`, {
            title, research_question: question, research_state: state, assignee_id: assignee || null, visibility,
          })
          setOpen(false)
          onSaved()
        })
      }}>
        <label>名稱<input value={title} onChange={(e) => setTitle(e.target.value)} required /></label>
        <label>研究問題<textarea value={question} onChange={(e) => setQuestion(e.target.value)} rows={2} /></label>
        <div className="form-row">
          <label>研究狀態（由人判斷，不會自動改）
            <select value={state} onChange={(e) => setState(e.target.value as GoalState)}>
              {Object.entries(GOAL_STATE).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </label>
          <label>負責人
            <select value={assignee} onChange={(e) => setAssignee(e.target.value ? Number(e.target.value) : '')}>
              <option value="">未指派</option>
              {project?.members.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
            </select>
          </label>
          <label>可見範圍
            <select value={visibility} onChange={(e) => setVisibility(e.target.value as 'shared' | 'private')}>
              <option value="shared">專案共享</option>
              <option value="private">只有建立者</option>
            </select>
          </label>
        </div>
        <ErrorBox error={error} />
        <div className="buttons">
          <button type="submit" disabled={busy}>儲存</button>
          <button type="button" className="ghost" onClick={() => setOpen(false)}>取消</button>
        </div>
      </form>
    </Card>
  )
}

function GoalLinks({ goalId, links, onChanged }: { goalId: number; links: LinkT[]; onChanged: () => void }) {
  const [drafts, setDrafts] = useState<LinkDraft[]>([])
  const { busy, error, run } = useSubmit()
  return (
    <>
      {links.length ? <ExternalLinks links={links} /> : <Empty>還沒有連結</Empty>}
      <LinkEditor links={drafts} onChange={setDrafts} />
      {drafts.length > 0 && (
        <button className="small" disabled={busy} onClick={() => void run(async () => {
          for (const d of drafts.filter((x) => x.url.trim())) {
            await api.post('/api/links', { ...d, target_type: 'goal', target_id: goalId })
          }
          setDrafts([])
          onChanged()
        })}>儲存連結</button>
      )}
      <ErrorBox error={error} />
    </>
  )
}

function PrivateNotes({ projectId, goalId, notes, onChanged }:
  { projectId: number; goalId: number; notes: Note[]; onChanged: () => void }) {
  const [body, setBody] = useState('')
  const { busy, error, run } = useSubmit()
  return (
    <>
      <p className="muted small">只有你自己看得到，不會出現在時間軸或其他人的畫面。</p>
      {notes.map((n) => (
        <div key={n.id} className="note-row">
          <Multiline text={n.body} />
          <span className="muted small">{fmtDateTime(n.updated_at)}</span>
          <button className="link-btn" disabled={busy} onClick={() => void run(async () => { await api.del(`/api/notes/${n.id}`); onChanged() })}>刪除</button>
        </div>
      ))}
      <form className="inline-form" onSubmit={(e) => {
        e.preventDefault()
        void run(async () => {
          await api.post(`/api/projects/${projectId}/notes`, { body, goal_id: goalId })
          setBody('')
          onChanged()
        })
      }}>
        <textarea value={body} onChange={(e) => setBody(e.target.value)} rows={2} aria-label="私人筆記" required />
        <div className="buttons"><button className="small" type="submit" disabled={busy}>新增私人筆記</button></div>
      </form>
      <ErrorBox error={error} />
    </>
  )
}
