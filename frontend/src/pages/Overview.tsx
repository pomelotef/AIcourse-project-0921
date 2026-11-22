import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { UpdateCard } from '../components/records'
import { Card, Empty, ErrorBox, GoalStateBadge, Loading } from '../components/ui'
import { CATEGORY } from '../labels'
import type { Action, Blocker, GoalState, MeetingCategory, Update, UserRef } from '../types'
import { daysAgo, fmtDate, useAsync } from '../util'

interface Attention { kind: string; text: string; member?: UserRef; meeting_id?: number; goal_id?: number }
interface ProjectRow {
  id: number
  title: string
  state: string
  members: (UserRef & { role: string })[]
  goal_count: number
  last_update_at: string | null
  recent_updates: Update[]
  open_blockers: Blocker[]
  open_action_count: number
  overdue_action_count: number
  pending_outcome_count: number
  latest_meetings: { id: number; title: string; occurred_at: string; category_label: string }[]
}
interface MemberRow {
  id: number
  name: string
  projects: { id: number; title: string }[]
  goals: { id: number; title: string; research_state: GoalState }[]
  last_update_at: string | null
  freshness: 'fresh' | 'stale' | 'no_record'
  latest_update: Update | null
  open_blockers: Blocker[]
  open_action_count: number
  overdue_actions: Action[]
}
interface OverviewData {
  rules: { stale_days: number; description: string }
  attention: Attention[]
  by_project: ProjectRow[]
  by_member: MemberRow[]
}

const FRESHNESS = { fresh: '近期有更新', stale: '資訊可能過期', no_record: '尚無紀錄' }

export default function Overview() {
  const [view, setView] = useState<'project' | 'member'>('project')
  const [staleDays, setStaleDays] = useState(14)
  const [category, setCategory] = useState<MeetingCategory | ''>('')
  const qs = `stale_days=${staleDays}${category ? `&category=${category}` : ''}`
  const { data, error, loading, reload } = useAsync(() => api.get<OverviewData>(`/api/me/overview?${qs}`), [qs])

  if (loading && !data) return <Loading />
  if (!data) return <ErrorBox error={error} onRetry={reload} />
  if (data.by_project.length === 0) {
    return (
      <div className="stack">
        <h1>實驗室總覽</h1>
        <Card><Empty>總覽列出你擔任指導者的專案。你目前沒有擔任指導者的專案，可以到「我的研究」查看自己的進度。</Empty></Card>
      </div>
    )
  }

  return (
    <div className="stack">
      <div className="page-head">
        <h1>實驗室總覽</h1>
        <div className="segmented" role="tablist">
          <button role="tab" aria-selected={view === 'project'} className={view === 'project' ? 'active' : ''} onClick={() => setView('project')}>依專案</button>
          <button role="tab" aria-selected={view === 'member'} className={view === 'member' ? 'active' : ''} onClick={() => setView('member')}>依成員</button>
        </div>
      </div>
      <ErrorBox error={error} onRetry={reload} />

      <Card title="需要關注" className="attention" actions={
        <label className="inline small">更新週期
          <select value={staleDays} onChange={(e) => setStaleDays(Number(e.target.value))}>
            {[7, 14, 21, 30].map((d) => <option key={d} value={d}>{d} 天</option>)}
          </select>
        </label>
      }>
        <p className="muted small">{data.rules.description} 只根據已填寫的資料，不代表研究沒有進展，也不做排名。</p>
        {data.attention.length === 0 ? <Empty>目前沒有需要關注的項目</Empty> : (
          <ul className="plain attention-list">
            {data.attention.map((a, i) => (
              <li key={i} className={`att-${a.kind}`}>
                {a.meeting_id ? <Link to={`/meetings/${a.meeting_id}`}>{a.text}</Link>
                  : a.goal_id ? <Link to={`/goals/${a.goal_id}`}>{a.text}</Link> : a.text}
              </li>
            ))}
          </ul>
        )}
      </Card>

      {view === 'project' ? (
        <>
          <div className="filters">
            <select value={category} onChange={(e) => setCategory(e.target.value as MeetingCategory | '')} aria-label="Meeting 分類">
              <option value="">全部 Meeting 分類</option>
              {Object.entries(CATEGORY).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </div>
          {data.by_project.map((p) => (
            <Card key={p.id} title={<Link to={`/projects/${p.id}`}>{p.title}</Link>}>
              <div className="stats">
                <Stat label="成員" value={p.members.filter((m) => m.role === 'student').map((m) => m.name).join('、') || '—'} />
                <Stat label="最近更新" value={p.last_update_at ? `${fmtDate(p.last_update_at)}（${daysAgo(p.last_update_at)}）` : '尚無'} />
                <Stat label="未解決 blocker" value={String(p.open_blockers.length)} warn={p.open_blockers.length > 0} />
                <Stat label="未完成待辦" value={`${p.open_action_count}${p.overdue_action_count ? `（${p.overdue_action_count} 項過期）` : ''}`} warn={p.overdue_action_count > 0} />
                <Stat label="待確認結論" value={String(p.pending_outcome_count)} warn={p.pending_outcome_count > 0} />
              </div>
              {p.latest_meetings.length > 0 && (
                <div className="meta">最近 meeting：{p.latest_meetings.map((m) => (
                  <Link key={m.id} to={`/meetings/${m.id}`}>{m.category_label} {fmtDate(m.occurred_at)}</Link>
                ))}</div>
              )}
              {p.open_blockers.length > 0 && (
                <ul className="plain">
                  {p.open_blockers.map((b) => (
                    <li key={b.id}><span className="badge blocked">blocker</span> {b.title}
                      <span className="muted small"> · {b.reported_by.name} · {b.goal && <Link to={`/goals/${b.goal.id}`}>{b.goal.title}</Link>}</span></li>
                  ))}
                </ul>
              )}
              {p.recent_updates.length > 0 && (
                <details>
                  <summary>最近 {p.recent_updates.length} 筆進度</summary>
                  {p.recent_updates.map((u) => <UpdateCard key={u.id} u={u} />)}
                </details>
              )}
            </Card>
          ))}
        </>
      ) : (
        <div className="grid-2">
          {data.by_member.length === 0 && <Card><Empty>你的專案目前沒有學生成員</Empty></Card>}
          {data.by_member.map((m) => (
            <Card key={m.id} title={m.name} actions={<span className={`badge fresh-${m.freshness}`}>{FRESHNESS[m.freshness]}</span>}>
              <div className="meta">
                {m.projects.map((p) => <Link key={p.id} to={`/projects/${p.id}`}>{p.title}</Link>)}
                <span>最近更新：{daysAgo(m.last_update_at)}</span>
              </div>
              {m.goals.length > 0 && (
                <ul className="plain">
                  {m.goals.map((g) => <li key={g.id}><Link to={`/goals/${g.id}`}>{g.title}</Link> <GoalStateBadge state={g.research_state} /></li>)}
                </ul>
              )}
              {m.latest_update && <UpdateCard u={m.latest_update} />}
              {m.open_blockers.length > 0 && (
                <div className="small">未解決 blocker：{m.open_blockers.map((b) => b.title).join('、')}</div>
              )}
              <div className="small muted">未完成待辦 {m.open_action_count} 項{m.overdue_actions.length ? `，其中 ${m.overdue_actions.length} 項已過期` : ''}</div>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}

function Stat({ label, value, warn }: { label: string; value: string; warn?: boolean }) {
  return (
    <div className={`stat ${warn ? 'warn' : ''}`}>
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
    </div>
  )
}
