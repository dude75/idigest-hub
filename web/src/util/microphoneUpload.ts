import type { NavigateFunction } from 'react-router-dom'
import { api, apiUpload } from '../api'
import { MIC_RECORDING_TAG } from '../constants/userTags'
import {
  beginPipelineRun,
  endPipelineRun,
  pipelineNavState,
  pipelineShouldTranscribe,
  transcribeRequest,
} from '../pipeline'
import { libraryPath } from '../routes'
import type { SchemaObjectTagsResponse, SchemaUserTagBrief } from '../openapi'
import type { Audio, Me, Task } from '../types'
import { showError } from '../util'

export async function tagMicrophoneRecording(audioId: string): Promise<SchemaUserTagBrief[]> {
  const r = await api<SchemaObjectTagsResponse>('/object-tags', {
    method: 'PUT',
    body: JSON.stringify({
      object_type: 'audio',
      object_id: audioId,
      tags: [MIC_RECORDING_TAG],
    }),
  })
  return r.tags ?? []
}

export type MicrophoneUploadProgress = {
  name: string
  percent: number
  phase: 'uploading' | 'processing'
}

type UploadMicOptions = {
  onProgress?: (progress: MicrophoneUploadProgress) => void
  afterUpload?: (item: Audio) => void | Promise<void>
}

export async function uploadMicrophoneRecording(
  file: File,
  navigate: NavigateFunction,
  options?: UploadMicOptions,
  me?: Me | null,
): Promise<Audio> {
  const pipeline = beginPipelineRun()
  const body = new FormData()
  body.append('file', file)
  body.append('from_microphone', 'true')

  const item = await apiUpload<Audio>('/audios', body, (loaded, total) => {
    if (!options?.onProgress) return
    const percent = total ? Math.round((loaded / total) * 100) : 0
    options.onProgress({
      name: file.name,
      percent,
      phase: percent >= 100 ? 'processing' : 'uploading',
    })
  })

  try {
    item.user_tags = await tagMicrophoneRecording(item.id)
  } catch (e) {
    showError(e)
  }

  if (pipelineShouldTranscribe(pipeline)) {
    const task = await api<Task>('/tasks/transcribe', {
      method: 'POST',
      body: JSON.stringify(transcribeRequest(item.id, pipeline, me)),
    })
    navigate(`/app/task/${task.task_id}`, { state: pipelineNavState(pipeline, task) })
    return item
  }

  endPipelineRun()
  navigate(libraryPath('audio'))
  await options?.afterUpload?.(item)
  return item
}
