import { describe, expect, it } from 'vitest'
import { isVideoUploadFilename } from './uploadFormats'

describe('isVideoUploadFilename', () => {
  it('detects common video extensions', () => {
    expect(isVideoUploadFilename('a.MP4')).toBe(true)
    expect(isVideoUploadFilename('path/to/clip.mov')).toBe(true)
  })

  it('returns false for audio', () => {
    expect(isVideoUploadFilename('clip.wav')).toBe(false)
    expect(isVideoUploadFilename('clip.mp3')).toBe(false)
  })
})
