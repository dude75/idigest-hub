import { describe, expect, it } from 'vitest'
import type { Task } from './types'
import {
  canCancelTask,
  isTaskWaitingOnWorkers,
  taskStageLabelKey,
  taskStatusBadgeTone,
} from './taskStage'

function task(partial: Partial<Task> & Pick<Task, 'type' | 'status'>): Task {
  return {
    task_id: 't1',
    ...partial,
  } as Task
}

describe('taskStage', () => {
  it('detects hub queue wait', () => {
    const queued = task({ type: 'transcribe', status: 'queued', meta: { stage: 'queued' } })
    expect(isTaskWaitingOnWorkers(queued)).toBe(true)
    expect(taskStageLabelKey(queued)).toBe('task.workerStage.queued')
    expect(taskStatusBadgeTone(queued)).toBe('pending')
  })

  it('detects engine and queue_full waits', () => {
    expect(isTaskWaitingOnWorkers(task({ type: 'summarize', status: 'queued', meta: { stage: 'waiting_engine' } }))).toBe(true)
    expect(isTaskWaitingOnWorkers(task({ type: 'summarize', status: 'queued', meta: { stage: 'queue_full' } }))).toBe(true)
  })

  it('treats worker-side queue as waiting', () => {
    const onWorker = task({ type: 'transcribe', status: 'running', meta: { stage: 'queued' } })
    expect(isTaskWaitingOnWorkers(onWorker)).toBe(true)
    expect(taskStageLabelKey(onWorker)).toBe('task.workerStage.worker_queue')
  })

  it('treats active worker processing as not waiting', () => {
    const running = task({ type: 'transcribe', status: 'running', meta: { stage: 'running' } })
    expect(isTaskWaitingOnWorkers(running)).toBe(false)
    expect(taskStageLabelKey(running)).toBe('task.pipeline.transcribing')
    expect(taskStatusBadgeTone(running)).toBe('pending')
  })

  it('marks missing worker for model pair as config error', () => {
    const stuck = task({ type: 'transcribe', status: 'queued', meta: { stage: 'no_matching_worker' } })
    expect(isTaskWaitingOnWorkers(stuck)).toBe(false)
    expect(taskStageLabelKey(stuck)).toBe('task.workerStage.no_matching_worker')
    expect(taskStatusBadgeTone(stuck)).toBe('warning')
  })

  it('allows cancel while hub-queued transcribe waits for a worker', () => {
    const waiting = task({ type: 'transcribe', status: 'queued', meta: { stage: 'queued' } })
    expect(canCancelTask(waiting)).toBe(true)
  })

  it('disallows cancel once transcribe is running on a worker', () => {
    const onWorker = task({ type: 'transcribe', status: 'running', meta: { stage: 'queued' } })
    expect(canCancelTask(onWorker)).toBe(false)
    expect(canCancelTask(task({ type: 'transcribe', status: 'running', meta: { stage: 'running' } }))).toBe(false)
  })

  it('allows cancel for active import and capture tasks', () => {
    expect(canCancelTask(task({ type: 'import', status: 'running', meta: {} }))).toBe(true)
    expect(canCancelTask(task({ type: 'capture', status: 'queued', meta: {} }))).toBe(true)
  })
})
