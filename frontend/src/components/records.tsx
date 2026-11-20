import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { LINK_TYPE } from '../labels'
import type { Blocker, LinkType, Outcome, Update, UserRef } from '../types'
import { daysAgo, fmtDate, fmtDateTime, useSubmit } from '../util'
import { CategoryBadge, Empty, ErrorBox, ExternalLinks, GoalLink, Multiline } from './ui'

// ---------------- progress update card ----------------
export function UpdateCard({ u, showGoal = true, onConvert }:
  { u: Update; showGoal?: boolean; onConvert?: (u: Update) => void }) {
  return (
    <article className="update" data-testid="update-card">
      <div className="meta">
        <strong>{u.author.name}</strong>
        <span>{u.publication_state === 'draft' ? `草稿 · ${fmtDateTime(u.updated_at)}` : fmtDateTime(u.published_at)}</span>
        {showGoal && u.goal && <span>目標：<GoalLink goal={u.goal} /></span>}
        {u.publication_state === 'draft' && <span className="badge draft">僅自己可見</span>}
      </div>
      {u.completed && <Field label="完成">{u.completed}</Field>}
      {u.findings && <Field label="發現 / 失敗嘗試">{u.findings}</Field>}
      {u.next_steps && (
        <Field label="下一步">
          {u.next_steps}
          {onConvert && <button className="link-btn" onClick={() => onConvert(u)}>轉成待辦</button>}
        </Field>
      )}
      {u.blockers.length > 0 && (
        <Field label="Blocker">
          {u.blockers.map((b) => <span key={b.id} className={`badge ${b.state === 'open' ? 'blocked' : ''}`}>#{b.id} {b.title}{b.state === 'resolved' ? '（已解決）' : ''}</span>)}
        </Field>
      )}
      {u.draft_blockers.length > 0 && (
        <Field label="待發布的 blocker">{u.draft_blockers.map((b) => b.title).join('、')}</Field>
      )}
      {u.no_blocker && u.blockers.length === 0 && <div className="muted small">無 blocker</div>}
      <ExternalLinks links={u.links} />
    </article>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="field">
      <span className="field-label">{label}</span>
      <div className="multiline">{children}</div>
    </div>
  )
}

// ---------------- blockers ----------------
export function BlockerList({ blockers, canResolve, onChanged, emptyText = '目前沒有未解決的 blocker' }:
  { blockers: Blocker[]; canResolve: (b: Blocker) => boolean; onChanged: () => void; emptyText?: string }) {
  if (!blockers.length) return <Empty>{emptyText}</Empty>
  return (
    <ul className="blocker-list">
      {blockers.map((b) => <BlockerRow key={b.id} b={b} canResolve={canResolve(b)} onChanged={onChanged} />)}
    </ul>
  )
}

function BlockerRow({ b, canResolve, onChanged }: { b: Blocker; canResolve: boolean; onChanged: () => void }) {
  const [resolving, setResolving] = useState(false)
  const [resolution, setResolution] = useState('')
  const { busy, error, run } = useSubmit()
  const save = (state: 'open' | 'resolved') => run(async () => {
    await api.patch(`/api/blockers/${b.id}`, { state, resolution })
    setResolving(false)
    onChanged()
  })
  return (
    <li className={`blocker ${b.state}`} data-testid="blocker-row">
      <div className="grow">
        <div><strong>#{b.id} {b.title}</strong> {b.state === 'resolved' && <span className="badge">已解決</span>}</div>
        <div className="meta">
          {b.goal && <span>目標：<GoalLink goal={b.goal} /></span>}
          <span>{b.reported_by.name} 提出 · {b.state === 'open' ? `${daysAgo(b.opened_at)}開啟` : `於 ${fmtDate(b.resolved_at)} 解決`}</span>
          {b.reference_count > 1 && <span>被 {b.reference_count} 筆更新引用</span>}
        </div>
        {b.description && <Multiline text={b.description} />}
        {b.resolution && <div className="note">解法：{b.resolution}</div>}
      </div>
      {canResolve && !resolving && (
        <div className="row-actions">
          {b.state === 'open'
            ? <button className="small" onClick={() => setResolving(true)}>標記解決</button>
            : <button className="small ghost" disabled={busy} onClick={() => save('open')}>重新開啟</button>}
        </div>
      )}
      {resolving && (
        <div className="inline-form full">
          <label>怎麼解決的？（可留白）
            <input value={resolution} onChange={(e) => setResolution(e.target.value)} />
          </label>
          <div className="buttons">
            <button disabled={busy} onClick={() => save('resolved')}>確認解決</button>
            <button className="ghost" onClick={() => setResolving(false)}>取消</button>
          </div>
        </div>
      )}
      <ErrorBox error={error} />
    </li>
  )
}

// ---------------- meeting outcomes ----------------
export function OutcomeCard({ o, isAdvisor, me, onChanged, showMeeting = false }:
  { o: Outcome; isAdvisor: boolean; me: UserRef; onChanged: () => void; showMeeting?: boolean }) {
  const [comment, setComment] = useState('')
  const [editing, setEditing] = useState(false)
  const [decision, setDecision] = useState(o.decision)
  const [rationale, setRationale] = useState(o.rationale)
  const [feedback, setFeedback] = useState(o.feedback)
  const { busy, error, run } = useSubmit()
  const pending = o.confirmation_state === 'pending'

  return (
    <article className={`outcome ${pending ? 'pending' : ''}`} data-testid="outcome-card">
      <div className="meta">
        {showMeeting && <><CategoryBadge category={o.meeting.category} /><Link to={`/meetings/${o.meeting.id}`}>{o.meeting.title}</Link><span>{fmtDate(o.meeting.occurred_at)}</span></>}
        <span>記錄：{o.author.name}</span>
        {pending
          ? <span className="badge pending">待指導者確認</span>
          : <span className="badge confirmed">已確認{o.confirmed_by && o.confirmed_by.id !== o.author.id ? `（${o.confirmed_by.name}）` : ''}</span>}
        {o.goal && <span>目標：<GoalLink goal={o.goal} /></span>}
      </div>
      {editing ? (
        <div className="inline-form">
          <label>決策<textarea value={decision} onChange={(e) => setDecision(e.target.value)} /></label>
          <label>理由<textarea value={rationale} onChange={(e) => setRationale(e.target.value)} /></label>
          <label>回饋<textarea value={feedback} onChange={(e) => setFeedback(e.target.value)} /></label>
          <div className="buttons">
            <button disabled={busy} onClick={() => run(async () => {
              await api.patch(`/api/outcomes/${o.id}`, { decision, rationale, feedback })
              setEditing(false)
              onChanged()
            })}>儲存</button>
            <button className="ghost" onClick={() => setEditing(false)}>取消</button>
          </div>
        </div>
      ) : (
        <>
          <div className="field"><span className="field-label">決策</span><div className="multiline decision">{o.decision}</div></div>
          {o.rationale && <div className="field"><span className="field-label">理由</span><div className="multiline">{o.rationale}</div></div>}
          {o.feedback && <div className="field"><span className="field-label">回饋</span><div className="multiline">{o.feedback}</div></div>}
        </>
      )}
      {o.comments.length > 0 && (
        <ul className="comments">
          {o.comments.map((c) => (
            <li key={c.id}><strong>{c.author.name}</strong>：{c.body} <span className="muted small">{fmtDateTime(c.created_at)}</span></li>
          ))}
        </ul>
      )}
      <div className="outcome-actions">
        {pending && isAdvisor && (
          <button className="small" disabled={busy} onClick={() => run(async () => {
            await api.post(`/api/outcomes/${o.id}/confirm`)
            onChanged()
          })}>確認此結論</button>
        )}
        {pending && o.author.id === me.id && !editing && <button className="small ghost" onClick={() => setEditing(true)}>編輯</button>}
        <form className="comment-form" onSubmit={(e) => {
          e.preventDefault()
          void run(async () => {
            await api.post(`/api/outcomes/${o.id}/comments`, { body: comment })
            setComment('')
            onChanged()
          })
        }}>
          <input value={comment} onChange={(e) => setComment(e.target.value)} placeholder="回覆 / 補充" aria-label="回覆" required />
          <button className="small" disabled={busy}>送出</button>
        </form>
      </div>
      <ErrorBox error={error} />
    </article>
  )
}

// ---------------- link editor used in forms ----------------
export interface LinkDraft { url: string; label: string; link_type: LinkType }

export function LinkEditor({ links, onChange }: { links: LinkDraft[]; onChange: (l: LinkDraft[]) => void }) {
  const set = (i: number, patch: Partial<LinkDraft>) => onChange(links.map((l, j) => (j === i ? { ...l, ...patch } : l)))
  return (
    <div className="link-editor">
      {links.map((l, i) => (
        <div className="form-row" key={i}>
          <input value={l.url} onChange={(e) => set(i, { url: e.target.value })} placeholder="https://…" aria-label="連結網址" />
          <input value={l.label} onChange={(e) => set(i, { label: e.target.value })} placeholder="說明（可選）" aria-label="連結說明" />
          <select value={l.link_type} onChange={(e) => set(i, { link_type: e.target.value as LinkType })} aria-label="連結類型">
            {Object.entries(LINK_TYPE).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
          <button type="button" className="ghost small" onClick={() => onChange(links.filter((_, j) => j !== i))}>移除</button>
        </div>
      ))}
      <button type="button" className="ghost small" onClick={() => onChange([...links, { url: '', label: '', link_type: 'general' }])}>
        + 附加連結（GitHub、實驗紀錄、文件…）
      </button>
    </div>
  )
}
