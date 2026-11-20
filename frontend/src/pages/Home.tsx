import { Link } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../auth'
import { ActionList } from '../components/actions'
import { BlockerList, OutcomeCard, UpdateCard } from '../components/records'
import { BlockedBadge, Card, CategoryBadge, Empty, ErrorBox, GoalStateBadge, Loading } from '../components/ui'
import type { Action, Blocker, Goal, Meeting, Outcome, Update } from '../types'
import { daysAgo, fmtDate, useAsync } from '../util'

interface HomeData {
  projects: { id: number; title: string; state: string; my_role: string }[]
  is_advisor: boolean
  my_goals: Goal[]
  my_actions: Action[]
  my_open_blockers: Blocker[]
  recent_feedback: Outcome[]
  pending_confirmation: Outcome[]
  drafts: Update[]
  recent_updates: Update[]
  last_meetings: Meeting[]
  upcoming_meetings: Meeting[]
}

function MeetingRows({ meetings }: { meetings: Meeting[] }) {
  return (
    <ul className="plain">
      {meetings.map((m) => (
        <li key={m.id}>
          <CategoryBadge category={m.category} /> <Link to={`/meetings/${m.id}`}>{m.title}</Link>
          <span className="muted small"> · {m.project_title} · {fmtDate(m.occurred_at)}</span>
        </li>
      ))}
    </ul>
  )
}

export default function Home() {
  const { user } = useAuth()
  const { data, error, loading, reload } = useAsync(() => api.get<HomeData>('/api/me/home'), [])
  if (loading && !data) return <Loading />
  if (!data) return <ErrorBox error={error} onRetry={reload} />
  const me = user!

  if (data.projects.length === 0) {
    return (
      <div className="stack">
        <h1>我的研究</h1>
        <Card>
          <Empty>你還沒有加入任何研究專案。可以<Link to="/projects">建立專案</Link>，或請指導者用你的 email 把你加入專案。</Empty>
        </Card>
      </div>
    )
  }

  return (
    <div className="stack">
      <div className="page-head">
        <h1>我的研究</h1>
        <Link className="button" to="/projects">所有專案</Link>
      </div>
      <ErrorBox error={error} onRetry={reload} />

      {data.pending_confirmation.length > 0 && (
        <Card title={`待你確認的 meeting 結論（${data.pending_confirmation.length}）`} className="attention">
          {data.pending_confirmation.map((o) => (
            <OutcomeCard key={o.id} o={o} isAdvisor me={me} onChanged={reload} showMeeting />
          ))}
        </Card>
      )}

      <div className="grid-2">
        <Card title="目前研究重點">
          {data.my_goals.length === 0 ? <Empty>目前沒有指派給你的研究目標</Empty> : (
            <ul className="goal-list">
              {data.my_goals.map((g) => (
                <li key={g.id}>
                  <Link to={`/goals/${g.id}`} className="goal-title">{g.title}</Link>
                  <div className="meta">
                    <GoalStateBadge state={g.research_state} />
                    <BlockedBadge count={g.open_blocker_count} />
                    {g.visibility === 'private' && <span className="badge draft">私人</span>}
                    <span>{g.project_title}</span>
                    <span>最近更新：{daysAgo(g.last_update_at)}</span>
                  </div>
                  {g.visibility === 'shared' && (
                    <Link to={`/goals/${g.id}?update=1`} className="small-link">+ 新增進度</Link>
                  )}
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card title="Meetings">
          {data.upcoming_meetings.length > 0 && (
            <>
              <h3 className="sub">即將到來（點進去看 Brief）</h3>
              <MeetingRows meetings={data.upcoming_meetings} />
            </>
          )}
          <h3 className="sub">上次 Meeting（各分類）</h3>
          {data.last_meetings.length === 0 ? <Empty>尚無 meeting 紀錄</Empty> : <MeetingRows meetings={data.last_meetings} />}
        </Card>
      </div>

      <div className="grid-2">
        <Card title="下一步（我的待辦）">
          <ActionList actions={data.my_actions} me={me} isAdvisor={false} onChanged={reload}
            showAssignee={false} emptyText="沒有未完成的待辦" />
        </Card>
        <Card title="指導者回饋 / 最近決策">
          {data.recent_feedback.length === 0 ? <Empty>還沒有 meeting 決策</Empty> :
            data.recent_feedback.slice(0, 4).map((o) => (
              <OutcomeCard key={o.id} o={o} isAdvisor={false} me={me} onChanged={reload} showMeeting />
            ))}
        </Card>
      </div>

      <div className="grid-2">
        <Card title="目前 Blocker">
          <BlockerList blockers={data.my_open_blockers} canResolve={() => true} onChanged={reload} />
        </Card>
        <Card title="最近研究更新">
          {data.drafts.length > 0 && (
            <div className="drafts">
              <strong className="small">草稿（{data.drafts.length}）</strong>
              <ul className="plain">
                {data.drafts.map((d) => (
                  <li key={d.id}><Link to={`/goals/${d.goal?.id}?draft=${d.id}`}>{d.goal?.title} · 繼續編輯</Link></li>
                ))}
              </ul>
            </div>
          )}
          {data.recent_updates.length === 0 ? <Empty>你還沒有發布進度更新</Empty> :
            data.recent_updates.map((u) => <UpdateCard key={u.id} u={u} />)}
        </Card>
      </div>
    </div>
  )
}
