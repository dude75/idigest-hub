import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { api, apiDownload } from '../api'
import { isOrgAdmin, useAuth } from '../auth'
import { AudioPlayer, type AudioPlayerHandle } from '../components/AudioPlayer'
import { InlineRename } from '../components/InlineRename'
import { ConfirmDialog } from '../components/ConfirmDialog'
import { EntityHint, EntityToolbar } from '../components/EntityToolbar'
import { ListRow } from '../components/ListRow'
import { ShareDialog } from '../components/ShareDialog'
import { loadSummarizeSkillIds, saveSummarizeSkillIds } from '../pipeline'
import { libraryPath } from '../routes'
import type { Skill, Summary, Task, Transcript } from '../types'
import { ShareBadges, fmtDate, showError } from '../util'
import { utteranceDisplayText, utteranceStart, utteranceTimeLabel } from '../util/utteranceMedia'

function skillNamesForSummary(summary: Summary, skills: Skill[]): string {
  const byId = new Map(skills.map((s) => [s.id, s.name]))
  const names = (summary.skill_ids || [])
    .map((sid) => byId.get(sid))
    .filter((name): name is string => Boolean(name))
  if (names.length > 0) return names.join(', ')
  return summary.display_title || summary.title || summary.id.slice(0, 8)
}

