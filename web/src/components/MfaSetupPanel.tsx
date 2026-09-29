import { useState, type ComponentType, type FormEvent, type SVGProps } from 'react'
import { useTranslation } from 'react-i18next'
import QRCodeImport from 'react-qr-code'
import { api } from '../api'
import { showError } from '../util'
import { AuthField } from './auth/AuthField'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { AppSubmitButton } from './app/AdminUi'
import { AppUrlCopyRow } from './app/AppUrlCopyRow'

type QRCodeProps = SVGProps<SVGSVGElement> & {
  value: string
  size?: number
  bgColor?: string
  fgColor?: string
  level?: 'L' | 'M' | 'H' | 'Q'
}

/** Vite may load react-qr-code as `{ default, QRCode }` instead of the component. */
function resolveQrCode(mod: unknown): ComponentType<QRCodeProps> {
  if (mod && typeof mod === 'object' && '$$typeof' in mod) return mod as ComponentType<QRCodeProps>
  if (mod && typeof mod === 'object' && 'default' in mod) {
    const inner = (mod as { default: unknown }).default
    if (inner && typeof inner === 'object' && '$$typeof' in inner) return inner as ComponentType<QRCodeProps>
  }
  return mod as ComponentType<QRCodeProps>
}

const QRCode = resolveQrCode(QRCodeImport)

type Props = {
  onComplete: () => void | Promise<void>
}

export function MfaSetupPanel({ onComplete }: Props) {
  const { t } = useTranslation()
  const [secret, setSecret] = useState<string | null>(null)
  const [otpauthUri, setOtpauthUri] = useState<string | null>(null)
  const [code, setCode] = useState('')
  const [recoveryCodes, setRecoveryCodes] = useState<string[] | null>(null)
  const [busy, setBusy] = useState(false)
  async function startSetup() {
    setBusy(true)
    try {
      const row = await api<{ secret: string; otpauth_uri: string }>('/auth/mfa/setup/start', { method: 'POST' })
      setSecret(row.secret)
      setOtpauthUri(row.otpauth_uri)
    } catch (e) {
      showError(e)
    } finally {
      setBusy(false)
    }
  }

  function downloadRecoveryCodes(codes: string[]) {
    const stamp = new Date().toISOString().slice(0, 10)
    const body = [
      t('mfa.recoveryDownloadHeader'),
      '',
      t('mfa.recoverySave'),
      '',
      ...codes,
      '',
    ].join('\n')
    const blob = new Blob([body], { type: 'text/plain;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `idigest-2fa-recovery-${stamp}.txt`
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
  }

  async function confirmSetup(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    try {
      const row = await api<{ recovery_codes: string[] }>('/auth/mfa/setup/confirm', {
        method: 'POST',
        body: JSON.stringify({ code: code.trim() }),
      })
      setRecoveryCodes(row.recovery_codes)
    } catch (err) {
      showError(err)
    } finally {
      setBusy(false)
    }
  }

  if (recoveryCodes) {
    return (
      <div className="flex flex-col gap-3">
        <p className="muted">{t('mfa.recoverySave')}</p>
        <ul className="mfa-recovery-list">
          {recoveryCodes.map((item) => (
            <li key={item}>
              <code>{item}</code>
            </li>
          ))}
        </ul>
        <div className="flex flex-wrap items-center gap-2 mfa-recovery-actions">
          <Button type="button" onClick={() => downloadRecoveryCodes(recoveryCodes)}>
            {t('common.downloadTxt')}
          </Button>
          <Button type="button" onClick={() => void onComplete()}
          >
            {t('common.confirm')}
          </Button>
        </div>
      </div>
    )
  }

  if (secret) {
    return (
      <form className="flex flex-col gap-3" onSubmit={(e) => void confirmSetup(e)}>
        <p className="muted">{t('mfa.setupHint')}</p>
        {otpauthUri && (
          <div className="mfa-qr-block">
            <QRCode
              value={otpauthUri}
              size={200}
              bgColor="#ffffff"
              fgColor="#111827"
              aria-label={t('mfa.qrAlt')}
            />
          </div>
        )}
        <details className="mfa-secret-block">
          <summary className="muted">{t('mfa.manualEntry')}</summary>
          <AppUrlCopyRow value={secret} />
        </details>
        <AuthField label={t('mfa.code')} htmlFor="mfa-setup-code">
          <Input
            id="mfa-setup-code"
            type="text"
            inputMode="numeric"
            autoComplete="one-time-code"
            pattern="[0-9 ]*"
            maxLength={8}
            required
            value={code}
            onChange={(e) => setCode(e.target.value)}
          />
        </AuthField>
        <AppSubmitButton type="submit" ready={code.replace(/\s/g, '').length >= 6} busy={busy}>
          {t('common.confirm')}
        </AppSubmitButton>
      </form>
    )
  }

  return (
    <Button type="button" disabled={busy} onClick={() => void startSetup()}>
      {t('mfa.enable')}
    </Button>
  )
}
