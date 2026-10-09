import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { api, apiDownload } from '../api'
import { isInstanceAdmin, useAuth } from '../auth'
import { InlineRename } from '../components/InlineRename'
import { EntityToolbar } from '../components/EntityToolbar'
import { ShareDialog } from '../components/ShareDialog'
import { MarkdownBody } from '../markdown'
import type { SchemaSkillListResponse, SchemaSkillPublicResponse } from '../openapi'
import { libraryPath } from '../routes'
import { fmtDate, showError } from '../util'
import { Button } from '@/components/ui/button'
import { AppInputField } from '../components/app/AppFormControls'
import { AppField } from '../components/app/AppField'
import { AdminFormActions, AppSubmitButton, HubBadge } from '../components/app/AdminUi'
import {
  EntityBodyCard,
  EntityDetailCard,
  EntityPage,
} from '../components/app/EntityUi'

function skillPath(skill: SchemaSkillPublicResponse): string {
  if (skill.scope === 'base') return `/skills/base/${skill.id}`
  if (skill.scope === 'org') return `/org/skills/${skill.id}`
  return `/skills/self/${skill.id}`
}

export function SkillPage() {
  const { id } = useParams<{ id: string }>()
  const { t } = useTranslation()
  const { me } = useAuth()
  const nav = useNavigate()
  const [item, setItem] = useState<SchemaSkillPublicResponse | null>(null)
  const [name, setName] = useState('')
  const [draft, setDraft] = useState('')
  const [editing, setEditing] = useState(false)
  const [loadFailed, setLoadFailed] = useState(false)
  const [share, setShare] = useState(false)
  const [busy, setBusy] = useState(false)
  const instance = isInstanceAdmin(me)
  const hasOrg = Boolean(me?.org)
  const backTo = hasOrg ? libraryPath('skills') : '/app/instance?tab=baseSkills'
  const canEdit = Boolean(item && (item.scope === 'base' ? instance : !item.readonly))
  const canCopy = hasOrg
  const mine = item?.scope === 'self' && item.owner_user_id === me?.user.id

  const skillEditReady = useMemo(() => {
    if (!item) return false
    const nextName = name.trim()
    if (!nextName) return false
    return nextName !== item.name || draft !== (item.body || '')
  }, [item, name, draft])

  async function load() {
    if (!id) return
    const path = hasOrg ? '/skills' : '/skills/base'
    const catalog = await api<SchemaSkillListResponse>(path)
    const next = (catalog.items ?? []).find((s) => s.id === id)
    if (!next) {
      setItem(null)
      throw new Error(t('errors.not_found'))
    }
    setItem(next)
    setName(next.name)
    setDraft(next.body || '')
  }

  useEffect(() => {
    setEditing(false)
    load()
      .then(() => setLoadFailed(false))
      .catch((e) => {
        setLoadFailed(true)
        showError(e)
      })
  }, [id, hasOrg])

  async function save() {
    if (!item) return
    setBusy(true)
    try {
      const next = await api<SchemaSkillPublicResponse>(skillPath(item), {
        method: 'PATCH',
        body: JSON.stringify({ name, body: draft }),
      })
      setItem({ ...item, ...next })
      setName(next.name)
      setDraft(next.body || '')
      setEditing(false)
    } catch (e) {
      showError(e)
    } finally {
      setBusy(false)
    }
  }

  async function remove() {
    if (!item) return
    await api(skillPath(item), { method: 'DELETE' })
    nav(backTo)
  }

  async function copy() {
    if (!item) return
    const next = await api<SchemaSkillPublicResponse>(`/skills/${item.id}/copy`, { method: 'POST' })
    nav(`/app/skill/${next.id}`)
  }

  async function renameSkill(nextName: string) {
    if (!item) return
    setBusy(true)
    try {
      const next = await api<SchemaSkillPublicResponse>(skillPath(item), {
        method: 'PATCH',
        body: JSON.stringify({ name: nextName, body: item.body }),
      })
      setItem({ ...item, ...next })
      setName(next.name)
    } catch (e) {
      showError(e)
      throw e
    } finally {
      setBusy(false)
    }
  }

  if (!item && !loadFailed) return <p className="muted">{t('common.loading')}</p>

  return (
    <EntityPage backTo={backTo}>
      {item ? (
        <InlineRename
          value={item.name}
          canEdit={mine}
          busy={busy}
          onSave={renameSkill}
        />
      ) : null}
      {item && (
        <>
          <EntityDetailCard>
          <div className="flex flex-wrap items-center gap-2">
            <HubBadge tone="muted">{item.catalog || item.scope}</HubBadge>
            <span className="muted">{fmtDate(item.created_at)}</span>
          </div>
          <EntityToolbar>
            <Button
              type="button"
              variant="outline"
              onClick={() => void apiDownload(`/skills/${item.id}/export`, `${item.name}.md`).catch(showError)}
            >
              {t('common.downloadMd')}
            </Button>
            {mine && (
              <Button type="button" variant="outline" onClick={() => setShare(true)}>
                {t('common.share')}
              </Button>
            )}
            {canEdit && !editing && (
              <Button
                type="button"
                variant="outline"
                onClick={() => {
                  setName(item.name)
                  setDraft(item.body || '')
                  setEditing(true)
                }}
              >
                {t('common.edit')}
              </Button>
            )}
            {canEdit && (
              <Button type="button" variant="destructive" onClick={() => void remove()}>{t('common.delete')}</Button>
            )}
            {canCopy ? (
              <Button type="button" variant="outline" onClick={() => void copy()}>
                {t('common.copy')}
              </Button>
            ) : null}
          </EntityToolbar>
          </EntityDetailCard>
          <EntityBodyCard title={t('skills.body')}>
          {editing ? (
            <div className="flex flex-col gap-3">
              <AppInputField label={t('common.name')} htmlFor="skill-edit-name" value={name} onChange={(e) => setName(e.target.value)} />
              <AppField label={t('skills.body')} htmlFor="skill-edit-body">
                <textarea id="skill-edit-body" className="skill-editor min-h-[12rem] w-full rounded-lg border border-input bg-transparent px-2.5 py-2 text-sm" value={draft} onChange={(e) => setDraft(e.target.value)} />
              </AppField>
              <AdminFormActions>
                <AppSubmitButton ready={skillEditReady} busy={busy} onClick={() => void save()}>
                  {t('common.save')}
                </AppSubmitButton>
                <Button type="button" variant="outline" disabled={busy} onClick={() => { setName(item.name); setDraft(item.body || ''); setEditing(false) }}>
                  {t('common.cancel')}
                </Button>
              </AdminFormActions>
            </div>
          ) : (
            <div className="summary-body">
              <MarkdownBody text={item.body || ''} />
            </div>
          )}
          </EntityBodyCard>
        </>
      )}
      {share && id && <ShareDialog objectType="skill" objectId={id} onClose={() => { setShare(false); void load() }} />}
    </EntityPage>
  )
}
