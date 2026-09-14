import { beforeEach, describe, expect, it } from 'vitest'
import type { Task } from './types'
import {
  beginPipelineRun,
  endPipelineRun,
  initialTaskFromNav,
  pipelineNavState,
} from './pipeline'

const sampleTask = (taskId: string): Task => ({
  task_id: taskId,
  type: 'transcribe',
  status: 'queued',
  meta: { stage: 'queued' },
  transcript_id: null,
  summary_id: null,
  error: null,
})

describe('pipelineNavState', () => {
  beforeEach(() => {
    endPipelineRun()
  })

  it('includes the task passed from create endpoints', () => {
    beginPipelineRun({ transcribe: true, skillIds: [] })
    const task = sampleTask('task-1')
    const state = pipelineNavState({ transcribe: true, skillIds: [] }, task)
    expect(state.task).toEqual(task)
    expect(state.pipeline.transcribe).toBe(true)
  })

  it('omits task when not provided', () => {
    beginPipelineRun({ transcribe: true, skillIds: ['skill-1'] })
    const state = pipelineNavState({ transcribe: true, skillIds: ['skill-1'] })
    expect(state.task).toBeUndefined()
  })
})

describe('initialTaskFromNav', () => {
  it('returns the task when ids match', () => {
    const task = sampleTask('task-42')
    expect(initialTaskFromNav({ pipeline: { transcribe: true, skillIds: [] }, task }, 'task-42')).toBe(task)
  })

  it('returns null when nav state is missing', () => {
    expect(initialTaskFromNav(null, 'task-42')).toBeNull()
    expect(initialTaskFromNav(undefined, 'task-42')).toBeNull()
  })

  it('returns null when task id differs from route param', () => {
    const task = sampleTask('task-42')
    expect(initialTaskFromNav({ pipeline: { transcribe: true, skillIds: [] }, task }, 'other')).toBeNull()
  })

  it('returns null when route param is missing', () => {
    const task = sampleTask('task-42')
    expect(initialTaskFromNav({ pipeline: { transcribe: true, skillIds: [] }, task }, undefined)).toBeNull()
  })
})
