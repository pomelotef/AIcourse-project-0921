import { useState } from 'react'
import { api } from '../api'
import type { Blocker, Update } from '../types'
import { useSubmit } from '../util'
import { LinkEditor, type LinkDraft } from './records'
import { ErrorBox } from './ui'

interface Props {
  goalId: number
  openBlockers: Blocker[]
  draft?: Update
  onSaved: (u: Update) => void
  onCancel: () => void
}

/** Progress update: completed / findings / blockers / next steps. Every field may stay empty. */
export function UpdateForm({ goalId, openBlockers, draft, onSaved, onCancel }: Props) {
  const [completed, setCompleted] = useState(draft?.completed ?? '')
  const [findings, setFindings] = useState(draft?.findings ?? '')
  const [nextSteps, setNextSteps] = useState(draft?.next_steps ?? '')
  const [noBlocker, setNoBlocker] = useState(draft?.no_blocker ?? false)
  const [refIds, setRefIds] = useState<number[]>(draft?.blockers.map((b) => b.id) ?? [])
  const [newBlockers, setNewBlockers] = useState(draft?.draft_blockers ?? [])
  const [links, setLinks] = useState<LinkDraft[]>(
    draft?.links.map((l) => ({ url: l.url, label: l.label, link_type: l.link_type })) ?? [])
  const { busy, error, run } = useSubmit()

  const save = (publish: boolean) => run(async () => {
    const body = {
      completed, findings, next_steps: nextSteps, no_blocker: noBlocker,
      referenced_blocker_ids: noBlocker ? [] : refIds,
      new_blockers: noBlocker ? [] : newBlockers.filter((b) => b.title.trim()),
      links: links.filter((l) => l.url.trim()),
      publish,
    }
    const u = draft
      ? await api.patch<Update>(`/api/updates/${draft.id}`, body)
      : await api.post<Update>(`/api/goals/${goalId}/updates`, body)
    onSaved(u)
  })

  return (
    <form className="update-form" onSubmit={(e) => { e.preventDefault(); void save(true) }} aria-label="進度更新">
      <label>這段時間完成了什麼
        <textarea value={completed} onChange={(e) => setCompleted(e.target.value)} rows={2} />
      </label>
      <label>新發現 / 失敗嘗試
        <textarea value={findings} onChange={(e) => setFindings(e.target.value)} rows={2}
          placeholder="例如：改了哪個參數、數據變化多少" />
      </label>

      <fieldset>
        <legend>目前困難（blocker）</legend>
        <label className="check-label">
          <input type="checkbox" checked={noBlocker} onChange={(e) => setNoBlocker(e.target.checked)} />
          目前沒有 blocker
        </label>
        {!noBlocker && (
          <>
            {openBlockers.length > 0 && (
              <div className="blocker-picks">
                <span className="muted small">仍卡在既有的 blocker？勾選以延續（同一個 blocker 會保留同一個編號）</span>
                {openBlockers.map((b) => (
                  <label key={b.id} className="check-label">
                    <input type="checkbox" checked={refIds.includes(b.id)}
                      onChange={(e) => setRefIds(e.target.checked ? [...refIds, b.id] : refIds.filter((x) => x !== b.id))} />
                    #{b.id} {b.title}
                  </label>
                ))}
              </div>
            )}
            {newBlockers.map((b, i) => (
              <div className="form-row" key={i}>
                <input value={b.title} placeholder="新的 blocker，例如：Vulkan backend 編譯失敗" aria-label="新 blocker"
                  onChange={(e) => setNewBlockers(newBlockers.map((x, j) => (j === i ? { ...x, title: e.target.value } : x)))} />
                <button type="button" className="ghost small" onClick={() => setNewBlockers(newBlockers.filter((_, j) => j !== i))}>移除</button>
              </div>
            ))}
            <button type="button" className="ghost small" onClick={() => setNewBlockers([...newBlockers, { title: '', description: '' }])}>
              + 新增 blocker
            </button>
          </>
        )}
      </fieldset>

      <label>下一步
        <textarea value={nextSteps} onChange={(e) => setNextSteps(e.target.value)} rows={2} />
      </label>
      <LinkEditor links={links} onChange={setLinks} />
      <p className="muted small">發布後專案成員都看得到；草稿只有你自己看得到。</p>
      <ErrorBox error={error} />
      <div className="buttons">
        <button type="submit" disabled={busy}>發布更新</button>
        <button type="button" className="secondary" disabled={busy} onClick={() => void save(false)}>存成草稿</button>
        <button type="button" className="ghost" onClick={onCancel}>取消</button>
      </div>
    </form>
  )
}
