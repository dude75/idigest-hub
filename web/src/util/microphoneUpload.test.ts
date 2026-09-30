import { beforeEach, describe, expect, it, vi } from 'vitest'
import { endPipelineRun, savePipeline } from '../pipeline'
import { uploadMicrophoneRecording } from './microphoneUpload'

const navigate = vi.fn()

vi.mock('../api', () => ({
  api: vi.fn(),
  apiUpload: vi.fn(),
}))

vi.mock('../util', () => ({
  showError: vi.fn(),
}))

import { api, apiUpload } from '../api'

const mockApi = vi.mocked(api)
const mockUpload = vi.mocked(apiUpload)

describe('uploadMicrophoneRecording', () => {
  beforeEach(() => {
    endPipelineRun()
    localStorage.clear()
    navigate.mockReset()
    mockApi.mockReset()
    mockUpload.mockReset()
  })

  it('uploads, tags mic, and navigates to library when transcribe is off', async () => {
    endPipelineRun()
    mockUpload.mockResolvedValue({ id: 'audio-1', filename: 'rec.webm' } as never)
    mockApi.mockResolvedValue({ tags: [] } as never)

    const file = new File(['x'], 'rec.webm', { type: 'audio/webm' })
    await uploadMicrophoneRecording(file, navigate)

    expect(mockUpload).toHaveBeenCalled()
    expect(mockApi).toHaveBeenCalledWith('/object-tags', expect.objectContaining({ method: 'PUT' }))
    expect(navigate).toHaveBeenCalledWith('/app/library/audio')
  })

  it('starts transcribe task when pipeline requests it', async () => {
    savePipeline({ transcribe: true, skillIds: [] })
    mockUpload.mockResolvedValue({ id: 'audio-2', filename: 'rec.webm' } as never)
    mockApi
      .mockResolvedValueOnce({ tags: [] } as never)
      .mockResolvedValueOnce({ task_id: 'task-9' } as never)

    const file = new File(['x'], 'rec.webm', { type: 'audio/webm' })
    await uploadMicrophoneRecording(file, navigate)

    expect(mockApi).toHaveBeenCalledWith('/tasks/transcribe', expect.objectContaining({ method: 'POST' }))
    expect(navigate).toHaveBeenCalledWith('/app/task/task-9', expect.objectContaining({ state: expect.any(Object) }))
  })
})
