import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../auth'
import { ActionForm, ActionList } from '../components/actions'
import { AiSummary } from '../components/AiSummary'
import { BlockerList, OutcomeCard, UpdateCard } from '../components/records'
import { Card, CategoryBadge, Empty, ErrorBox, Loading, Multiline } from '../components/ui'
import type { Action, Blocker, Goal, Meeting, Outcome, Project, Update, UserRef } from '../types'
import { fmtDate, fmtDateTime, useAsync, useSubmit } from '../util'

interface MeetingDetail { meeting: Meeting; my_role: 'advisor' | 'student'; outcomes: Outcome[]; actions: Action[] }
interface Brief {
  meeting: Meeting
  member: UserRef | null
  is_first_meeting: boolean
  previous_meeting: Meeting | null
  window: { start: string | null; end: string }
  previous_outcomes: Outcome[]
  previous_commitments: Action[]
  carried_over_actions: Action[]
  updates: Update[]
  open_blockers: Blocker[]
  resolved_blockers: Blocker[]
  agenda: string
}

export default function MeetingPage() {
  const id = Number(useParams().id)
  const { user } = useAuth()
  const me = user!
  const [memberId, setMemberId] = useState<number | ''>('')
  const detail = useAsync(() => api.get<MeetingDetail>(`/api/meetings/${id}`), [id])
  const brief = useAsync(
    () => api.get<Brief>(`/api/meetings/${id}/brief${memberId ? `?member_id=${memberId}` : ''}`), [id, memberId])
  const pid = detail.data?.meeting.project_id
  const project = useAsync(() => (pid ? api.get<Project>(`/api/projects/${pid}`) : Promise.resolve(null)), [pid])
  const goals = useAsync(() => (pid ? api.get<Goal[]>(`/api/projects/${pid}/goals`) : Promise.resolve([] as Goal[])), [pid])
  const [addingAction, setAddingAction] = useState(false)

  if (detail.loading && !detail.data) return <Loading />
  if (!detail.data) return <ErrorBox error={detail.error} onRetry={detail.reload} />
  const { meeting, outcomes, actions } = detail.data
  const isAdvisor = detail.data.my_role === 'advisor'
  const sharedGoals = (goals.data ?? []).filter((g) => g.visibility === 'shared')
  const reloadAll = () => { detail.reload(); brief.reload() }
  const b = brief.data

  return (
    <div className="stack">
      <div className="breadcrumb"><Link to={`/projects/${meeting.project_id}?tab=meetings`}>{project.data?.title ?? '專案'}</Link></div>
      <div className="page-head">
        <div>
          <h1>{meeting.title}</h1>
          <div className="meta">
            <CategoryBadge category={meeting.category} />
            <span>{fmtDateTime(meeting.occurred_at)}</span>
            <span>參與：{meeting.participants.map((p) => p.name).join('、')}</span>
          </div>
        </div>
        <label className="inline">只看
          <select value={memberId} onChange={(e) => setMemberId(e.target.value ? Number(e.target.value) : '')} aria-label="只看某位成員">
            <option value="">全部成員</option>
            {project.data?.members.filter((m) => m.role === 'student').map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
          </select>
        </label>
      </div>

      <ErrorBox error={brief.error} onRetry={brief.reload} />
      {!b ? <Loading label="整理 Meeting Brief…" /> : (
        <>
          <p className="muted small">
            {b.is_first_meeting
              ? `這是此專案第一次 ${categoryText(meeting)}，沒有先前的同分類 meeting；以下列出到本次為止的進度、blocker 與未完成待辦。`
              : <>比較範圍：上次同分類 meeting <Link to={`/meetings/${b.previous_meeting!.id}`}>{b.previous_meeting!.title}</Link>（{fmtDate(b.window.start)}）之後到本次 meeting。</>}
          </p>
          <AiSummary key={`${id}-${memberId}`} meetingId={id} memberId={memberId} />
          <div className="grid-2">
            <Card title="上次 Meeting 的承諾">
              {b.is_first_meeting ? <Empty>無先前紀錄</Empty> : (
                <>
                  {b.previous_outcomes.map((o) => (
                    <div key={o.id} className="prev-decision">決策：{o.decision}{o.rationale && <span className="muted">（理由：{o.rationale}）</span>}</div>
                  ))}
                  <ActionList actions={b.previous_commitments} me={me} isAdvisor={isAdvisor} onChanged={reloadAll} emptyText="上次 meeting 沒有建立待辦" />
                </>
              )}
              {b.carried_over_actions.length > 0 && (
                <>
                  <h3 className="sub">更早之前仍未完成</h3>
                  <ActionList actions={b.carried_over_actions} me={me} isAdvisor={isAdvisor} onChanged={reloadAll} />
                </>
              )}
            </Card>
            <Card title={`期間的進度更新（${b.updates.length}）`}>
              {b.updates.length === 0 ? <Empty>這段期間沒有新的進度更新</Empty> : b.updates.map((u) => <UpdateCard key={u.id} u={u} />)}
            </Card>
          </div>
          <div className="grid-2">
            <Card title="未解決的 Blocker">
              <BlockerList blockers={b.open_blockers} canResolve={(x) => isAdvisor || x.reported_by.id === me.id} onChanged={reloadAll} />
              {b.resolved_blockers.length > 0 && (
                <>
                  <h3 className="sub">期間已解決</h3>
                  <BlockerList blockers={b.resolved_blockers} canResolve={() => false} onChanged={reloadAll} />
                </>
              )}
            </Card>
            <Card title="待討論問題">
              {b.agenda ? <Multiline text={b.agenda} /> : <Empty>未填寫</Empty>}
            </Card>
          </div>
        </>
      )}

      <Card title="本次決策、理由、回饋">
        {outcomes.length === 0 && <Empty>還沒有記錄本次 meeting 的結論</Empty>}
        {outcomes.map((o) => <OutcomeCard key={o.id} o={o} isAdvisor={isAdvisor} me={me} onChanged={reloadAll} />)}
        <OutcomeForm meetingId={meeting.id} goals={sharedGoals} isAdvisor={isAdvisor} onCreated={reloadAll} />
      </Card>

      <Card title="本次 meeting 產生的待辦" actions={!addingAction && project.data && <button className="small" onClick={() => setAddingAction(true)}>新增待辦</button>}>
        {addingAction && project.data && (
          <ActionForm projectId={meeting.project_id} members={project.data.members} me={me} isAdvisor={isAdvisor}
            goals={sharedGoals} sourceMeetingId={meeting.id} defaultAssigneeId={memberId || undefined}
            onCreated={() => { setAddingAction(false); reloadAll() }} onCancel={() => setAddingAction(false)} />
        )}
        <ActionList actions={actions} me={me} isAdvisor={isAdvisor} onChanged={reloadAll} emptyText="尚未建立待辦" />
      </Card>
    </div>
  )
}

function categoryText(m: Meeting): string {
  return { lab: 'Lab Meeting', industry: '產學 Meeting', one_on_one: '個別 Meeting', other: '其他 Meeting' }[m.category]
}

function OutcomeForm({ meetingId, goals, isAdvisor, onCreated }:
  { meetingId: number; goals: Goal[]; isAdvisor: boolean; onCreated: () => void }) {
  const [goalId, setGoalId] = useState<number | ''>('')
  const [decision, setDecision] = useState('')
  const [rationale, setRationale] = useState('')
  const [feedback, setFeedback] = useState('')
  const { busy, error, run } = useSubmit()
  return (
    <form className="inline-form outcome-form" aria-label="記錄 meeting 結論" onSubmit={(e) => {
      e.preventDefault()
      void run(async () => {
        await api.post(`/api/meetings/${meetingId}/outcomes`, { goal_id: goalId || null, decision, rationale, feedback })
        setDecision(''); setRationale(''); setFeedback('')
        onCreated()
      })
    }}>
      <h3 className="sub">記錄結論</h3>
      <label>相關研究目標
        <select value={goalId} onChange={(e) => setGoalId(e.target.value ? Number(e.target.value) : '')}>
          <option value="">整個專案</option>
          {goals.map((g) => <option key={g.id} value={g.id}>{g.title}</option>)}
        </select>
      </label>
      <label>決策<textarea value={decision} onChange={(e) => setDecision(e.target.value)} required rows={2}
        placeholder="例如：先驗證量測方法，再給 Vulkan 一週" /></label>
      <label>理由<textarea value={rationale} onChange={(e) => setRationale(e.target.value)} rows={2} /></label>
      <label>回饋 / 修改建議<textarea value={feedback} onChange={(e) => setFeedback(e.target.value)} rows={2} /></label>
      {!isAdvisor && <p className="muted small">學生記錄的結論會標示為「待指導者確認」，避免把單方筆記當成雙方共識。</p>}
      <ErrorBox error={error} />
      <div className="buttons"><button type="submit" disabled={busy}>儲存結論</button></div>
    </form>
  )
}
