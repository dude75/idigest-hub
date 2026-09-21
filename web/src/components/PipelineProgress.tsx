import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { activePipeline, loadPipelineRun, type IngestPipeline } from '../pipeline'
import { isTaskProcessingOnWorker, isTaskWaitingOnWorkers } from '../taskStage'
import type { Task } from '../types'

export type PipelineStepId = 'import' | 'capture' | 'transcribe' | 'summarize'

export type PipelineStep = {
  id: PipelineStepId
  labelKey: string
}

export function pipelineIngestStepId(task: Task | null, showImport: boolean): PipelineStepId | null {
  if (task?.type === 'capture') return 'capture'
  if (showImport || task?.type === 'import') return 'import'
  return null
}

export function buildPipelineSteps(
  pipeline: IngestPipeline,
  showImport: boolean,
  task: Task | null = null,
): PipelineStep[] {
  const steps: PipelineStep[] = []
  const ingestId = pipelineIngestStepId(task, showImport)
  if (ingestId === 'capture') steps.push({ id: 'capture', labelKey: 'task.type.capture' })
  else if (ingestId === 'import') steps.push({ id: 'import', labelKey: 'task.type.import' })
  if (pipeline.transcribe) steps.push({ id: 'transcribe', labelKey: 'task.type.transcribe' })
  if (pipeline.skillIds.length > 0) steps.push({ id: 'summarize', labelKey: 'task.type.summarize' })
  return steps
}

function pipelineCurrentStepId(task: Task): PipelineStepId {
  if (task.type === 'capture') return 'capture'
  if (task.type === 'import') return 'import'
  if (task.type === 'summarize') return 'summarize'
  return 'transcribe'
}

export function pipelineStepStatus(
  step: PipelineStepId,
  task: Task | null,
  steps: PipelineStep[],
): 'pending' | 'waiting' | 'active' | 'done' {
  if (!task) return 'pending'
  const idx = steps.findIndex((s) => s.id === step)
  const currentIdx = steps.findIndex((s) => s.id === pipelineCurrentStepId(task))
  if (currentIdx < 0) {
    if (task.status === 'success') return 'done'
    return 'pending'
  }
  if (idx < currentIdx) return 'done'
  if (idx > currentIdx) return 'pending'
  if (task.status === 'success') return 'done'
  if (isTaskWaitingOnWorkers(task)) return 'waiting'
  if (task.status === 'queued' || task.status === 'running') {
    if (task.type === 'import' || task.type === 'capture') return 'active'
    if (isTaskProcessingOnWorker(task) || task.status === 'running') return 'active'
    return 'waiting'
  }
  return 'pending'
}

export function shouldShowPipelineProgress(steps: PipelineStep[], inPipelineRun: boolean): boolean {
  if (steps.length === 0) return false
  if (steps.length <= 1 && !inPipelineRun) return false
  return true
}

export function PipelineProgress({ task }: { task: Task | null }) {
  const { t } = useTranslation()
  const pipeline = activePipeline()
  const [showImport, setShowImport] = useState(
    () => task?.type === 'import' || task?.type === 'capture',
  )

  useEffect(() => {
    if (task?.type === 'import' || task?.type === 'capture') setShowImport(true)
  }, [task?.type])

  const steps = buildPipelineSteps(pipeline, showImport, task)
  const inPipelineRun = loadPipelineRun() !== null

  if (!shouldShowPipelineProgress(steps, inPipelineRun)) return null

  return (
    <ol className="pipeline-progress" aria-label={t('task.pipeline.title')}>
      {steps.map((step, i) => {
        const status = pipelineStepStatus(step.id, task, steps)
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
