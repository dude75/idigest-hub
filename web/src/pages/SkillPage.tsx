import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { api, apiDownload } from '../api'
import { isInstanceAdmin, useAuth } from '../auth'
import { InlineRename } from '../components/InlineRename'
import { ShareDialog } from '../components/ShareDialog'
import { MarkdownBody } from '../markdown'
import type { Skill } from '../types'
import { fmtDate, showError } from '../util'

function skillPath(skill: Skill): string {
  if (skill.scope === 'base') return `/skills/base/${skill.id}`
  if (skill.scope === 'org') return `/org/skills/${skill.id}`
  return `/skills/self/${skill.id}`
}

export function SkillPage() {
  const { id } = useParams<{ id: string }>()
  const { t } = useTranslation()
  const { me } = useAuth()
  const nav = useNavigate()
  const [item, setItem] = useState<Skill | null>(null)
  const [name, setName] = useState('')
  const [draft, setDraft] = useState('')
  const [editing, setEditing] = useState(false)
  const [loadFailed, setLoadFailed] = useState(false)
  const [share, setShare] = useState(false)
  const [busy, setBusy] = useState(false)
  const instance = isInstanceAdmin(me)
  const hasOrg = Boolean(me?.org)
  const backTo = hasOrg ? '/app/skills' : '/app/instance?tab=baseSkills'
  const canEdit = Boolean(item && (item.scope === 'base' ? instance : !item.readonly))
  const canCopy = hasOrg
  const mine = item?.scope === 'self' && item.owner_user_id === me?.user.id

  async function load() {
    if (!id) return
    const path = hasOrg ? '/skills' : '/skills/base'
    const catalog = await api<{ items: Skill[] }>(path)
    const next = catalog.items.find((s) => s.id === id)
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
      const next = await api<Skill>(skillPath(item), {
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
    const next = await api<Skill>(`/skills/${item.id}/copy`, { method: 'POST' })
    nav(`/app/skill/${next.id}`)
  }

  async function renameSkill(nextName: string) {
    if (!item) return
    setBusy(true)
    try {
      const next = await api<Skill>(skillPath(item), {
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
    <div>
      <Link to={backTo}>{t('common.back')}</Link>
      {item ? (
        <InlineRename
          value={item.name}
          canEdit={mine}
          busy={busy}
          onSave={renameSkill}
        />
      ) : (
        <h1>{t('skills.title')}</h1>
      )}
      {item && (
        <>
          <div className="row">
            <span className="badge">{item.catalog || item.scope}</span>
            <span className="muted">{fmtDate(item.created_at)}</span>
          </div>
          <div className="row" style={{ margin: '8px 0' }}>
            <button
              type="button"
              onClick={() => void apiDownload(`/skills/${item.id}/export`, `${item.name}.md`).catch(showError)}
            >
              {t('common.downloadMd')}
            </button>
            {mine && <button type="button" onClick={() => setShare(true)}>{t('common.share')}</button>}
            {canEdit && !editing && (
              <button type="button" onClick={() => { setName(item.name); setDraft(item.body || ''); setEditing(true) }}>
                {t('common.edit')}
              </button>
            )}
            {canEdit && (
              <button type="button" className="danger" onClick={() => void remove()}>{t('common.delete')}</button>
            )}
            {canCopy && <button type="button" onClick={() => void copy()}>{t('common.copy')}</button>}
          </div>
          <h2>{t('skills.body')}</h2>
          {editing ? (
            <div className="stack">
              <label>
                {t('common.name')}
                <input value={name} onChange={(e) => setName(e.target.value)} />
              </label>
              <textarea
                className="skill-editor"
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
              />
              <div className="row">
                <button className="primary" type="button" disabled={busy} onClick={() => void save()}>
                  {t('common.save')}
                </button>
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => { setName(item.name); setDraft(item.body || ''); setEditing(false) }}
                >
                  {t('common.cancel')}
                </button>
              </div>
            </div>
          ) : (
            <div className="summary-body">
              <MarkdownBody text={item.body || ''} />
            </div>
          )}
        </>
      )}
      {share && id && <ShareDialog objectType="skill" objectId={id} onClose={() => { setShare(false); void load() }} />}
    </div>
  )
}
