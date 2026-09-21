import { describe, expect, it } from 'vitest'
import type { Task } from './types'
import {
  buildPipelineSteps,
  pipelineStepStatus,
  shouldShowPipelineProgress,
} from './components/PipelineProgress'

const transcribeTask = (status: string): Task => ({
  task_id: 't1',
  type: 'transcribe',
  status,
  meta: {},
  transcript_id: null,
  summary_id: null,
  error: null,
})

const captureTask = (status: string, stage?: string): Task => ({
  task_id: 'c1',
  type: 'capture',
  status,
  meta: stage ? { stage } : {},
  transcript_id: null,
  summary_id: null,
  error: null,
})

describe('buildPipelineSteps', () => {
  it('builds capture → transcribe for meeting ingest', () => {
    const steps = buildPipelineSteps({ transcribe: true, skillIds: [] }, false, captureTask('running'))
    expect(steps.map((s) => s.id)).toEqual(['capture', 'transcribe'])
  })

  it('builds import → transcribe → summarize chain', () => {
    const steps = buildPipelineSteps({ transcribe: true, skillIds: ['s1'] }, true)
    expect(steps.map((s) => s.id)).toEqual(['import', 'transcribe', 'summarize'])
  })

  it('builds transcribe-only steps for uploads', () => {
    const steps = buildPipelineSteps({ transcribe: true, skillIds: [] }, false)
    expect(steps.map((s) => s.id)).toEqual(['transcribe'])
  })
})

describe('shouldShowPipelineProgress', () => {
  it('shows a single transcribe step during an active pipeline run', () => {
    const steps = buildPipelineSteps({ transcribe: true, skillIds: [] }, false)
    expect(shouldShowPipelineProgress(steps, true)).toBe(true)
  })

  it('hides a single transcribe step outside a pipeline run', () => {
    const steps = buildPipelineSteps({ transcribe: true, skillIds: [] }, false)
    expect(shouldShowPipelineProgress(steps, false)).toBe(false)
  })

  it('shows multi-step pipelines even outside a run', () => {
    const steps = buildPipelineSteps({ transcribe: true, skillIds: ['s1'] }, true)
    expect(shouldShowPipelineProgress(steps, false)).toBe(true)
  })
})

describe('pipelineStepStatus', () => {
  it('marks the current transcribe step waiting while queued for a worker', () => {
    const steps = buildPipelineSteps({ transcribe: true, skillIds: [] }, false)
    const task = transcribeTask('queued')
    expect(pipelineStepStatus('transcribe', task, steps)).toBe('waiting')
  })

  it('marks import done once transcribe is running on worker', () => {
    const steps = buildPipelineSteps({ transcribe: true, skillIds: [] }, true)
    const task: Task = { ...transcribeTask('running'), meta: { stage: 'running' } }
    expect(pipelineStepStatus('import', task, steps)).toBe('done')
    expect(pipelineStepStatus('transcribe', task, steps)).toBe('active')
  })
})
