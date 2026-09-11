import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { api, apiDownload } from '../api'
import { isOrgAdmin, useAuth } from '../auth'
import { InlineRename } from '../components/InlineRename'
import { ConfirmDialog } from '../components/ConfirmDialog'
import { ShareDialog } from '../components/ShareDialog'
import { MarkdownBody } from '../markdown'
import { libraryPath } from '../routes'
import type { Summary } from '../types'
import { ShareBadges, fmtDate, showError } from '../util'

export function SummaryPage() {
  const { id } = useParams<{ id: string }>()
  const { t } = useTranslation()
  const { me } = useAuth()
  const nav = useNavigate()
  const [item, setItem] = useState<Summary | null>(null)
  const [draft, setDraft] = useState('')
  const [editing, setEditing] = useState(false)
  const [loadFailed, setLoadFailed] = useState(false)
  const [share, setShare] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [busy, setBusy] = useState(false)
  const admin = isOrgAdmin(me)
  const canDelete = item && (item.owner_user_id === me?.user.id || admin)
  const canEdit = Boolean(canDelete)
  const mine = item?.owner_user_id === me?.user.id

  async function load() {
    if (!id) return
    const next = await api<Summary>(`/summaries/${id}`)
    setItem(next)
    setDraft(next.body || '')
  }

  useEffect(() => {
    load()
      .then(() => setLoadFailed(false))
      .catch((e) => {
        setLoadFailed(true)
        showError(e)
      })
  }, [id])

  async function save() {
    if (!id) return
    setBusy(true)
    try {
      const next = await api<Summary>(`/summaries/${id}`, {
        method: 'PATCH',
        body: JSON.stringify({ body: draft }),
      })
      setItem(next)
      setDraft(next.body || '')
      setEditing(false)
    } catch (e) {
      showError(e)
    } finally {
      setBusy(false)
    }
  }

  async function toggleHidden() {
    if (!id || !item) return
    try {
      await api(`/summaries/${id}/${item.hidden ? 'unhide' : 'hide'}`, { method: 'POST' })
      await load()
    } catch (e) {
      showError(e)
    }
  }

  async function doRemove() {
    if (!id) return
    setBusy(true)
    try {
      await api(`/summaries/${id}`, { method: 'DELETE' })
      nav(libraryPath('summaries'))
    } catch (e) {
      showError(e)
      setBusy(false)
    }
  }

  async function renameTitle(title: string) {
    if (!id) return
    setBusy(true)
    try {
      const next = await api<Summary>(`/summaries/${id}`, {
        method: 'PATCH',
        body: JSON.stringify({ title }),
      })
      setItem(next)
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
      <Link to={libraryPath('summaries')}>{t('common.back')}</Link>
      {item ? (
        <InlineRename
          value={item.display_title || item.title || item.id.slice(0, 8)}
          canEdit={canEdit}
          busy={busy}
          onSave={renameTitle}
        />
      ) : (
        <h1>{t('summary.title')}</h1>
      )}
      {item && (
        <>
          <div className="row">
            <ShareBadges item={item} />
            <span className="muted">{fmtDate(item.created_at)}</span>
            {item.source_transcript_id && (
              <Link to={`/app/transcript/${item.source_transcript_id}`}>
                {t('summary.sourceTranscript', { id: item.source_transcript_id.slice(0, 8) })}
              </Link>
            )}
          </div>
          <div className="row" style={{ margin: '8px 0' }}>
            <button
              type="button"
              onClick={() => void apiDownload(`/summaries/${item.id}/export?format=md`).catch(showError)}
            >
              {t('common.downloadMd')}
            </button>
            {mine && <button type="button" onClick={() => setShare(true)}>{t('common.share')}</button>}
            <button
              type="button"
              title={t('library.hideHint')}
              onClick={() => void toggleHidden()}
            >
              {item.hidden ? t('common.unhide') : t('common.hide')}
            </button>
            {canEdit && !editing && (
              <button type="button" onClick={() => { setDraft(item.body || ''); setEditing(true) }}>
                {t('common.edit')}
              </button>
            )}
            {canDelete && (
              <button
                type="button"
                className="danger"
                title={admin && !mine ? t('library.deleteAdminHint') : t('library.deleteOwnerHint')}
                onClick={() => setConfirmDelete(true)}
              >
                {t('common.delete')}
              </button>
            )}
          </div>
          {editing ? (
            <div className="stack">
              <textarea
                className="summary-editor"
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
                  onClick={() => { setDraft(item.body || ''); setEditing(false) }}
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
      {share && id && <ShareDialog objectType="summary" objectId={id} onClose={() => { setShare(false); void load() }} />}
      {confirmDelete && item && (
        <ConfirmDialog
          message={t('library.deleteConfirm', { title: item.display_title || item.title || item.id.slice(0, 8) })}
          confirmLabel={t('common.delete')}
          danger
          busy={busy}
          onConfirm={() => void doRemove()}
          onClose={() => setConfirmDelete(false)}
        />
      )}
    </div>
  )
}
