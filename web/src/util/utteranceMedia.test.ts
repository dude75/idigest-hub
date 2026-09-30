import { describe, expect, it } from 'vitest'
import {
  parseTimestampFromText,
  utteranceDisplayText,
  utteranceStart,
  utteranceTimeLabel,
} from './utteranceMedia'
import type { Utterance } from '../types'

describe('parseTimestampFromText', () => {
  it('parses bracket timestamps', () => {
    expect(parseTimestampFromText('[01:02:03] Hello')).toEqual({ seconds: 3723, rest: 'Hello' })
  })

  it('parses plain timestamps', () => {
    expect(parseTimestampFromText('0:05 speech')).toEqual({ seconds: 5, rest: 'speech' })
  })
})

describe('utteranceStart', () => {
  it('prefers numeric start field', () => {
    expect(utteranceStart({ text: 'x', start: 12 } as Utterance)).toBe(12)
  })

  it('falls back to text timestamp', () => {
    expect(utteranceStart({ text: '[00:01:00] hi' } as Utterance)).toBe(60)
  })
})

describe('utteranceDisplayText', () => {
  it('strips leading timestamp from text', () => {
    expect(utteranceDisplayText({ text: '[00:00:05] word' } as Utterance)).toBe('word')
  })
})

describe('utteranceTimeLabel', () => {
  it('formats start time', () => {
    expect(utteranceTimeLabel({ text: 't', start: 65 } as Utterance)).toBe('01:05')
  })
})
