import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { api, apiDownload } from '../api'
import { isOrgAdmin, useAuth } from '../auth'
import { AudioPlayer, type AudioPlayerHandle } from '../components/AudioPlayer'
import { InlineRename } from '../components/InlineRename'
import { LibraryArtifactImpactModal } from '../components/LibraryArtifactImpactModal'
import { EntityHint, EntityToolbar } from '../components/EntityToolbar'
import { ListRow } from '../components/ListRow'
import { ShareDialog } from '../components/ShareDialog'
import {
  beginSummarizePipelineRun,
  loadSummarizeSkillIds,
  pipelineNavState,
  saveSummarizeSkillIds,
} from '../pipeline'
import { libraryPath } from '../routes'
import type { SchemaSkillListResponse, SchemaSkillPublicResponse } from '../openapi'
import type { Summary, Task, Transcript } from '../types'
import { UserTagsEditor } from '../components/UserTagsEditor'
import { ShareBadges, fmtDate, showError } from '../util'
import { utteranceDisplayText, utteranceStart, utteranceTimeLabel } from '../util/utteranceMedia'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { AppCheckboxRow } from '../components/app/AppFormControls'
import {
  TranscriptToneSummaryCard,
  UtteranceToneChip,
  utteranceValenceHint,
  utteranceValenceStripeClass,
} from '../components/TranscriptTonePanel'
import { HubBadge } from '../components/app/AdminUi'
import { skillScopeLabel } from '../skillScope'
import { AppCursorHint } from '../components/app/AppCursorHint'
import { AppHoverHint } from '../components/app/AppHoverHint'
import {
  EntityBodyCard,
  EntityDetailCard,
  EntityPage,
} from '../components/app/EntityUi'

