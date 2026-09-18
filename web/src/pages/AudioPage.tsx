import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { api, apiDownload } from '../api'
import { isOrgAdmin, useAuth } from '../auth'
import { AudioPlayer } from '../components/AudioPlayer'
import { ConfirmDialog } from '../components/ConfirmDialog'
import { EntityHint, EntityToolbar } from '../components/EntityToolbar'
import { ListRow } from '../components/ListRow'
import { ShareDialog } from '../components/ShareDialog'
import { pipelineNavState } from '../pipeline'
import { LIBRARY_DEFAULT } from '../routes'
import type { Audio, Task } from '../types'
import { ShareBadges, TranscriptDerivedBadges, fmtDate, showError } from '../util'

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
    <div>
      <Link to={LIBRARY_DEFAULT}>{t('common.back')}</Link>
      <h1>{item?.filename || t('audio.title')}</h1>
      {item && (
        <>
          {sourceUrl && (
            <p className="muted audio-source-url">
              {t('audio.sourceUrl')}:{' '}
              <a href={sourceUrl} target="_blank" rel="noopener noreferrer">
                {sourceUrl}
              </a>
            </p>
          )}
          <div className="entity-actions">
            <div className="audio-media">
              <div className="row">
                <ShareBadges item={item} />
                <span className="muted">{fmtDate(item.created_at)}</span>
              </div>
              <AudioPlayer audioId={item.id} />
              <EntityToolbar>
              {item.can_transcribe && (
                <button
                  type="button"
                  onClick={() => void apiDownload(`/audios/${item.id}/file?download=1`, item.filename).catch(showError)}
                >
                  {t('common.download')}
                </button>
              )}
              {item.can_transcribe ? (
                <button className="primary" disabled={busy} onClick={() => void transcribe()}>
                  {item.transcripts && item.transcripts.length > 0 ? t('audio.transcribeAgain') : t('audio.transcribe')}
                </button>
              ) : (
                <span className="muted">{t('audio.noFile')}</span>
              )}
              {mine && <button type="button" onClick={() => setShare(true)}>{t('common.share')}</button>}
              <button
                type="button"
                title={t('library.hideHint')}
                onClick={() => void toggleHidden()}
              >
                {item.hidden ? t('common.unhide') : t('common.hide')}
              </button>
              {admin && (
                <button
                  type="button"
                  className="danger"
                  title={t('library.wipeHint')}
                  onClick={() => setConfirmWipe(true)}
                >
                  {t('common.wipe')}
                </button>
              )}
              </EntityToolbar>
            </div>
            {!admin && <EntityHint>{t('library.cannotDeleteHint')}</EntityHint>}
          </div>
          <h2>{t('audio.transcripts')}</h2>
          <div className="list">
            {(item.transcripts || []).length === 0 && <p className="muted">{t('common.empty')}</p>}
            {(item.transcripts || []).map((tr) => (
              <ListRow
                key={tr.id}
                to={`/app/transcript/${tr.id}`}
                title={tr.display_title || tr.title || tr.id.slice(0, 8)}
                meta={
                  <>
                    <span>{fmtDate(tr.created_at)}</span>
                    <TranscriptDerivedBadges transcript={tr} />
                    {tr.owner_email && <span>· {tr.owner_email}</span>}
                  </>
                }
                trailing={<ShareBadges item={tr} />}
              />
            ))}
          </div>
        </>
      )}
      {share && id && <ShareDialog objectType="audio" objectId={id} onClose={() => { setShare(false); void load() }} />}
      {confirmWipe && item && (
        <ConfirmDialog
          message={t('library.wipeConfirm', { title: item.filename || item.id.slice(0, 8) })}
          confirmLabel={t('common.wipe')}
          danger
          busy={busy}
          onConfirm={() => void doWipe()}
          onClose={() => setConfirmWipe(false)}
        />
      )}
    </div>
  )
}
