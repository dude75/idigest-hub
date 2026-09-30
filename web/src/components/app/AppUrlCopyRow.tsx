import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { AppHoverHint } from '@/components/app/AppHoverHint'
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

function UrlCodeValue({
  value,
  display,
  id,
  className,
}: {
  value: string
  display: string
  id?: string
  className: string
}) {
  const code = (
    <code className={cn(className, value && 'cursor-help')} id={id}>
      {display}
    </code>
  )
  if (!value) {
    return code
  }
  return (
    <AppHoverHint content={value} contentClassName="max-w-md break-all font-normal">
      {code}
    </AppHoverHint>
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
        <UrlCodeValue value={value} display={display} id={id} className="sso-url-value" />
        <CopyButton text={value} disabled={disabled} />
      </div>
    )
  }

  return (
    <div className={cn('public-link-url-row', className)}>
      <UrlCodeValue value={value} display={display} id={id} className="public-link-url" />
      <CopyButton text={value} disabled={disabled} />
    </div>
  )
}
