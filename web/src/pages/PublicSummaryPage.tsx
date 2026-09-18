import { useEffect, useRef, useState, type FormEvent } from 'react'
import { useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { api } from '../api'
import { useAuth } from '../auth'
import { AuthPageShell } from '../components/AuthPageShell'
import { MarkdownBody } from '../markdown'
import { showError } from '../util'

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
        <p className="muted">{t('common.loading')}</p>
      </AuthPageShell>
    )
  }

  const title = data?.display_title || data?.title

  return (
    <AuthPageShell>
      <article className="card public-summary-card stack">
        {failed && !data && <p className="err">{t('publicSummary.notFound')}</p>}
        {data?.pin_required && (
          <form className="stack" onSubmit={(e) => void unlock(e)}>
            <h1>{t('publicSummary.pinTitle')}</h1>
            <p className="muted">{t('publicSummary.pinHint')}</p>
            <label>
              PIN
              <input
                ref={pinRef}
                inputMode="numeric"
                pattern="[0-9]*"
                autoComplete="off"
                autoFocus
                required
                value={pin}
                onChange={(e) => setPin(e.target.value)}
              />
            </label>
            <button className="primary" type="submit" disabled={busy || !pin.trim()}>
              {t('publicSummary.unlock')}
            </button>
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
      </article>
    </AuthPageShell>
  )
}
