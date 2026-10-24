export { PROFILE_TELEGRAM_SECTION_ID } from '../../shell/constants'

export const PROFILE_TABS = ['general', 'models', 'security', 'data', 'ui'] as const
export type ProfileTab = (typeof PROFILE_TABS)[number]

export function resolveProfileTab(raw: string | null): ProfileTab {
  if (raw && (PROFILE_TABS as readonly string[]).includes(raw)) return raw as ProfileTab
  return 'general'
}
