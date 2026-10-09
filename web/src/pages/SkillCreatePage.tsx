import { useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { api } from '../api'
import { isOrgAdmin, useAuth } from '../auth'
import { AdminFormActions, AppSubmitButton } from '../components/app/AdminUi'
import { AppInputField, AppSelectField } from '../components/app/AppFormControls'
import { AppField } from '../components/app/AppField'
import { EntityBodyCard, EntityPage } from '../components/app/EntityUi'
import type { SchemaSkillPublicResponse } from '../openapi'
import { libraryPath } from '../routes'
import { showError } from '../util'
type SkillCreateKind = 'self' | 'org'

export function SkillCreatePage() {
  const { t } = useTranslation()
  const { me } = useAuth()
  const nav = useNavigate()
  const hasOrg = Boolean(me?.org)
  const admin = isOrgAdmin(me)
  const [name, setName] = useState('')
  const [body, setBody] = useState('')
  const [kind, setKind] = useState<SkillCreateKind>('self')
  const [busy, setBusy] = useState(false)

  if (!hasOrg) return <Navigate to="/app/profile" replace />

  const ready = Boolean(name.trim())

  const kindOptions: { value: SkillCreateKind; label: string }[] = [
    { value: 'self', label: t('skills.newSelf') },
    ...(admin ? [{ value: 'org' as const, label: t('skills.newOrg') }] : []),
  ]

  async function save() {
    if (!ready) return
    setBusy(true)
    try {
      const path = kind === 'self' ? '/skills/self' : '/org/skills'
      await api<SchemaSkillPublicResponse>(path, {
        method: 'POST',
        body: JSON.stringify({ name: name.trim(), body }),
      })
      nav(libraryPath('skills'))
    } catch (e) {
      showError(e)
    } finally {
      setBusy(false)
    }
  }

  return (
    <EntityPage backTo={libraryPath('skills')}>
      <EntityBodyCard title={t('skills.createTitle')}>
        <div className="flex flex-col gap-3">
          <AppInputField
            label={t('common.name')}
            htmlFor="skill-create-name"
            value={name}
            disabled={busy}
            onChange={(e) => setName(e.target.value)}
          />
          <AppField label={t('skills.body')} htmlFor="skill-create-body">
            <textarea
              id="skill-create-body"
              className="skill-editor min-h-[12rem] w-full rounded-lg border border-input bg-transparent px-2.5 py-2 text-sm"
              value={body}
              disabled={busy}
              onChange={(e) => setBody(e.target.value)}
            />
          </AppField>
          <div className="skill-create-actions">
            <AppSelectField
              className="w-full"
              label={t('skills.createKind')}
              htmlFor="skill-create-kind"
              value={kind}
              disabled={busy}
              options={kindOptions}
              onValueChange={(v) => setKind(v as SkillCreateKind)}
            />
            <AdminFormActions className="skill-create-submit">
              <AppSubmitButton ready={ready} busy={busy} onClick={() => void save()}>
                {t('common.save')}
              </AppSubmitButton>
            </AdminFormActions>
          </div>
        </div>
      </EntityBodyCard>
    </EntityPage>
  )
}
