import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { api, apiDownload } from '../api'
import { isOrgAdmin, useAuth } from '../auth'
import { AudioPlayer } from '../components/AudioPlayer'
import { LibraryArtifactImpactModal } from '../components/LibraryArtifactImpactModal'
import { EntityHint, EntityToolbar } from '../components/EntityToolbar'
import { ListRow } from '../components/ListRow'
import { ShareDialog } from '../components/ShareDialog'
import {
  EntityDetailCard,
  EntityPage,
  ListSection,
} from '../components/app/EntityUi'
import { AppHoverHint } from '../components/app/AppHoverHint'
import { pipelineNavState } from '../pipeline'
import { requestTone, toneAnalyticsLabelKey } from '../toneAnalytics'
import { libraryPath } from '../routes'
import type { Audio, Task } from '../types'
import { UserTagsEditor } from '../components/UserTagsEditor'
import { ShareBadges, TranscriptDerivedBadges, fmtDate, showError } from '../util'
import { Button } from '@/components/ui/button'

function httpSourceUrl(value: string | null | undefined): string | null {
  if (!value) return null
  try {
    const parsed = new URL(value)
    if (parsed.protocol === 'http:' || parsed.protocol === 'https:') return value
  } catch {
    return null
  }
  return null
}

export function AudioPage() {
  const { id } = useParams<{ id: string }>()
  const { t } = useTranslation()
  const { me, refresh } = useAuth()
  const nav = useNavigate()
  const [item, setItem] = useState<Audio | null>(null)
  const [loadFailed, setLoadFailed] = useState(false)
  const [share, setShare] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [busy, setBusy] = useState(false)
  const admin = isOrgAdmin(me)
  const mine = item?.owner_user_id === me?.user.id
  const canDelete = item && (mine || admin)
  const sourceUrl = httpSourceUrl(item?.source_url)
  const transcripts = item?.transcripts || []

  async function load() {
    if (!id) return
    try {
      setItem(await api<Audio>(`/audios/${id}`))
      setLoadFailed(false)
    } catch (e) {
      setLoadFailed(true)
      showError(e)
    }
  }

  useEffect(() => {
    void load()
  }, [id])

  async function transcribe() {
    if (!id) return
    setBusy(true)
    try {
      const task = await api<Task>('/tasks/transcribe', {
        method: 'POST',
        body: JSON.stringify({ audio_id: id, tone: requestTone(me) }),
      })
      nav(`/app/task/${task.task_id}`, {
        state: pipelineNavState({ transcribe: true, skillIds: [] }, task),
      })
    } catch (e) {
      showError(e)
    } finally {
      setBusy(false)
    }
  }

  async function toggleHidden() {
    if (!id || !item) return
    try {
      await api(`/audios/${id}/${item.hidden ? 'unhide' : 'hide'}`, { method: 'POST' })
      await load()
    } catch (e) {
      showError(e)
    }
  }

  async function doDelete() {
    if (!id) return
    setBusy(true)
    try {
      await api(`/audios/${id}`, { method: 'DELETE' })
      await refresh()
      nav(libraryPath('audio'))
    } catch (e) {
      showError(e)
      setBusy(false)
    }
  }

  if (!item && !loadFailed) return <p className="muted">{t('common.loading')}</p>

  return (
    <EntityPage backTo={libraryPath('audio')}>
      <h1 className="entity-title">{item?.filename || t('audio.title')}</h1>
      {item && (
        <>
          <EntityDetailCard>
            {sourceUrl && (
              <p className="muted audio-source-url">
                {t('audio.sourceUrl')}:{' '}
                <a href={sourceUrl} target="_blank" rel="noopener noreferrer">
                  {sourceUrl}
                </a>
              </p>
            )}
            <div className="entity-meta-row flex flex-wrap items-center gap-2">
              <span className="muted">{fmtDate(item.created_at)}</span>
              <ShareBadges item={item} />
            </div>
            <UserTagsEditor
              objectType="audio"
              objectId={item.id}
              tags={item.user_tags || []}
              onChange={(user_tags) => setItem({ ...item, user_tags })}
            />
            <AudioPlayer audioId={item.id} />
            <EntityToolbar>
              {item.can_transcribe && (
                <Button type="button" variant="outline" onClick={() => void apiDownload(`/audios/${item.id}/file?download=1`, item.filename).catch(showError)}>
                  {t('common.download')}
                </Button>
              )}
              {item.can_transcribe ? (
                <>
                  <Button type="button" disabled={busy} onClick={() => void transcribe()}>
                    {transcripts.length > 0 ? t('audio.transcribeAgain') : t('audio.transcribe')}
                  </Button>
                  <span className="muted text-sm">{t(toneAnalyticsLabelKey(me))}</span>
                </>
              ) : (
                <span className="muted">{t('audio.noFile')}</span>
              )}
              {mine ? <Button type="button" variant="outline" onClick={() => setShare(true)}>{t('common.share')}</Button> : null}
              <AppHoverHint content={t('library.hideHint')}>
                <Button type="button" variant="outline" onClick={() => void toggleHidden()}>
                  {item.hidden ? t('common.unhide') : t('common.hide')}
                </Button>
              </AppHoverHint>
              {canDelete ? (
                <AppHoverHint content={admin && !mine ? t('library.deleteAdminHint') : t('library.deleteOwnerHint')}>
                  <Button type="button" variant="destructive" onClick={() => setConfirmDelete(true)}>
                    {t('common.delete')}
                  </Button>
                </AppHoverHint>
              ) : null}
            </EntityToolbar>
            {!canDelete && item ? <EntityHint>{t('library.cannotDeleteHint')}</EntityHint> : null}
          </EntityDetailCard>
          <ListSection title={t('audio.transcripts')} empty={t('common.empty')} isEmpty={transcripts.length === 0}>
            {transcripts.map((tr) => (
              <ListRow
                key={tr.id}
                to={`/app/transcript/${tr.id}`}
                title={tr.display_title || tr.title || tr.id.slice(0, 8)}
                meta={
                  <>
                    <span>{fmtDate(tr.created_at)}</span>
                    <TranscriptDerivedBadges transcript={tr} />
                    {tr.owner_email ? <span>· {tr.owner_email}</span> : null}
                  </>
                }
                trailing={<ShareBadges item={tr} />}
              />
            ))}
          </ListSection>
        </>
      )}
      {share && id ? <ShareDialog objectType="audio" objectId={id} onClose={() => { setShare(false); void load() }} /> : null}
      {confirmDelete && item && id ? (
        <LibraryArtifactImpactModal
          objectType="audio"
          objectId={id}
          title={item.filename || item.id.slice(0, 8)}
          onConfirm={() => doDelete()}
          onClose={() => setConfirmDelete(false)}
        />
      ) : null}
    </EntityPage>
  )
}
