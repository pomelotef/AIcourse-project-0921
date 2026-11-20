import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api'
import { Card, Empty, ErrorBox, Loading } from '../components/ui'
import { ROLE } from '../labels'
import type { Project, Role } from '../types'
import { useAsync, useSubmit } from '../util'

export default function Projects() {
  const { data, error, loading, reload } = useAsync(() => api.get<Project[]>('/api/projects'), [])
  const [creating, setCreating] = useState(false)

  return (
    <div className="stack">
      <div className="page-head">
        <h1>專案</h1>
        {!creating && <button onClick={() => setCreating(true)}>建立專案</button>}
      </div>
      {creating && <NewProject onCancel={() => setCreating(false)} />}
      <ErrorBox error={error} onRetry={reload} />
      {loading && !data ? <Loading /> : !data?.length ? <Card><Empty>還沒有專案</Empty></Card> : (
        <div className="grid-2">
          {data.map((p) => (
            <Card key={p.id} title={<Link to={`/projects/${p.id}`}>{p.title}</Link>}>
              {p.description && <p className="muted">{p.description}</p>}
              <div className="meta">
                <span>我的角色：{ROLE[p.my_role]}</span>
                <span>{p.members.map((m) => m.name).join('、')}</span>
                {p.state === 'archived' && <span className="badge">已封存</span>}
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}

function NewProject({ onCancel }: { onCancel: () => void }) {
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [role, setRole] = useState<Role>('advisor')
  const { busy, error, run } = useSubmit()
  const navigate = useNavigate()
  return (
    <Card title="建立研究專案">
      <form className="inline-form" onSubmit={(e) => {
        e.preventDefault()
        void run(async () => {
          const p = await api.post<Project>('/api/projects', { title, description, creator_role: role })
          navigate(`/projects/${p.id}`)
        })
      }}>
        <label>專案名稱<input value={title} onChange={(e) => setTitle(e.target.value)} required maxLength={200} /></label>
        <label>說明<textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={2} /></label>
        <label>我在此專案的角色
          <select value={role} onChange={(e) => setRole(e.target.value as Role)}>
            <option value="advisor">指導者（可加入成員、指派目標）</option>
            <option value="student">學生（先自己記錄，之後再邀請指導者）</option>
          </select>
        </label>
        <ErrorBox error={error} />
        <div className="buttons">
          <button type="submit" disabled={busy}>建立</button>
          <button type="button" className="ghost" onClick={onCancel}>取消</button>
        </div>
      </form>
    </Card>
  )
}
