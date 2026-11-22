import { useState } from 'react'
import { api } from '../api'
import { useAuth } from '../auth'
import { ErrorBox } from '../components/ui'
import type { Me } from '../types'
import { useSubmit } from '../util'

export default function Login() {
  const { setUser } = useAuth()
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [email, setEmail] = useState('')
  const [name, setName] = useState('')
  const [password, setPassword] = useState('')
  const { busy, error, run, setError } = useSubmit()

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    void run(async () => {
      const me = mode === 'login'
        ? await api.post<Me>('/api/auth/login', { email, password })
        : await api.post<Me>('/api/auth/register', { email, name, password })
      setUser(me)
    })
  }

  return (
    <main className="auth-page">
      <div className="auth-box">
        <h1>LabPulse</h1>
        <p className="muted">研究進度與 meeting 脈絡的共享紀錄</p>
        <form onSubmit={submit}>
          {mode === 'register' && (
            <label>名字<input value={name} onChange={(e) => setName(e.target.value)} required maxLength={100} /></label>
          )}
          <label>Email<input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoComplete="username" /></label>
          <label>密碼
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required
              minLength={mode === 'register' ? 8 : 1} autoComplete={mode === 'login' ? 'current-password' : 'new-password'} />
          </label>
          <ErrorBox error={error} />
          <button type="submit" disabled={busy}>{mode === 'login' ? '登入' : '建立帳號'}</button>
        </form>
        <button className="link-btn" onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setError(null) }}>
          {mode === 'login' ? '還沒有帳號？註冊' : '已有帳號？登入'}
        </button>
      </div>
    </main>
  )
}
