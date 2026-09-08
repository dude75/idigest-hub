import type { ReactNode } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useAuth } from './auth'
import { Shell } from './components/Shell'
import { AudioPage } from './pages/AudioPage'
import { ChangePasswordPage } from './pages/ChangePasswordPage'
import { ForgotPage } from './pages/ForgotPage'
import { InstancePage } from './pages/InstancePage'
import { LibraryPage } from './pages/LibraryPage'
import { LandingPage } from './pages/LandingPage'
import { LoginPage } from './pages/LoginPage'
import { OrgPage } from './pages/OrgPage'
import { ProfilePage } from './pages/ProfilePage'
import { ResetPage } from './pages/ResetPage'
import { SetupPage } from './pages/SetupPage'
import { SignupPage } from './pages/SignupPage'
import { SkillPage } from './pages/SkillPage'
import { SkillsPage } from './pages/SkillsPage'
import { StatsPage } from './pages/StatsPage'
import { SummaryPage } from './pages/SummaryPage'
import { TaskPage } from './pages/TaskPage'
import { TasksPage } from './pages/TasksPage'
import { TranscriptPage } from './pages/TranscriptPage'

function Gate({ children }: { children: ReactNode }) {
  const { ready, bootstrapDone, me } = useAuth()
  const { t } = useTranslation()
  if (!ready) return <p className="page muted">{t('common.loading')}</p>
  if (!bootstrapDone) return <Navigate to="/setup" replace />
  if (!me) return <Navigate to="/login" replace />
  if (me.must_change_password) return <Navigate to="/change-password" replace />
  return children
}

export default function App() {
  return (
    <Routes>
      <Route path="/setup" element={<SetupPage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/signup" element={<SignupPage />} />
      <Route path="/forgot" element={<ForgotPage />} />
      <Route path="/reset" element={<ResetPage />} />
      <Route path="/change-password" element={<ChangePasswordPage />} />
      <Route
        path="/app"
        element={
          <Gate>
            <Shell />
          </Gate>
        }
      >
        <Route index element={<LibraryPage />} />
        <Route path="audio/:id" element={<AudioPage />} />
        <Route path="transcript/:id" element={<TranscriptPage />} />
        <Route path="summary/:id" element={<SummaryPage />} />
        <Route path="skills" element={<SkillsPage />} />
        <Route path="skill/:id" element={<SkillPage />} />
        <Route path="org" element={<OrgPage />} />
        <Route path="stats" element={<StatsPage />} />
        <Route path="profile" element={<ProfilePage />} />
        <Route path="instance" element={<InstancePage />} />
        <Route path="tasks" element={<TasksPage />} />
        <Route path="task/:id" element={<TaskPage />} />
      </Route>
      <Route path="/" element={<LandingPage />} />
      <Route path="*" element={<LandingPage />} />
    </Routes>
  )
}
