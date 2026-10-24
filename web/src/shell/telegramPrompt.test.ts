import { describe, expect, it } from 'vitest'
import type { Me } from '../types'
import { shellShowsTelegramPrompt } from './telegramPrompt'

const baseMe = {
  user: {
    shell_show_telegram_link: true,
  },
  org: { id: 'org-1' },
} as Me

describe('shellShowsTelegramPrompt', () => {
  it('is false without org member context', () => {
    expect(shellShowsTelegramPrompt(null, { bot_enabled: true, linked: false } as const)).toBe(false)
  })

  it('is false when user hides the prompt', () => {
    const me = {
      ...baseMe,
      user: { ...baseMe.user, shell_show_telegram_link: false },
    } as Me
    expect(shellShowsTelegramPrompt(me, { bot_enabled: true, linked: false } as const)).toBe(false)
  })

  it('is false when linked or bot disabled', () => {
    expect(
      shellShowsTelegramPrompt(baseMe, { bot_enabled: true, linked: true } as const),
    ).toBe(false)
    expect(
      shellShowsTelegramPrompt(baseMe, { bot_enabled: false, linked: false } as const),
    ).toBe(false)
  })

  it('is true when prompt allowed and not linked', () => {
    expect(
      shellShowsTelegramPrompt(baseMe, { bot_enabled: true, linked: false } as const),
    ).toBe(true)
  })
})