function skillNamesForSummary(summary: Summary, skills: SchemaSkillPublicResponse[]): string {
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
  const [skills, setSkills] = useState<NonNullable<SchemaSkillListResponse['items']>>([])
  const [picked, setPicked] = useState<Record<string, boolean>>({})
  const [loadFailed, setLoadFailed] = useState(false)
  const [share, setShare] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [busy, setBusy] = useState(false)
  const [openText, setOpenText] = useState(false)
  const [seekOnClick, setSeekOnClick] = useState(false)
  const [showToneOnUtterances, setShowToneOnUtterances] = useState(() => {
    try {
      return localStorage.getItem('idigest-transcript-show-tone') === 'true'
    } catch {
      return false
    }
  })
  const playerRef = useRef<AudioPlayerHandle>(null)
  const pickedInit = useRef(false)
  const admin = isOrgAdmin(me)
  const mine = item?.owner_user_id === me?.user.id
  const canDelete = item && (mine || admin)
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
      api<SchemaSkillListResponse>('/skills'),
    ])
    setItem(tr)
    setSkills(sk.items ?? [])
  }

  useEffect(() => {
    setOpenText(false)
    setSeekOnClick(false)
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
      const pipeline = beginSummarizePipelineRun(skill_ids)
      const task = await api<Task>('/tasks/summarize', {
        method: 'POST',
        body: JSON.stringify({ transcript_id: id, skill_ids }),
      })
      nav(`/app/task/${task.task_id}`, { state: pipelineNavState(pipeline, task) })
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

  async function doDelete() {
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

  const utteranceActions = (
    <div className="transcript-utterance-actions flex flex-wrap items-center justify-end gap-2">
      {!openText ? (
        <span className="text-sm text-muted-foreground">{t('transcript.collapsed', { n: (item?.utterances || []).length })}</span>
      ) : null}
      {openText && item?.has_tone_analytics ? (
        <AppCheckboxRow
          id="transcript-show-tone"
          label={t('transcript.showToneOnLines')}
          checked={showToneOnUtterances}
          onCheckedChange={(checked) => {
            setShowToneOnUtterances(checked)
            try {
              localStorage.setItem('idigest-transcript-show-tone', checked ? 'true' : 'false')
            } catch {
              /* ignore */
            }
          }}
        />
      ) : null}
      {openText && item?.source_audio_id ? (
        <AppCheckboxRow
          id="transcript-seek-on-click"
          label={t('transcript.playFromLine')}
          checked={seekOnClick}
          onCheckedChange={setSeekOnClick}
        />
      ) : null}
      <Button
        type="button"
        size="sm"
        variant="outline"
        onClick={() => {
          setOpenText((v) => {
            if (v) setSeekOnClick(false)
            return !v
          })
        }}
      >
        {openText ? t('transcript.collapse') : t('transcript.expand')}
      </Button>
    </div>
  )

  return (
    <EntityPage backTo={libraryPath('transcripts')}>
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
          <EntityDetailCard>
              <div className="entity-meta-row flex flex-wrap items-center gap-2">
                <span className="muted">{fmtDate(item.created_at)}</span>
                {item.source_audio_id ? (
                  <Link to={`/app/audio/${item.source_audio_id}`}>
                    {item.source_filename || t('transcript.sourceAudio', { id: item.source_audio_id.slice(0, 8) })}
                  </Link>
                ) : null}
                <ShareBadges item={item} />
              </div>
              <TranscriptToneSummaryCard item={item} />
              <UserTagsEditor
                objectType="transcript"
                objectId={item.id}
                tags={item.user_tags || []}
                onChange={(user_tags) => setItem({ ...item, user_tags })}
              />
              {item.source_audio_id ? <AudioPlayer ref={playerRef} audioId={item.source_audio_id} /> : null}
              <EntityToolbar>
                <Button type="button" variant="outline" onClick={() => void apiDownload(`/transcripts/${item.id}/export?format=txt`).catch(showError)}
                >
                  {t('common.downloadTxt')}
                </Button>
                <Button type="button" variant="outline" onClick={() => void apiDownload(`/transcripts/${item.id}/export?format=json`).catch(showError)}
                >
                  {t('common.downloadJson')}
                </Button>
                {mine && <Button type="button" variant="outline" onClick={() => setShare(true)}>{t('common.share')}</Button>}
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
          <EntityBodyCard title={t('transcript.utterances')} actions={utteranceActions}>
            {openText ? (
              <div
                className={`summary-body${showToneOnUtterances && item.has_tone_analytics ? ' transcript-utterances-show-tone' : ''}`}
              >
                {(item.utterances || []).length === 0 ? <p className="muted">{t('common.empty')}</p> : null}
                {(item.utterances || []).map((u, i) => {
                  const start = utteranceStart(u)
                  const seekable = Boolean(seekOnClick && item.source_audio_id && start != null)
                  const onSeek = seekable ? () => playerRef.current?.seekTo(start!) : undefined
                  const time = utteranceTimeLabel(u)
                  const seekHint = seekable && time ? t('transcript.seekAudio', { time }) : undefined
                  const showTone = showToneOnUtterances && item.has_tone_analytics
                  const stripeClass = showTone ? utteranceValenceStripeClass(u) : ''
                  const toneHint = stripeClass ? utteranceValenceHint(u, t) : null
                  const stripe = stripeClass ? (
                    <div className={`utterance-stripe ${stripeClass}`} />
                  ) : null
                  const stripeInCol =
                    stripe && toneHint ? (
                      <AppCursorHint content={toneHint} className="utterance-stripe-hit">
                        {stripe}
                      </AppCursorHint>
                    ) : (
                      stripe
                    )
                  const toneCol =
                    item.has_tone_analytics ? (
                      <div className="utterance-stripe-col">{showTone ? stripeInCol : null}</div>
                    ) : null
                  const main = (
                    <div
                      className={`utterance-main${seekable ? ' utterance-main-seekable' : ''}${seekHint ? ' cursor-help' : ''}`}
                    >
                      <span className="utterance-meta">
                        {time && <span className="utterance-time">{time}</span>}
                        {u.speaker && <span className="speaker">{u.speaker}:</span>}
                        {showTone ? <UtteranceToneChip u={u} /> : null}
                      </span>
                      <span className="utterance-text">{utteranceDisplayText(u)}</span>
                    </div>
                  )
                  const mainWithHint =
                    seekHint && onSeek ? (
                      <AppCursorHint
                        content={seekHint}
                        className="utterance-main-hit utterance-main-seekable"
                        onClick={onSeek}
                      >
                        {main}
                      </AppCursorHint>
                    ) : onSeek ? (
                      <div
                        className="utterance-main-hit utterance-main-seekable"
                        onClick={onSeek}
                        role="button"
                        tabIndex={0}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' || e.key === ' ') {
                            e.preventDefault()
                            onSeek()
                          }
                        }}
                      >
                        {main}
                      </div>
                    ) : (
                      main
                    )
                  return (
                    <div key={i} className="utterance-row">
                      {toneCol}
                      {mainWithHint}
                    </div>
                  )
                })}
              </div>
            ) : null}
          </EntityBodyCard>
          <Card className="transcript-summaries">
            <CardHeader className="pb-3">
              <CardTitle className="transcript-summaries-title text-base">{t('transcript.summaries')}</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-3">
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
                  <AppCheckboxRow
                    key={s.id}
                    id={`transcript-skill-${s.id}`}
                    className="library-pipeline-skill"
                    label={
                      <>
                        {s.name}{' '}
                        <HubBadge tone="muted" className="align-middle">
                          {skillScopeLabel(s.scope, s.catalog, t)}
                        </HubBadge>
                      </>
                    }
                    checked={Boolean(picked[s.id])}
                    onCheckedChange={(checked) => toggleSkill(s.id, checked)}
                  />
                ))}
              </div>
            </details>
            <div className="transcript-summaries-actions">
              <Button disabled={busy || selectedSkillIds.length === 0} onClick={() => void summarize()}
              >
                {t('transcript.summarize')}
              </Button>
            </div>
            <div className="transcript-summaries-results border-t pt-3">
              <h3 className="mb-2 text-sm font-medium">{t('transcript.summariesCount', { count: (item.summaries || []).length })}</h3>
              {(item.summaries || []).length === 0 ? (
                <p className="stats-empty py-4">{t('common.empty')}</p>
              ) : (
                <div className="list task-list-embedded transcript-summaries-list -mx-4 sm:mx-0">
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
              )}
            </div>
            </CardContent>
          </Card>
        </>
      )}
      {share && id && <ShareDialog objectType="transcript" objectId={id} onClose={() => { setShare(false); void load() }} />}
      {confirmDelete && item && id ? (
        <LibraryArtifactImpactModal
          objectType="transcript"
          objectId={id}
          title={item.display_title || item.title || item.id.slice(0, 8)}
          onConfirm={() => doDelete()}
          onClose={() => setConfirmDelete(false)}
        />
      ) : null}
    </EntityPage>
  )
}
