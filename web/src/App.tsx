import { lazy, Suspense, type ReactNode } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useAuth } from './auth'
import { Shell } from './components/Shell'
import { AudioPage } from './pages/AudioPage'
import { ChangePasswordPage } from './pages/ChangePasswordPage'
import { Enroll2faPage } from './pages/Enroll2faPage'
import { Verify2faPage } from './pages/Verify2faPage'
import { ForgotPage } from './pages/ForgotPage'
import { LibraryPage } from './pages/LibraryPage'
import { LandingPage } from './pages/LandingPage'
import { LoginPage } from './pages/LoginPage'
import { SsoLoginPage } from './pages/SsoLoginPage'
import { OrgPage } from './pages/OrgPage'
import { PublicLinksPage } from './pages/PublicLinksPage'
import { ProfilePage } from './pages/ProfilePage'
import { PublicSummaryPage } from './pages/PublicSummaryPage'
import { ResetPage } from './pages/ResetPage'
import { SetupPage } from './pages/SetupPage'
import { SignupPage } from './pages/SignupPage'
import { SkillPage } from './pages/SkillPage'
import { SkillsPage } from './pages/SkillsPage'
import { SecurityPage } from './pages/security/SecurityPage'
import { StatsPage } from './pages/StatsPage'
import { SummaryPage } from './pages/SummaryPage'
import { TaskPage } from './pages/TaskPage'
import { TasksPage } from './pages/TasksPage'
import { TranscriptPage } from './pages/TranscriptPage'
import { resolveAuthBlockPath, resolveHomePath, LIBRARY_DEFAULT } from './routes'

const InstancePage = lazy(() =>
  import('./pages/instance/InstancePage').then((m) => ({ default: m.InstancePage })),
)

function LazyInstancePage() {
  const { t } = useTranslation()
  return (
    <Suspense fallback={<p className="page muted">{t('common.loading')}</p>}>
      <InstancePage />
    </Suspense>
  )
}

function AppHomeRedirect() {
  const { me } = useAuth()
  return <Navigate to={resolveHomePath(me)} replace />
}

function Gate({ children }: { children: ReactNode }) {
  const { ready, bootstrapDone, me } = useAuth()
  const { t } = useTranslation()
  if (!ready) return <p className="page muted">{t('common.loading')}</p>
  if (!bootstrapDone) return <Navigate to="/setup" replace />
  if (!me) return <Navigate to="/login" replace />
  const block = resolveAuthBlockPath(me)
  if (block === '/change-password') return <Navigate to="/change-password" replace />
  if (block === '/enroll-2fa') return <Navigate to="/enroll-2fa" replace />
  return children
}

export default function App() {
  return (
    <Routes>
      <Route path="/setup" element={<SetupPage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/sso/:orgId" element={<SsoLoginPage />} />
      <Route path="/signup" element={<SignupPage />} />
      <Route path="/forgot" element={<ForgotPage />} />
      <Route path="/reset" element={<ResetPage />} />
      <Route path="/public/summary/:token" element={<PublicSummaryPage />} />
      <Route path="/change-password" element={<ChangePasswordPage />} />
      <Route path="/verify-2fa" element={<Verify2faPage />} />
      <Route path="/enroll-2fa" element={<Enroll2faPage />} />
      <Route
        path="/app"
        element={
          <Gate>
            <Shell />
          </Gate>
        }
      >
        <Route index element={<AppHomeRedirect />} />
        <Route path="library" element={<Navigate to={LIBRARY_DEFAULT} replace />} />
        <Route path="library/:tab" element={<LibraryPage />} />
        <Route path="audio/:id" element={<AudioPage />} />
        <Route path="transcript/:id" element={<TranscriptPage />} />
        <Route path="summary/:id" element={<SummaryPage />} />
        <Route path="skills" element={<SkillsPage />} />
        <Route path="skill/:id" element={<SkillPage />} />
        <Route path="org" element={<OrgPage />} />
        <Route path="public-links" element={<PublicLinksPage />} />
        <Route path="stats" element={<StatsPage />} />
        <Route path="profile" element={<ProfilePage />} />
        <Route path="instance" element={<LazyInstancePage />} />
        <Route path="security" element={<SecurityPage />} />
        <Route path="audit" element={<Navigate to="/app/security" replace />} />
        <Route path="tasks" element={<TasksPage />} />
        <Route path="task/:id" element={<TaskPage />} />
      </Route>
      <Route path="/" element={<LandingPage />} />
      <Route path="*" element={<LandingPage />} />
    </Routes>
  )
}