function pickedSkillIds(picked: Record<string, boolean>): string[] {
  return Object.entries(picked).filter(([, v]) => v).map(([sid]) => sid)
}

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
  const [confirmWipe, setConfirmWipe] = useState(false)
  const [busy, setBusy] = useState(false)
  const [pendingTaskId, setPendingTaskId] = useState<string | null>(null)
  const [openText, setOpenText] = useState(false)
  const [seekOnClick, setSeekOnClick] = useState(false)
  const playerRef = useRef<AudioPlayerHandle>(null)
  const pickedInit = useRef(false)
  const admin = isOrgAdmin(me)
  const mine = item?.owner_user_id === me?.user.id
  const canRename = Boolean(mine || admin)
  const selectedSkillIds = useMemo(() => pickedSkillIds(picked), [picked])
  const selectedSkillNames = useMemo(
    () => skills.filter((s) => picked[s.id]).map((s) => s.name),
    [skills, picked],
  )

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
    setSeekOnClick(false)
    setPendingTaskId(null)
    pickedInit.current = false
    setPicked({})
    load()
      .then(() => setLoadFailed(false))
      .catch((e) => {
        setLoadFailed(true)
        showError(e)
      })
  }, [id])

  useEffect(() => {
    if (skills.length === 0 || pickedInit.current) return
    pickedInit.current = true
    const saved = new Set(loadSummarizeSkillIds())
    const initial: Record<string, boolean> = {}
    for (const skill of skills) {
      if (saved.has(skill.id)) initial[skill.id] = true
    }
    setPicked(initial)
  }, [skills])

  useEffect(() => {
    if (!pendingTaskId || !id) return
    let cancelled = false
    const interval = window.setInterval(() => {
      void (async () => {
        try {
          const [tr, task] = await Promise.all([
            api<Transcript>(`/transcripts/${id}`),
            api<Task>(`/tasks/${pendingTaskId}`),
          ])
          if (cancelled) return
          setItem(tr)
          if (task.status === 'success' || task.status === 'failed') {
            setPendingTaskId(null)
          }
        } catch {
          /* ignore transient poll errors */
        }
      })()
    }, 3000)
    return () => {
      cancelled = true
      window.clearInterval(interval)
    }
  }, [pendingTaskId, id])

  function toggleSkill(skillId: string, checked: boolean) {
    setPicked((prev) => {
      const next = { ...prev, [skillId]: checked }
      saveSummarizeSkillIds(pickedSkillIds(next))
      return next
    })
  }

  async function summarize() {
    if (!id) return
    const skill_ids = selectedSkillIds
    if (skill_ids.length === 0) return
    setBusy(true)
    try {
      const task = await api<Task>('/tasks/summarize', {
        method: 'POST',
        body: JSON.stringify({ transcript_id: id, skill_ids }),
      })
      setPendingTaskId(task.task_id)
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

  async function doWipe() {
    if (!id) return
    setBusy(true)
    try {
      await api(`/transcripts/${id}`, { method: 'DELETE' })
      nav(libraryPath('transcripts'))
    } catch (e) {
      showError(e)
      setBusy(false)
    }
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

  const skillsSummaryKey = selectedSkillIds.length === 0
    ? 'transcript.skillsNone'
    : 'transcript.skillsPicked'

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
          <div className="entity-actions">
            <div className="audio-media">
              <div className="row">
                <ShareBadges item={item} />
                <span className="muted">{fmtDate(item.created_at)}</span>
                {item.source_audio_id && (
                  <Link to={`/app/audio/${item.source_audio_id}`}>
                    {item.source_filename || t('transcript.sourceAudio', { id: item.source_audio_id.slice(0, 8) })}
                  </Link>
                )}
              </div>
              {item.source_audio_id && <AudioPlayer ref={playerRef} audioId={item.source_audio_id} />}
              <EntityToolbar>
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
                    onClick={() => setConfirmWipe(true)}
                  >
                    {t('common.wipe')}
                  </button>
                )}
              </EntityToolbar>
            </div>
            {!admin && <EntityHint>{t('library.cannotDeleteHint')}</EntityHint>}
          </div>
          <section className="item fold">
            <div className="row fold-head">
              <h2 className="grow">{t('transcript.utterances')}</h2>
              {!openText && (
                <span className="muted">{t('transcript.collapsed', { n: (item.utterances || []).length })}</span>
              )}
              {openText && item.source_audio_id && (
                <label className="inline">
                  <input
                    type="checkbox"
                    checked={seekOnClick}
                    onChange={(e) => setSeekOnClick(e.target.checked)}
                  />
                  <span>{t('transcript.playFromLine')}</span>
                </label>
              )}
              <button
                type="button"
                onClick={() => {
                  setOpenText((v) => {
                    if (v) setSeekOnClick(false)
                    return !v
                  })
                }}
              >
                {openText ? t('transcript.collapse') : t('transcript.expand')}
              </button>
            </div>
            {openText && (
              <div className="summary-body fold-body">
                {(item.utterances || []).length === 0 && <p className="muted">{t('common.empty')}</p>}
                {(item.utterances || []).map((u, i) => {
                  const start = utteranceStart(u)
                  const seekable = Boolean(seekOnClick && item.source_audio_id && start != null)
                  const time = utteranceTimeLabel(u)
                  return (
                    <div
                      className={`utterance${seekable ? ' utterance-seekable' : ''}`}
                      key={i}
                      title={seekable && time ? t('transcript.seekAudio', { time }) : undefined}
                      onClick={seekable ? () => playerRef.current?.seekTo(start!) : undefined}
                    >
                      {time && <span className="utterance-time">{time}</span>}
                      {u.speaker && <span className="speaker">{u.speaker}:</span>}
                      {utteranceDisplayText(u)}
                    </div>
                  )
                })}
              </div>
            )}
          </section>
          <section className="card transcript-summaries">
            <h2 className="transcript-summaries-title">{t('transcript.summaries')}</h2>
            <details className="fold library-pipeline transcript-summaries-skills">
              <summary>
                {t('transcript.skills')}
                {' · '}
                <span className="library-pipeline-summary">
                  {skillsSummaryKey === 'transcript.skillsNone'
                    ? t(skillsSummaryKey)
                    : t(skillsSummaryKey, {
                        count: selectedSkillIds.length,
                        names: selectedSkillNames.join(', '),
                      })}
                </span>
              </summary>
              <div className="fold-body library-pipeline-body">
                {skills.length === 0 && <p className="muted">{t('common.empty')}</p>}
                {skills.map((s) => (
                  <label key={s.id} className="library-pipeline-skill row">
                    <input
                      type="checkbox"
                      checked={Boolean(picked[s.id])}
                      onChange={(e) => toggleSkill(s.id, e.target.checked)}
                    />
                    <span>{s.name} <span className="badge">{s.catalog || s.scope}</span></span>
                  </label>
                ))}
              </div>
            </details>
            <div className="transcript-summaries-actions">
              <button
                className="primary"
                disabled={busy || selectedSkillIds.length === 0}
                onClick={() => void summarize()}
              >
                {t('transcript.summarize')}
              </button>
              {pendingTaskId && (
                <p className="muted transcript-summaries-pending">
                  {t('transcript.summarizePending')}{' '}
                  <Link to={`/app/task/${pendingTaskId}`}>{t('transcript.summarizePendingLink')}</Link>
                </p>
              )}
            </div>
            <div className="transcript-summaries-results">
              <h3>{t('transcript.summariesCount', { count: (item.summaries || []).length })}</h3>
              <div className="list">
                {(item.summaries || []).length === 0 && <p className="muted">{t('common.empty')}</p>}
                {(item.summaries || []).map((s) => (
                  <ListRow
                    key={s.id}
                    to={`/app/summary/${s.id}`}
                    title={skillNamesForSummary(s, skills)}
                    meta={<span>{fmtDate(s.created_at)}</span>}
                    trailing={<ShareBadges item={s} />}
                  />
                ))}
              </div>
            </div>
          </section>
        </>
      )}
      {share && id && <ShareDialog objectType="transcript" objectId={id} onClose={() => { setShare(false); void load() }} />}
      {confirmWipe && item && (
        <ConfirmDialog
          message={t('library.wipeConfirm', { title: item.display_title || item.title || item.id.slice(0, 8) })}
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
