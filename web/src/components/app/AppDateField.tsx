import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { format, isValid, parse } from 'date-fns'
import { enUS, es, ru } from 'date-fns/locale'
import { CalendarIcon } from 'lucide-react'
import { enUS as rdpEnUS, es as rdpEs, ru as rdpRu } from 'react-day-picker/locale'
import { useTranslation } from 'react-i18next'

import { Calendar } from '@/components/ui/calendar'
import { Button } from '@/components/ui/button'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { cn } from '@/lib/utils'

import { AppField } from './AppField'

function parseDay(value: string): Date | undefined {
  if (!value) return undefined
  const d = parse(value, 'yyyy-MM-dd', new Date())
  return isValid(d) ? d : undefined
}

function toDayString(d: Date): string {
  return format(d, 'yyyy-MM-dd')
}

function localesFor(lang: string) {
  if (lang.startsWith('ru')) {
    return { df: ru, rdp: rdpRu }
  }
  if (lang.startsWith('es')) {
    return { df: es, rdp: rdpEs }
  }
  return { df: enUS, rdp: rdpEnUS }
}

type AppDateFieldProps = {
  label: ReactNode
  htmlFor: string
  value: string
  onChange: (value: string) => void
  className?: string
}

export function AppDateField({ label, htmlFor, value, onChange, className }: AppDateFieldProps) {
  const { t, i18n } = useTranslation()
  const [open, setOpen] = useState(false)
  const [timeZone, setTimeZone] = useState<string | undefined>(undefined)
  const { df, rdp } = useMemo(() => localesFor(i18n.language), [i18n.language])
  const selected = parseDay(value)

  useEffect(() => {
    setTimeZone(Intl.DateTimeFormat().resolvedOptions().timeZone)
  }, [])

  return (
    <AppField label={label} htmlFor={htmlFor}>
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger
          id={htmlFor}
          render={
            <Button
              variant="outline"
              data-empty={!selected}
              className={cn(
                'w-full justify-start gap-2 text-left font-normal data-[empty=true]:text-muted-foreground',
                className,
              )}
            />
          }
        >
          <CalendarIcon className="size-4 shrink-0 opacity-70" />
          {selected ? (
            <span className="truncate">{format(selected, 'PPP', { locale: df })}</span>
          ) : (
            <span className="truncate">{t('common.pickDate')}</span>
          )}
        </PopoverTrigger>
        <PopoverContent className="w-auto p-0" align="start">
          <Calendar
            mode="single"
            locale={rdp}
            timeZone={timeZone}
            selected={selected}
            defaultMonth={selected}
            onSelect={(day) => {
              if (!day) return
              onChange(toDayString(day))
              setOpen(false)
            }}
          />
        </PopoverContent>
      </Popover>
    </AppField>
  )
}
