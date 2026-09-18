import { describe, expect, it } from 'vitest'
import type { Task } from './types'
import {
  isTaskWaitingOnWorkers,
  taskStageLabelKey,
  taskStatusBadgeClass,
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
    expect(taskStatusBadgeClass(queued)).toBe('badge wait')
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
    expect(taskStatusBadgeClass(running)).toBe('badge warn')
  })

  it('marks missing worker for model pair as config error', () => {
    const stuck = task({ type: 'transcribe', status: 'queued', meta: { stage: 'no_matching_worker' } })
    expect(isTaskWaitingOnWorkers(stuck)).toBe(false)
    expect(taskStageLabelKey(stuck)).toBe('task.workerStage.no_matching_worker')
    expect(taskStatusBadgeClass(stuck)).toBe('badge err')
  })
})
