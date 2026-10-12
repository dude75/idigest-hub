import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Film, Link2, Video } from 'lucide-react'
import { cn } from '@/lib/utils'
import { ingestLinkFieldMode, ingestLinkUrlLooksInvalid } from '../util/captureHost'
import { ingestStudioHitSurfaceClassName } from './ingestStudioHitSurface'

type Props = {
  value: string
  placeholder: string
  disabled?: boolean
  className?: string
  onChange: (value: string) => void
  onSubmit?: () => void
  onInvalidBlur?: () => void
}

export function IngestStudioLinkField({
  value,
  placeholder,
  disabled,
  className,
  onChange,
  onSubmit,
  onInvalidBlur,
}: Props) {
  const { t } = useTranslation()
  const [focused, setFocused] = useState(false)
  const mode = ingestLinkFieldMode(value)
  const showIcon = !focused && !value.trim()
  const invalid = ingestLinkUrlLooksInvalid(value)

  const Icon = mode === 'meeting' ? Video : mode === 'import' ? Film : Link2

  return (
    <div
      className={cn(
        ingestStudioHitSurfaceClassName(),
        focused && 'ingest-studio-link-zone-focus',
        invalid && 'ingest-studio-link-zone-invalid',
        className,
      )}
    >
      {showIcon ? (
        <Icon
          className="ingest-studio-hit-surface-icon pointer-events-none"
          strokeWidth={1.25}
          aria-hidden="true"
        />
      ) : null}
      <textarea
        className="ingest-studio-link-input"
        rows={1}
        value={value}
        placeholder={showIcon ? undefined : placeholder}
        disabled={disabled}
        aria-label={t('library.ingestUrl')}
        aria-invalid={invalid || undefined}
        onChange={(e) => onChange(e.target.value)}
        onFocus={() => setFocused(true)}
        onBlur={() => {
          setFocused(false)
          if (value.trim() && invalid) onInvalidBlur?.()
        }}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault()
            onSubmit?.()
          }
        }}
      />
    </div>
  )
}
