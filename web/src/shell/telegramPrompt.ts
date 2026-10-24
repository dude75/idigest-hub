import type { SchemaMeTelegramStatusResponse } from '../openapi'
import type { Me } from '../types'

/** Floating shell Telegram icon (prompt to link), not the bot settings block. */
export function shellShowsTelegramPrompt(
  me: Me | null,
  status: SchemaMeTelegramStatusResponse | null,
): boolean {
  return Boolean(
    me?.org &&
      (me.user.shell_show_telegram_link ?? true) &&
      status?.bot_enabled &&
      !status.linked,
  )
}
