import { useTranslation } from 'react-i18next'
import { cn } from '@/lib/utils'
import { formatAudioTime, fmtMediaTime } from '@/util'
import { appDurationCompactClass, appDurationHumanClass } from './appTypography'

type AppDurationProps = {
  sec: number
  /** `human` — localized phrasing; `compact` — MM:SS for dense numeric UI. */
  variant?: 'human' | 'compact'
  className?: string
}

export function AppDuration({ sec, variant = 'human', className }: AppDurationProps) {
  const { t } = useTranslation()
  const text =
    variant === 'compact' ? fmtMediaTime(sec) : formatAudioTime(sec, t)
  return (
    <span
      className={cn(
        variant === 'compact' ? appDurationCompactClass : appDurationHumanClass,
        className,
      )}
    >
      {text}
    </span>
  )
}
