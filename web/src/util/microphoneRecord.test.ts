import { describe, expect, it } from 'vitest'
import { recordingExtensionForMime, recordingFilenameForMime } from './microphoneRecord'

describe('recordingExtensionForMime', () => {
  it('maps webm mime to .webm', () => {
    expect(recordingExtensionForMime('audio/webm;codecs=opus')).toBe('.webm')
  })

  it('maps mp4 mime to .m4a for Safari', () => {
    expect(recordingExtensionForMime('audio/mp4')).toBe('.m4a')
  })
})

describe('recordingFilenameForMime', () => {
  it('uses matching extension', () => {
    expect(recordingFilenameForMime('audio/mp4')).toMatch(/\.m4a$/)
    expect(recordingFilenameForMime('audio/webm')).toMatch(/\.webm$/)
  })
})
