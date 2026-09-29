import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '../api'
import { loadPipeline, normalizePipeline, savePipeline, type IngestPipeline } from '../pipeline'
import type { Skill } from '../types'
import { showError } from '../util'
import { AppCheckboxRow } from './app/AppFormControls'

function pipelineSummaryKey(pipeline: IngestPipeline): string {
  if (!pipeline.transcribe) return 'library.pipeline.summaryOff'
  if (pipeline.skillIds.length === 0) return 'library.pipeline.summaryTranscribe'
  return 'library.pipeline.summaryFull'
}

export function IngestPipelinePanel() {
  const { t } = useTranslation()
  const [pipeline, setPipeline] = useState<IngestPipeline>(() => loadPipeline())
  const [skills, setSkills] = useState<Skill[]>([])

  useEffect(() => {
    void api<{ items: Skill[] }>('/skills')
      .then((r) => setSkills(r.items))
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

  function toggleSkill(skillId: string, checked: boolean) {
    const skillIds = checked
      ? [...pipeline.skillIds, skillId]
      : pipeline.skillIds.filter((id) => id !== skillId)
    update({ ...pipeline, skillIds })
  }

  const summaryKey = pipelineSummaryKey(pipeline)
  const summaryArgs = summaryKey === 'library.pipeline.summaryFull'
    ? { count: pipeline.skillIds.length }
    : undefined

  return (
    <details className="fold library-pipeline">
      <summary>
        {t('library.pipeline.title')}
        {' · '}
        <span className="library-pipeline-summary">{t(summaryKey, summaryArgs)}</span>
      </summary>
      <div className="fold-body library-pipeline-body">
        <AppCheckboxRow
          id="library-pipeline-transcribe"
          className="library-pipeline-step"
          label={t('library.pipeline.transcribe')}
          checked={pipeline.transcribe}
          onCheckedChange={setTranscribe}
        />
        {pipeline.transcribe && (
          <div className="library-pipeline-skills">
            <div className="library-pipeline-skills-label">{t('library.pipeline.summarizeSkills')}</div>
            {skills.length === 0 && <p className="muted">{t('common.empty')}</p>}
            {skills.map((s) => (
              <AppCheckboxRow
                key={s.id}
                id={`library-pipeline-skill-${s.id}`}
                className="library-pipeline-skill"
                label={s.name}
                checked={pipeline.skillIds.includes(s.id)}
                onCheckedChange={(checked) => toggleSkill(s.id, checked)}
              />
            ))}
          </div>
        )}
      </div>
    </details>
  )
}
