import { useTranslation } from 'react-i18next'
import { Label } from '@/components/ui/label'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { cn } from '@/lib/utils'
import type { SchemaSkillPublicResponse } from '../openapi'
import { skillScopeLabel } from '../skillScope'
import { HubBadge } from './app/AdminUi'

export type SummarizeSkillOption = Pick<SchemaSkillPublicResponse, 'id' | 'name' | 'scope' | 'catalog'>

const NONE_SENTINEL = '__none__'

export type SummarizeSkillRadioGroupProps = {
  skills: SummarizeSkillOption[]
  /** Selected skill id, or null when the “none” row is chosen or nothing is selected. */
  value: string | null
  onValueChange: (skillId: string | null) => void
  /** When true, first row skips summarize (transcribe-only pipeline). */
  showNoneOption?: boolean
  noneLabelKey?: string
  idPrefix: string
  className?: string
  rowClassName?: string
  'aria-labelledby'?: string
}

export function SummarizeSkillRadioGroup({
  skills,
  value,
  onValueChange,
  showNoneOption = false,
  noneLabelKey = 'library.pipeline.summarizeSkillNone',
  idPrefix,
  className,
  rowClassName,
  'aria-labelledby': ariaLabelledBy,
}: SummarizeSkillRadioGroupProps) {
  const { t } = useTranslation()
  const groupValue = value ?? (showNoneOption ? NONE_SENTINEL : '')

  return (
    <RadioGroup
      className={className}
      aria-labelledby={ariaLabelledBy}
      value={groupValue}
      onValueChange={(next) => {
        if (next === NONE_SENTINEL) {
          onValueChange(null)
          return
        }
        onValueChange(next.length > 0 ? next : null)
      }}
    >
      {showNoneOption ? (
        <div className={cn('flex items-center gap-2', rowClassName)}>
          <RadioGroupItem value={NONE_SENTINEL} id={`${idPrefix}-none`} />
          <Label htmlFor={`${idPrefix}-none`} className="font-normal">
            {t(noneLabelKey)}
          </Label>
        </div>
      ) : null}
      {skills.map((s) => (
        <div key={s.id} className={cn('flex items-center gap-2', rowClassName)}>
          <RadioGroupItem value={s.id} id={`${idPrefix}-${s.id}`} />
          <Label htmlFor={`${idPrefix}-${s.id}`} className="font-normal">
            {s.name}{' '}
            <HubBadge tone="muted" className="align-middle">
              {skillScopeLabel(s.scope, s.catalog, t)}
            </HubBadge>
          </Label>
        </div>
      ))}
    </RadioGroup>
  )
}
