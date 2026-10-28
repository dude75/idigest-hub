import { describe, expect, it } from 'vitest'
import { agreementText, hubReadingSurface, summaryBody } from './typography'

describe('typography class tokens', () => {
  it('exports stable hub UI reading surface classes', () => {
    expect(hubReadingSurface).toBe('hub-reading-surface')
    expect(summaryBody).toBe('summary-body')
    expect(agreementText).toBe('agreement-text')
  })
})
