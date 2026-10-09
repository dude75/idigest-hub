import { describe, expect, it } from 'vitest'
import {
  captureMeetingNeedsPin,
  ingestLinkFieldMode,
  isImportVideoUrl,
  isMeetingCaptureUrl,
  isTelemostCaptureUrl,
  meetingRoomPath,
  normalizeJitsiHostInput,
  shouldRouteImportUrlToCapture,
} from './captureHost'

describe('meetingRoomPath', () => {
  it('returns last path segment for meeting URLs', () => {
    expect(meetingRoomPath('https://meet.example.com/room/abc-def')).toBe('abc-def')
  })

  it('returns last segment for video watch URLs', () => {
    expect(meetingRoomPath('https://youtube.com/watch?v=x')).toBe('watch')
  })
})

describe('isTelemostCaptureUrl', () => {
  it('accepts telemost guest links', () => {
    expect(isTelemostCaptureUrl('https://telemost.yandex.ru/j/abc123')).toBe(true)
  })

  it('rejects unknown hosts', () => {
    expect(isTelemostCaptureUrl('https://meet.jit.si/room')).toBe(false)
  })
})

describe('shouldRouteImportUrlToCapture', () => {
  it('routes telemost when capture enabled', () => {
    expect(shouldRouteImportUrlToCapture('https://telemost.yandex.ru/j/x', true)).toBe(true)
    expect(shouldRouteImportUrlToCapture('https://telemost.yandex.ru/j/x', false)).toBe(false)
  })

  it('does not route youtube to capture', () => {
    expect(shouldRouteImportUrlToCapture('https://www.youtube.com/watch?v=abc', true)).toBe(false)
  })
})

describe('captureMeetingNeedsPin', () => {
  it('needs pin for jitsi-like hosts, not telemost', () => {
    expect(captureMeetingNeedsPin('https://meet.jit.si/MyRoom', true)).toBe(true)
    expect(captureMeetingNeedsPin('https://telemost.yandex.ru/j/x', true)).toBe(false)
  })
})

describe('ingestLinkFieldMode', () => {
  it('classifies meeting and video URLs', () => {
    expect(ingestLinkFieldMode('')).toBe('idle')
    expect(ingestLinkFieldMode('https://meet.jit.si/MyRoom')).toBe('meeting')
    expect(ingestLinkFieldMode('https://www.youtube.com/watch?v=abc')).toBe('import')
  })
})

describe('isMeetingCaptureUrl', () => {
  it('detects jitsi rooms without capture flag', () => {
    expect(isMeetingCaptureUrl('https://meet.jit.si/MyRoom')).toBe(true)
    expect(isMeetingCaptureUrl('https://www.youtube.com/watch?v=abc')).toBe(false)
  })
})

describe('isImportVideoUrl', () => {
  it('detects known video hosts', () => {
    expect(isImportVideoUrl('https://youtu.be/abc')).toBe(true)
    expect(isImportVideoUrl('https://meet.jit.si/MyRoom')).toBe(false)
  })
})

describe('normalizeJitsiHostInput', () => {
  it('extracts hostname from pasted URLs', () => {
    expect(normalizeJitsiHostInput('https://meet.jit.si/MyRoom')).toBe('meet.jit.si')
  })

  it('strips www prefix', () => {
    expect(normalizeJitsiHostInput('www.meet.example.com')).toBe('meet.example.com')
  })
})
