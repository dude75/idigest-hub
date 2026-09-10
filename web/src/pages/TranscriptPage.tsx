import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { api, apiDownload } from '../api'
import { isOrgAdmin, useAuth } from '../auth'
import { InlineRename } from '../components/InlineRename'
import { ShareDialog } from '../components/ShareDialog'
import { libraryPath } from '../routes'
import type { Skill, Task, Transcript } from '../types'
import { ShareBadges, fmtDate, showError } from '../util'

export function TranscriptPage() {
  const { id } = useParams<{ id: string }>()
  const { t } = useTranslation()
  const { me } = useAuth()
  const nav = useNavigate()
  const [item, setItem] = useState<Transcript | null>(null)
  const [skills, setSkills] = useState<Skill[]>([])
  const [picked, setPicked] = useState<Record<string, boolean>>({})
  const [loadFailed, setLoadFailed] = useState(false)
  const [share, setShare] = useState(false)
  const [busy, setBusy] = useState(false)
  const [openText, setOpenText] = useState(false)
  const admin = isOrgAdmin(me)
  const mine = item?.owner_user_id === me?.user.id
  const canRename = Boolean(mine || admin)

  async function load() {
    if (!id) return
    const [tr, sk] = await Promise.all([
      api<Transcript>(`/transcripts/${id}`),
      api<{ items: Skill[] }>('/skills'),
    ])
    setItem(tr)
    setSkills(sk.items)
  }

  useEffect(() => {
    setOpenText(false)
    load()
      .then(() => setLoadFailed(false))
      .catch((e) => {
        setLoadFailed(true)
        showError(e)
      })
  }, [id])

  async function summarize() {
    if (!id) return
    const skill_ids = Object.entries(picked).filter(([, v]) => v).map(([sid]) => sid)
    if (skill_ids.length === 0) {
      showError(new Error(t('transcript.needSkills')))
      return
    }
    setBusy(true)
    try {
      const task = await api<Task>('/tasks/summarize', {
        method: 'POST',
        body: JSON.stringify({ transcript_id: id, skill_ids }),
      })
      nav(`/app/task/${task.task_id}`)
    } catch (e) {
      showError(e)
    } finally {
      setBusy(false)
    }
  }

  async function toggleHidden() {
    if (!id || !item) return
    try {
      await api(`/transcripts/${id}/${item.hidden ? 'unhide' : 'hide'}`, { method: 'POST' })
      await load()
    } catch (e) {
      showError(e)
    }
  }

  async function wipe() {
    if (!id || !item) return
    const title = item.display_title || item.title || item.id.slice(0, 8)
    if (!window.confirm(t('library.wipeConfirm', { title }))) return
    await api(`/transcripts/${id}`, { method: 'DELETE' })
    nav(libraryPath('transcripts'))
  }

  async function renameTitle(title: string) {
    if (!id) return
    setBusy(true)
    try {
      const next = await api<Transcript>(`/transcripts/${id}`, {
        method: 'PATCH',
        body: JSON.stringify({ title }),
      })
      setItem((prev) => (prev ? { ...prev, ...next } : next))
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
      <Link to={libraryPath('transcripts')}>{t('common.back')}</Link>
      {item ? (
        <InlineRename
          value={item.display_title || item.title || item.id.slice(0, 8)}
          canEdit={canRename}
          busy={busy}
          onSave={renameTitle}
        />
      ) : (
        <h1>{t('transcript.title')}</h1>
      )}
      {item && (
        <>
          <div className="row">
            <ShareBadges item={item} />
            <span className="muted">{fmtDate(item.created_at)}</span>
            {item.source_audio_id && (
              <Link to={`/app/audio/${item.source_audio_id}`}>
                {item.source_filename || t('transcript.sourceAudio', { id: item.source_audio_id.slice(0, 8) })}
              </Link>
            )}
          </div>
          <div className="row" style={{ margin: '8px 0' }}>
            <button
              type="button"
              onClick={() => void apiDownload(`/transcripts/${item.id}/export?format=txt`).catch(showError)}
            >
              {t('common.downloadTxt')}
            </button>
            <button
              type="button"
              onClick={() => void apiDownload(`/transcripts/${item.id}/export?format=json`).catch(showError)}
            >
              {t('common.downloadJson')}
            </button>
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
                onClick={() => void wipe()}
              >
                {t('common.wipe')}
              </button>
            )}
          </div>
          {!admin && (
            <p className="muted" style={{ marginTop: 8 }}>{t('library.cannotDeleteHint')}</p>
          )}
          <section className="item fold">
            <div className="row fold-head">
              <h2 className="grow">{t('transcript.utterances')}</h2>
              {!openText && (
                <span className="muted">{t('transcript.collapsed', { n: (item.utterances || []).length })}</span>
              )}
              <button type="button" onClick={() => setOpenText((v) => !v)}>
                {openText ? t('transcript.collapse') : t('transcript.expand')}
              </button>
            </div>
            {openText && (
              <div className="summary-body fold-body">
                {(item.utterances || []).length === 0 && <p className="muted">{t('common.empty')}</p>}
                {(item.utterances || []).map((u, i) => (
                  <div className="utterance" key={i}>
                    {u.speaker && <span className="speaker">{u.speaker}:</span>}
                    {u.text}
                  </div>
                ))}
              </div>
            )}
          </section>
          <h2>{t('transcript.skills')}</h2>
          <div className="stack">
            {skills.map((s) => (
              <label key={s.id} className="row">
                <input
                  type="checkbox"
                  checked={Boolean(picked[s.id])}
                  onChange={(e) => setPicked((p) => ({ ...p, [s.id]: e.target.checked }))}
                />
                <span>{s.name} <span className="badge">{s.catalog || s.scope}</span></span>
              </label>
            ))}
          </div>
          <button className="primary" disabled={busy} onClick={() => void summarize()}>{t('transcript.summarize')}</button>
          <h2>{t('transcript.summaries')}</h2>
          <div className="list">
            {(item.summaries || []).map((s) => (
              <div className="item row" key={s.id}>
                <Link className="title grow" to={`/app/summary/${s.id}`}>
                  {s.display_title || s.title || s.id.slice(0, 8)}
                </Link>
                <ShareBadges item={s} />
              </div>
            ))}
          </div>
        </>
      )}
      {share && id && <ShareDialog objectType="transcript" objectId={id} onClose={() => { setShare(false); void load() }} />}
    </div>
  )
}
