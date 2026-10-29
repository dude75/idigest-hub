import { describe, expect, it } from 'vitest'
import {
  agreementText,
  appAdminLead,
  appEntityTitle,
  appFieldCaption,
  appImpactRowLabel,
  appImpactTagMuted,
  appLandingLead,
  appMetricLabel,
  appMuted,
  appMutedText,
  appPrimaryText,
  appToneEyebrow,
  hubReadingSurface,
  summaryBody,
} from './typography'

describe('typography class tokens', () => {
  it('exports stable hub UI reading surface classes', () => {
    expect(hubReadingSurface).toBe('hub-reading-surface')
    expect(summaryBody).toBe('summary-body')
    expect(agreementText).toBe('agreement-text')
  })

  it('re-exports app chrome typography tokens', () => {
    expect(appPrimaryText).toContain('text-base')
    expect(appPrimaryText).toContain('font-medium')
    expect(appMutedText).toBe('text-sm text-muted-foreground')
    expect(appMuted).toBe('text-muted-foreground')
    expect(appAdminLead).toContain('text-base')
    expect(appEntityTitle).toContain('font-semibold')
    expect(appFieldCaption).toContain('text-xs')
    expect(appMetricLabel).toContain('font-medium')
    expect(appLandingLead).toContain('text-[1.08rem]')
    expect(appLandingLead).toContain('text-muted-foreground')
    expect(appToneEyebrow).toContain('uppercase')
    expect(appToneEyebrow).toContain('text-xs')
    expect(appImpactRowLabel).toContain('text-[0.8rem]')
    expect(appImpactTagMuted).toContain('text-[0.72rem]')
  })
})
