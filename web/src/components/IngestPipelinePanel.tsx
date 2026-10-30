import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '../api'
import { useAuth } from '../auth'
import { toneAnalyticsLabelKey } from '../toneAnalytics'
import { loadPipeline, normalizePipeline, savePipeline, type IngestPipeline } from '../pipeline'
import type { SchemaSkillListResponse } from '../openapi'
import { showError } from '../util'
import { cn } from '@/lib/utils'
import { AppCheckboxRow } from './app/AppFormControls'
import { SummarizeSkillRadioGroup } from './SummarizeSkillRadioGroup'
import { appFieldCaption, appMutedText } from './app/appTypography'

function pipelineSummaryKey(pipeline: IngestPipeline): string {
  if (!pipeline.transcribe) return 'library.pipeline.summaryOff'
  if (pipeline.skillIds.length === 0) return 'library.pipeline.summaryTranscribe'
  return 'library.pipeline.summaryFull'
}

type IngestPipelinePanelProps = {
  className?: string
  defaultOpen?: boolean
}

export function IngestPipelinePanel({ className, defaultOpen }: IngestPipelinePanelProps = {}) {
  const { t } = useTranslation()
  const { me } = useAuth()
  const [pipeline, setPipeline] = useState<IngestPipeline>(() => loadPipeline())
  const [skills, setSkills] = useState<NonNullable<SchemaSkillListResponse['items']>>([])

  useEffect(() => {
    void api<SchemaSkillListResponse>('/skills')
      .then((r) => setSkills(r.items ?? []))
      .catch(showError)
  }, [])

  function update(next: IngestPipeline) {
    const normalized = normalizePipeline(next)
    setPipeline(normalized)
    savePipeline(normalized)
  }

  function setTranscribe(transcribe: boolean) {
    update({ transcribe, skillIds: transcribe ? pipeline.skillIds : [] })
  }

  function setSkillId(skillId: string | null) {
    update({ ...pipeline, skillIds: skillId ? [skillId] : [] })
  }

  const summaryKey = pipelineSummaryKey(pipeline)
  const selectedSkill = useMemo(
    () => skills.find((s) => s.id === pipeline.skillIds[0]),
    [skills, pipeline.skillIds],
  )
  const summaryArgs =
    summaryKey === 'library.pipeline.summaryFull' && selectedSkill
      ? { name: selectedSkill.name }
      : undefined

  return (
    <details className={cn('fold library-pipeline', className)} open={defaultOpen || undefined}>
      <summary>
        {t('library.pipeline.title')}
        {' · '}
        <span className={cn(appMutedText, 'library-pipeline-summary')}>{t(summaryKey, summaryArgs)}</span>
      </summary>
      <div className="fold-body library-pipeline-body">
        <AppCheckboxRow
          id="library-pipeline-transcribe"
          className="library-pipeline-step"
          label={t('library.pipeline.transcribe')}
          checked={pipeline.transcribe}
          onCheckedChange={setTranscribe}
        />
        {pipeline.transcribe ? (
          <p className={cn(appMutedText, 'library-pipeline-tone')}>{t(toneAnalyticsLabelKey(me))}</p>
        ) : null}
        {pipeline.transcribe && (
          <div className="library-pipeline-skills">
            <div
              className={cn(appFieldCaption, 'library-pipeline-skills-label')}
              id="library-pipeline-skills-label"
            >
              {t('library.pipeline.summarizeSkills')}
            </div>
            {skills.length === 0 && <p className={appMutedText}>{t('common.empty')}</p>}
            {skills.length > 0 ? (
              <SummarizeSkillRadioGroup
                skills={skills}
                value={pipeline.skillIds[0] ?? null}
                onValueChange={setSkillId}
                showNoneOption
                idPrefix="library-pipeline-skill"
                rowClassName="library-pipeline-skill"
                aria-labelledby="library-pipeline-skills-label"
              />
            ) : null}
          </div>
        )}
      </div>
    </details>
  )
}
