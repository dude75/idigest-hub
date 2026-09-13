import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { activePipeline, type IngestPipeline } from '../pipeline'
import type { Task } from '../types'

type StepId = 'import' | 'transcribe' | 'summarize'

type Step = {
  id: StepId
  labelKey: string
}

function buildSteps(pipeline: IngestPipeline, showImport: boolean): Step[] {
  const steps: Step[] = []
  if (showImport) steps.push({ id: 'import', labelKey: 'task.type.import' })
  if (pipeline.transcribe) steps.push({ id: 'transcribe', labelKey: 'task.type.transcribe' })
  if (pipeline.skillIds.length > 0) steps.push({ id: 'summarize', labelKey: 'task.type.summarize' })
  return steps
}

function stepStatus(step: StepId, task: Task | null, steps: Step[]): 'pending' | 'active' | 'done' {
  if (!task) return 'pending'
  const idx = steps.findIndex((s) => s.id === step)
  const currentIdx = steps.findIndex((s) => s.id === task.type)
  if (currentIdx < 0) {
    if (task.status === 'success') return 'done'
    return 'pending'
  }
  if (idx < currentIdx) return 'done'
  if (idx > currentIdx) return 'pending'
  if (task.status === 'success') return 'done'
  if (task.status === 'queued' || task.status === 'running') return 'active'
  return 'pending'
}

export function PipelineProgress({ task }: { task: Task | null }) {
  const { t } = useTranslation()
  const pipeline = activePipeline()
  const [showImport, setShowImport] = useState(false)

  useEffect(() => {
    if (task?.type === 'import') setShowImport(true)
  }, [task?.type])

  const steps = buildSteps(pipeline, showImport)

  if (steps.length <= 1) return null

  return (
    <ol className="pipeline-progress" aria-label={t('task.pipeline.title')}>
      {steps.map((step, i) => {
        const status = stepStatus(step.id, task, steps)
        return (
          <li
            key={step.id}
            className={`pipeline-step pipeline-step-${status}${i < steps.length - 1 ? ' pipeline-step-has-next' : ''}`}
          >
            <span className="pipeline-step-marker" aria-hidden="true" />
            <span className="pipeline-step-label">{t(step.labelKey)}</span>
          </li>
        )
      })}
    </ol>
  )
}
