import { useEffect, useRef, useState, type FormEvent } from 'react'
import { useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { api } from '../api'
import { useAuth } from '../auth'
import { AuthPageShell } from '../components/AuthPageShell'
import { BackToLandingLink } from '../components/BackToLandingLink'
import { MarkdownBody } from '../markdown'
import { showError } from '../util'
import { AppSubmitButton } from '@/components/app/AdminUi'
import { Card, CardContent } from '@/components/ui/card'
import { AppInputField } from '../components/app/AppFormControls'
import { Link2Off } from 'lucide-react'

type PublicSummary = {
  pin_required: boolean
  title?: string | null
  display_title?: string
  body?: string
}

export function PublicSummaryPage() {
  const { token } = useParams<{ token: string }>()
  const { t } = useTranslation()
  const { ready, bootstrapDone } = useAuth()
  const [data, setData] = useState<PublicSummary | null>(null)
  const [pin, setPin] = useState('')
  const [busy, setBusy] = useState(false)
  const [failed, setFailed] = useState(false)
  const pinRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    const meta = document.createElement('meta')
    meta.name = 'robots'
    meta.content = 'noindex, nofollow'
    document.head.appendChild(meta)
    return () => {
      document.head.removeChild(meta)
    }
  }, [])

  async function load() {
    if (!token) return
    const next = await api<PublicSummary>(`/public/summary/${encodeURIComponent(token)}`)
    setData(next)
    setFailed(false)
  }

  useEffect(() => {
    if (!token || !ready || !bootstrapDone) return
    load().catch(() => setFailed(true))
  }, [token, ready, bootstrapDone])

  useEffect(() => {
    if (data?.pin_required) pinRef.current?.focus()
  }, [data?.pin_required])

  async function unlock(e: FormEvent) {
    e.preventDefault()
    if (!token) return
    setBusy(true)
    try {
      const next = await api<PublicSummary>(`/public/summary/${encodeURIComponent(token)}/unlock`, {
        method: 'POST',
        body: JSON.stringify({ pin }),
      })
      setData(next)
    } catch (err) {
      showError(err)
    } finally {
      setBusy(false)
    }
  }

  if (!ready || !bootstrapDone) {
    return (
      <AuthPageShell>
        <Card className="public-summary-card w-full max-w-sm">
          <CardContent className="py-8 text-center text-sm text-muted-foreground">
            {t('common.loading')}
          </CardContent>
        </Card>
      </AuthPageShell>
    )
  }

  if (failed && !data) {
    return (
      <AuthPageShell>
        <Card className="public-summary-not-found w-full max-w-sm shadow-sm" role="alert">
          <CardContent className="flex flex-col items-center gap-4 px-6 py-8 text-center">
            <span className="public-summary-not-found-icon" aria-hidden="true">
              <Link2Off className="size-6" strokeWidth={1.75} />
            </span>
            <p className="text-base font-medium leading-snug text-foreground">{t('publicSummary.notFound')}</p>
            <BackToLandingLink className="mt-1" />
          </CardContent>
        </Card>
      </AuthPageShell>
    )
  }

  const title = data?.display_title || data?.title

  return (
    <AuthPageShell>
      <Card className="public-summary-card w-full max-w-3xl">
        <CardContent className="flex flex-col gap-4 pt-6">
        {data?.pin_required && (
          <form className="flex flex-col gap-3" onSubmit={(e) => void unlock(e)}>
            <h1>{t('publicSummary.pinTitle')}</h1>
            <p className="muted">{t('publicSummary.pinHint')}</p>
            <AppInputField
              label="PIN"
              htmlFor="public-summary-pin"
              ref={pinRef}
              inputMode="numeric"
              pattern="[0-9]*"
              autoComplete="off"
              autoFocus
              required
              value={pin}
              onChange={(e) => setPin(e.target.value)}
            />
            <AppSubmitButton type="submit" ready={Boolean(pin.trim())} busy={busy}>
              {t('publicSummary.unlock')}
            </AppSubmitButton>
          </form>
        )}
        {data && !data.pin_required && (
          <>
            <h1>{title || t('summary.title')}</h1>
            <div className="summary-body">
              <MarkdownBody text={data.body || ''} />
            </div>
          </>
        )}
        </CardContent>
      </Card>
    </AuthPageShell>
  )
}
