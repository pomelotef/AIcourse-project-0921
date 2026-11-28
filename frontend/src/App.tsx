import { NavLink, Route, Routes } from 'react-router-dom'
import { AuthProvider, useAuth } from './auth'
import { NotificationBell } from './components/NotificationBell'
import { Loading } from './components/ui'
import { LiveIndicator, LiveProvider } from './live'
import GoalPage from './pages/GoalPage'
import Home from './pages/Home'
import Login from './pages/Login'
import MeetingPage from './pages/MeetingPage'
import Overview from './pages/Overview'
import ProjectPage from './pages/ProjectPage'
import Projects from './pages/Projects'

export default function App() {
  return (
    <AuthProvider>
      <Shell />
    </AuthProvider>
  )
}

function Shell() {
  const { user, ready, logout } = useAuth()
  if (!ready) return <main className="page"><Loading /></main>
  if (!user) return <Login />
  return (
    <LiveProvider>
      <header className="topbar">
        <div className="topbar-inner">
          <NavLink to="/" className="brand">LabPulse</NavLink>
          <nav>
            <NavLink to="/" end>我的研究</NavLink>
            <NavLink to="/overview">總覽</NavLink>
            <NavLink to="/projects">專案</NavLink>
          </nav>
          <div className="user">
            <LiveIndicator />
            <NotificationBell />
            <span className="muted">{user.name}</span>
            <button className="ghost small" onClick={() => void logout()}>登出</button>
          </div>
        </div>
      </header>
      <main className="page">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/overview" element={<Overview />} />
          <Route path="/projects" element={<Projects />} />
          <Route path="/projects/:id" element={<ProjectPage />} />
          <Route path="/goals/:id" element={<GoalPage />} />
          <Route path="/meetings/:id" element={<MeetingPage />} />
          <Route path="*" element={<p>找不到此頁面</p>} />
        </Routes>
      </main>
    </LiveProvider>
  )
}
