import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

type Props = {
  value: string
  id?: string
  label?: string
  emptyDisplay?: string
  disabled?: boolean
  className?: string
}

function CopyButton({ text, disabled }: { text: string; disabled?: boolean }) {
  const { t } = useTranslation()
  const [copied, setCopied] = useState(false)

  async function copy() {
    if (!text || disabled) return
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1500)
    } catch {
      /* clipboard unavailable */
    }
  }

  return (
    <Button
      type="button"
      size="sm"
      variant="secondary"
      className="public-link-copy"
      disabled={disabled || !text}
      onClick={() => void copy()}
    >
      {copied ? t('profile.copied') : t('common.copy')}
    </Button>
  )
}

/** Monospace value + copy — inline (`public-link-url-row`) or labeled SSO grid row. */
export function AppUrlCopyRow({
  value,
  id,
  label,
  emptyDisplay = '—',
  disabled,
  className,
}: Props) {
  const display = value || emptyDisplay

  if (label) {
    return (
      <div className={cn('sso-url-row', className)}>
        <span className="sso-url-label">{label}</span>
        <code className="sso-url-value" title={value || undefined} id={id}>
          {display}
        </code>
        <CopyButton text={value} disabled={disabled} />
      </div>
    )
  }

  return (
    <div className={cn('public-link-url-row', className)}>
      <code className="public-link-url" title={value || undefined} id={id}>
        {display}
      </code>
      <CopyButton text={value} disabled={disabled} />
    </div>
  )
}
