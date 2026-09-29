import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { api, apiDownload } from '../api'
import { isOrgAdmin, useAuth } from '../auth'
import { AudioPlayer } from '../components/AudioPlayer'
import { ConfirmDialog } from '../components/ConfirmDialog'
import { EntityHint, EntityToolbar } from '../components/EntityToolbar'
import { ListRow } from '../components/ListRow'
import { ShareDialog } from '../components/ShareDialog'
import {
  EntityBackLink,
  EntityDetailCard,
  EntityPage,
  ListSection,
} from '../components/app/EntityUi'
import { pipelineNavState } from '../pipeline'
import { LIBRARY_DEFAULT } from '../routes'
import type { Audio, Task } from '../types'
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
  const [confirmWipe, setConfirmWipe] = useState(false)
  const [busy, setBusy] = useState(false)
  const admin = isOrgAdmin(me)
  const mine = item?.owner_user_id === me?.user.id
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
        body: JSON.stringify({ audio_id: id }),
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

  async function doWipe() {
    if (!id) return
    setBusy(true)
    try {
      await api(`/audios/${id}`, { method: 'DELETE' })
      await refresh()
      nav(LIBRARY_DEFAULT)
    } catch (e) {
      showError(e)
      setBusy(false)
    }
  }

  if (!item && !loadFailed) return <p className="muted">{t('common.loading')}</p>

  return (
    <EntityPage>
      <EntityBackLink to={LIBRARY_DEFAULT}>{t('common.back')}</EntityBackLink>
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
            <div className="flex flex-wrap items-center gap-2">
              <ShareBadges item={item} />
              <span className="muted">{fmtDate(item.created_at)}</span>
            </div>
            <AudioPlayer audioId={item.id} />
            <EntityToolbar>
              {item.can_transcribe && (
                <Button type="button" variant="outline" onClick={() => void apiDownload(`/audios/${item.id}/file?download=1`, item.filename).catch(showError)}>
                  {t('common.download')}
                </Button>
              )}
              {item.can_transcribe ? (
                <Button type="button" disabled={busy} onClick={() => void transcribe()}>
                  {transcripts.length > 0 ? t('audio.transcribeAgain') : t('audio.transcribe')}
                </Button>
              ) : (
                <span className="muted">{t('audio.noFile')}</span>
              )}
              {mine ? <Button type="button" variant="outline" onClick={() => setShare(true)}>{t('common.share')}</Button> : null}
              <Button type="button" variant="outline" title={t('library.hideHint')} onClick={() => void toggleHidden()}>
                {item.hidden ? t('common.unhide') : t('common.hide')}
              </Button>
              {admin ? (
                <Button type="button" variant="destructive" title={t('library.wipeHint')} onClick={() => setConfirmWipe(true)}>
                  {t('common.wipe')}
                </Button>
              ) : null}
            </EntityToolbar>
            {!admin ? <EntityHint>{t('library.cannotDeleteHint')}</EntityHint> : null}
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
      {confirmWipe && item ? (
        <ConfirmDialog
          message={t('library.wipeConfirm', { title: item.filename || item.id.slice(0, 8) })}
          confirmLabel={t('common.wipe')}
          danger
          busy={busy}
          onConfirm={() => void doWipe()}
          onClose={() => setConfirmWipe(false)}
        />
      ) : null}
    </EntityPage>
  )
}
