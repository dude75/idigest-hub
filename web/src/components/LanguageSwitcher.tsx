import { useTranslation } from 'react-i18next'
import { useAuth } from '../auth'
import { LOCALES } from '../i18n'
import type { Locale } from '../types'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

export function LanguageSwitcher() {
  const { i18n, t } = useTranslation()
  const { setLocale } = useAuth()
  return (
    <div
      className="lang inline-flex items-center gap-0.5 rounded-lg border border-border bg-muted/50 p-0.5"
      role="group"
      aria-label="language"
    >
      {LOCALES.map((lng) => {
        const active = i18n.language === lng
        return (
          <Button
            key={lng}
            type="button"
            variant={active ? 'default' : 'ghost'}
            size="xs"
            className={cn('min-w-[2.1rem] px-2 font-semibold tracking-wide', !active && 'text-muted-foreground')}
            aria-pressed={active}
            onClick={() => void setLocale(lng as Locale)}
          >
            {t(`lang.${lng}`)}
          </Button>
        )
      })}
    </div>
  )
}
