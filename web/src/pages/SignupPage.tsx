import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { Link, Navigate, useNavigate, useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { api } from '../api'
import { useAuth } from '../auth'
import { AuthPageShell } from '../components/AuthPageShell'
import { LegalDocumentAcceptance } from '../components/LegalDocumentAcceptance'
import { type LegalDocumentKey, type PublicLegalDocument } from '../legalDocuments'
import { resolveAuthContinuationPath } from '../routes'
import type { Tariff } from '../types'
import { showError } from '../util'

export function SignupPage() {
  const { t, i18n } = useTranslation()
  const { ready, bootstrapDone, me, refresh } = useAuth()
  const nav = useNavigate()
  const [search] = useSearchParams()
  const wanted = search.get('tariff') || ''
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [tariffId, setTariffId] = useState('')
  const [tariffs, setTariffs] = useState<Tariff[]>([])
  const [legalDocs, setLegalDocs] = useState<PublicLegalDocument[]>([])
  const [legalDocsLoading, setLegalDocsLoading] = useState(true)
  const [checked, setChecked] = useState<Partial<Record<LegalDocumentKey, boolean>>>({})
  const [tariffsLoading, setTariffsLoading] = useState(true)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    setTariffsLoading(true)
    api<{ items: Tariff[] }>('/auth/signup-tariffs')
      .then((r) => {
        setTariffs(r.items)
        const match = r.items.find((item) => item.id === wanted)
        setTariffId((match || r.items[0])?.id || '')
      })
      .catch(showError)
      .finally(() => setTariffsLoading(false))
  }, [wanted])

  useEffect(() => {
    setLegalDocsLoading(true)
    api<{ items: PublicLegalDocument[] }>('/public/legal-documents')
      .then((r) => setLegalDocs(r.items))
      .catch(showError)
      .finally(() => setLegalDocsLoading(false))
  }, [i18n.language])

  const allLegalChecked = useMemo(
    () => legalDocs.length === 0 || legalDocs.every((doc) => checked[doc.key]),
    [checked, legalDocs],
  )

  if (ready && !bootstrapDone) return <Navigate to="/setup" replace />
  if (ready && me) return <Navigate to={resolveAuthContinuationPath(me)} replace />

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    if (!allLegalChecked) return
    setBusy(true)
    try {
      await api('/auth/signup', {
        method: 'POST',
        body: JSON.stringify({
          email,
          password,
          tariff_id: tariffId,
          locale: i18n.language,
          accept_legal_documents: legalDocs.length > 0,
        }),
      })
      const next = await refresh()
      nav(resolveAuthContinuationPath(next), { replace: true })
    } catch (e) {
      showError(e)
    } finally {
      setBusy(false)
    }
  }

  const formLoading = tariffsLoading || legalDocsLoading

  return (
    <AuthPageShell>
      <form className="card auth-card stack" onSubmit={(e) => void onSubmit(e)}>
        <h1>{t('auth.signup')}</h1>
        {formLoading ? (
          <p className="muted">{t('common.loading')}</p>
        ) : tariffs.length === 0 ? (
          <p className="muted">{t('auth.noSignup')}</p>
        ) : (
          <>
            <label>
              {t('common.email')}
              <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
            </label>
            <label>
              {t('common.password')}
              <input type="password" required minLength={8} value={password} onChange={(e) => setPassword(e.target.value)} />
            </label>
            <label>
              {t('auth.tariff')}
              <select value={tariffId} onChange={(e) => setTariffId(e.target.value)}>
                {tariffs.map((tr) => (
                  <option key={tr.id} value={tr.id}>
                    {tr.name}{tr.unlimited ? ` (${t('wallet.unlimited')})` : ''}
                  </option>
                ))}
              </select>
            </label>
            {legalDocs.length > 0 && (
              <LegalDocumentAcceptance
                documents={legalDocs}
                checked={checked}
                disabled={busy}
                onCheckedChange={(key, value) => setChecked((prev) => ({ ...prev, [key]: value }))}
              />
            )}
            <button className="primary" disabled={busy || !allLegalChecked} type="submit">
              {t('auth.signup')}
            </button>
          </>
        )}
        <Link to="/login">{t('auth.toLogin')}</Link>
      </form>
    </AuthPageShell>
  )
}
