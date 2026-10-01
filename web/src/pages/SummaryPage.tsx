import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { api, apiDownload } from '../api'
import { isOrgAdmin, useAuth } from '../auth'
import { AudioPlayer } from '../components/AudioPlayer'
import { InlineRename } from '../components/InlineRename'
import { ConfirmDialog } from '../components/ConfirmDialog'
import { EntityToolbar } from '../components/EntityToolbar'
import { ShareDialog } from '../components/ShareDialog'
import { MarkdownBody } from '../markdown'
import { libraryPath } from '../routes'
import type { Summary } from '../types'
import { UserTagsEditor } from '../components/UserTagsEditor'
import { ShareBadges, fmtDate, showError } from '../util'
import { Button } from '@/components/ui/button'
import { AppHoverHint } from '../components/app/AppHoverHint'
import { AdminFormActions, AppSubmitButton } from '../components/app/AdminUi'
import {
  EntityBackLink,
  EntityBodyCard,
  EntityDetailCard,
  EntityPage,
} from '../components/app/EntityUi'

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

  const summaryEditReady = useMemo(() => {
    if (!item) return false
    return draft !== (item.body || '')
  }, [item, draft])

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
    <EntityPage>
      <EntityBackLink to={libraryPath('summaries')}>{t('common.back')}</EntityBackLink>
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
          <EntityDetailCard>
              <div className="entity-meta-row flex flex-wrap items-center gap-2">
                <span className="muted">{fmtDate(item.created_at)}</span>
                {item.source_transcript_id ? (
                  <Link to={`/app/transcript/${item.source_transcript_id}`}>
                    {item.source_transcript_title || t('summary.sourceTranscript', { id: item.source_transcript_id.slice(0, 8) })}
                  </Link>
                ) : null}
                <ShareBadges item={item} />
              </div>
              <UserTagsEditor
                objectType="summary"
                objectId={item.id}
                tags={item.user_tags || []}
                onChange={(user_tags) => setItem({ ...item, user_tags })}
              />
              {item.source_audio_id ? <AudioPlayer audioId={item.source_audio_id} /> : null}
              <EntityToolbar>
                <Button type="button" variant="outline" onClick={() => void apiDownload(`/summaries/${item.id}/export?format=md`).catch(showError)}
                >
                  {t('common.downloadMd')}
                </Button>
                {mine && <Button type="button" variant="outline" onClick={() => setShare(true)}>{t('common.share')}</Button>}
                <AppHoverHint content={t('library.hideHint')}>
                  <Button type="button" variant="outline" onClick={() => void toggleHidden()}>
                    {item.hidden ? t('common.unhide') : t('common.hide')}
                  </Button>
                </AppHoverHint>
                {canEdit && !editing && (
                  <Button type="button" variant="outline" onClick={() => { setDraft(item.body || ''); setEditing(true) }}>
                    {t('common.edit')}
                  </Button>
                )}
                {canDelete && (
                  <AppHoverHint content={admin && !mine ? t('library.deleteAdminHint') : t('library.deleteOwnerHint')}>
                    <Button type="button" variant="destructive" onClick={() => setConfirmDelete(true)}>
                      {t('common.delete')}
                    </Button>
                  </AppHoverHint>
                )}
              </EntityToolbar>
          </EntityDetailCard>
          <EntityBodyCard title={t('summary.body')}>
            {editing ? (
              <div className="flex flex-col gap-3">
                <textarea
                  className="summary-editor min-h-[12rem] w-full rounded-lg border border-input bg-transparent px-2.5 py-2 text-sm"
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                />
                <AdminFormActions>
                  <AppSubmitButton ready={summaryEditReady} busy={busy} onClick={() => void save()}>
                    {t('common.save')}
                  </AppSubmitButton>
                  <Button type="button" variant="outline" disabled={busy} onClick={() => { setDraft(item.body || ''); setEditing(false) }}>
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
      {share && id && (
        <ShareDialog
          objectType="summary"
          objectId={id}
          canManagePublicLink={mine}
          onClose={() => { setShare(false); void load() }}
        />
      )}
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
    </EntityPage>
  )
}
