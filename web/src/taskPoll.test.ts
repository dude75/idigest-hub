import { describe, expect, it } from 'vitest'
import type { Task } from './types'
import { followUpTaskId, isActiveTaskStatus, isTerminalTaskStatus } from './taskPoll'

const task = (overrides: Partial<Task> = {}): Task => ({
  task_id: 't1',
  type: 'transcribe',
  status: 'queued',
  meta: {},
  transcript_id: null,
  summary_id: null,
  error: null,
  ...overrides,
})

describe('taskPoll helpers', () => {
  it('detects active and terminal statuses', () => {
    expect(isActiveTaskStatus('queued')).toBe(true)
    expect(isActiveTaskStatus('running')).toBe(true)
    expect(isActiveTaskStatus('success')).toBe(false)
    expect(isTerminalTaskStatus('error')).toBe(true)
  })

  it('reads follow_up_task_id from meta', () => {
    expect(followUpTaskId(task())).toBeNull()
    expect(followUpTaskId(task({ meta: { follow_up_task_id: 'next-1' } }))).toBe('next-1')
    expect(followUpTaskId(task({ meta: { follow_up_task_id: '' } }))).toBeNull()
  })
})
