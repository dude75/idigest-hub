import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '../api'
import { Modal } from './Modal'
import type { LibraryArtifactDeleteImpact } from '../types'
import { formatInteger, showError, truncateLabel } from '../util'
import { Button } from '@/components/ui/button'

type Props = {
  objectType: 'audio' | 'transcript' | 'summary'
  objectId: string
  title: string
  onClose: () => void
  onConfirm: () => void | Promise<void>
}

export function LibraryArtifactImpactModal({
  objectType,
  objectId,
  title,
  onClose,
  onConfirm,
}: Props) {
  const { t } = useTranslation()
  const [impact, setImpact] = useState<LibraryArtifactDeleteImpact | null>(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)

  const path =
    objectType === 'audio'
      ? `/audios/${objectId}/delete-impact`
      : objectType === 'transcript'
        ? `/transcripts/${objectId}/delete-impact`
        : `/summaries/${objectId}/delete-impact`

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    void api<LibraryArtifactDeleteImpact>(path)
      .then((data) => {
        if (!cancelled) setImpact(data)
      })
      .catch((error) => {
        if (!cancelled) {
          showError(error)
          onClose()
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [path, onClose])

  const hasImpact = useMemo(() => {
    if (!impact) return false
    const tasks = (impact.active_tasks?.queued ?? 0) + (impact.active_tasks?.running ?? 0)
    return (
      (impact.shared_with?.length ?? 0) > 0
      || (impact.transcripts?.length ?? 0) > 0
      || (impact.summaries?.length ?? 0) > 0
      || tasks > 0
      || Boolean(impact.has_active_public_link)
    )
  }, [impact])

  async function confirm() {
    setBusy(true)
    try {
      await onConfirm()
      onClose()
    } catch (e) {
      showError(e)
    } finally {
      setBusy(false)
    }
  }

  const bannerClass = loading ? 'loading' : hasImpact ? 'warn' : 'ok'
  const bannerMessage = loading
    ? t('instance.workerImpactLoading')
    : hasImpact
      ? t('library.artifactImpactWarn')
      : t('instance.workerImpactNoImpact')

  return (
    <Modal
      onClose={() => {
        if (busy) return
        onClose()
      }}
      closeOnBackdrop={!busy && !loading}
      wide
      title={t('library.artifactDeleteTitle', { title: truncateLabel(title, 64) })}
      panelClassName="worker-impact-modal max-h-[min(92vh,880px)] overflow-y-auto sm:max-w-3xl"
      footer={
        <>
          <Button type="button" variant="outline" disabled={busy || loading} autoFocus onClick={onClose}>
            {t('common.cancel')}
          </Button>
          <Button
            type="button"
            variant="destructive"
            disabled={loading || busy}
            onClick={() => void confirm()}
          >
            {busy ? t('library.artifactDeleting') : t('common.delete')}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <div className={`worker-impact-banner ${bannerClass}`}>
          <p>{bannerMessage}</p>
        </div>
        <p className="worker-impact-subhead muted">{t('library.artifactImpactBillingNote')}</p>
        {!loading && impact ? (
          <div className="worker-impact-sections">
            {(impact.shared_with?.length ?? 0) > 0 ? (
              <section className="worker-impact-section">
                <div className="worker-impact-section-head">
                  <h3>{t('library.artifactImpactSharedWith')}</h3>
                </div>
                <ul className="worker-impact-list">
                  {impact.shared_with!.map((row) => (
                    <li key={row.email} className="worker-impact-row">
                      {row.email}
                    </li>
                  ))}
                </ul>
              </section>
            ) : null}
            {impact.has_active_public_link ? (
              <section className="worker-impact-section">
                <div className="worker-impact-section-head">
                  <h3>{t('library.artifactImpactPublicLink')}</h3>
                  <p className="worker-impact-section-hint">{t('library.artifactImpactPublicLinkHint')}</p>
                </div>
              </section>
            ) : null}
            {(impact.transcripts?.length ?? 0) > 0 ? (
              <section className="worker-impact-section">
                <div className="worker-impact-section-head">
                  <h3>{t('library.artifactImpactTranscripts')}</h3>
                  <p className="worker-impact-section-hint">{t('library.artifactImpactTranscriptsHint')}</p>
                </div>
                <ul className="worker-impact-list">
                  {impact.transcripts!.map((row) => (
                    <li key={row.id} className="worker-impact-row">
                      {truncateLabel(row.title, 80)}
                    </li>
                  ))}
                </ul>
              </section>
            ) : null}
            {(impact.summaries?.length ?? 0) > 0 ? (
              <section className="worker-impact-section">
                <div className="worker-impact-section-head">
                  <h3>{t('library.artifactImpactSummaries')}</h3>
                  <p className="worker-impact-section-hint">{t('library.artifactImpactSummariesHint')}</p>
                </div>
                <ul className="worker-impact-list">
                  {impact.summaries!.map((row) => (
                    <li key={row.id} className="worker-impact-row">
                      {truncateLabel(row.title, 80)}
                    </li>
                  ))}
                </ul>
              </section>
            ) : null}
            {((impact.active_tasks?.queued ?? 0) + (impact.active_tasks?.running ?? 0)) > 0 ? (
              <section className="worker-impact-section">
                <div className="worker-impact-section-head">
                  <h3>{t('library.artifactImpactTasks')}</h3>
                </div>
                <ul className="worker-impact-list">
                  {(impact.active_tasks?.queued ?? 0) > 0 ? (
                    <li className="worker-impact-row warn">
                      {t('library.artifactImpactTasksQueued', {
                        count: formatInteger(impact.active_tasks!.queued),
                      })}
                    </li>
                  ) : null}
                  {(impact.active_tasks?.running ?? 0) > 0 ? (
                    <li className="worker-impact-row warn">
                      {t('library.artifactImpactTasksRunning', {
                        count: formatInteger(impact.active_tasks!.running),
                      })}
                    </li>
                  ) : null}
                </ul>
              </section>
            ) : null}
          </div>
        ) : null}
      </div>
    </Modal>
  )
}
