import { useMemo, useState } from 'react'
import { Card, CardContent, CardFooter } from '@/components/ui/card'
import { ProfileCardHeader } from './ProfileCardHeader'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { AppSubmitButton, HubBadge } from '../../components/app/AdminUi'
import { Input } from '@/components/ui/input'
import { AppCheckboxRow, AppInputField } from '../../components/app/AppFormControls'
import { AppUrlCopyRow } from '../../components/app/AppUrlCopyRow'
import { useProfilePage } from './ProfilePageContext'
import { cn } from '@/lib/utils'
import { appMutedText, appStatsEmpty, appFieldCaption } from '../../components/app/appTypography'

export function ProfileDataTab() {
  const {
    t,
    hasOrg,
    apiAllowed,
    tokens,
    activeTokens,
    tokenName,
    setTokenName,
    secret,
    creating,
    createToken,
    tokenTotp,
    setTokenTotp,
    tokenTotpOpen,
    setTokenTotpOpen,
    revoke,
    backupTranscripts,
    setBackupTranscripts,
    backupSummaries,
    setBackupSummaries,
    backupSkills,
    setBackupSkills,
    backupFormat,
    setBackupFormat,
    backingUp,
    restoringUp,
    restoreMessage,
    restoreInputRef,
    downloadBackup,
    restoreBackup,
    canDeleteAccount,
    openDeleteAccount,
    fmtDate,
  } = useProfilePage()

  const [showRevokedTokens, setShowRevokedTokens] = useState(false)
  const revokedTokens = useMemo(() => tokens.filter((tok) => tok.revoked), [tokens])
  const visibleTokens = useMemo(
    () => (showRevokedTokens ? tokens : tokens.filter((tok) => !tok.revoked)),
    [tokens, showRevokedTokens],
  )

  return (
    <div className="profile-data-tab flex flex-col gap-4">
      <div className="profile-data-grid grid gap-4 lg:grid-cols-2">
        {hasOrg && (
          <Card className="admin-form-card profile-backup-card h-full">
            <ProfileCardHeader title={t('profile.backup')} lead={t('profile.backupLead')} />
            <CardContent className="flex flex-1 flex-col gap-3">
              <div className="profile-backup-body">
                <div className="profile-backup-group">
                  <span className={cn(appFieldCaption, 'profile-backup-label')}>{t('profile.backupInclude')}</span>
                  <div className="profile-backup-checks flex flex-col gap-1">
                    <AppCheckboxRow
                      id="profile-backup-transcripts"
                      label={t('library.transcripts')}
                      checked={backupTranscripts}
                      onCheckedChange={setBackupTranscripts}
                    />
                    <AppCheckboxRow
                      id="profile-backup-summaries"
                      label={t('library.summaries')}
                      checked={backupSummaries}
                      onCheckedChange={setBackupSummaries}
                    />
                    <AppCheckboxRow
                      id="profile-backup-skills"
                      label={t('nav.skills')}
                      checked={backupSkills}
                      onCheckedChange={setBackupSkills}
                    />
                  </div>
                </div>
                <div className="profile-backup-group">
                  <span className={cn(appFieldCaption, 'profile-backup-label')} id="profile-backup-format-label">
                    {t('profile.backupFormat')}
                  </span>
                  <RadioGroup
                    className="profile-backup-format-group"
                    aria-labelledby="profile-backup-format-label"
                    value={backupFormat}
                    onValueChange={(value) => setBackupFormat(value as 'zip' | 'tgz')}
                  >
                    <div className="flex items-center gap-2">
                      <RadioGroupItem value="zip" id="profile-backup-format-zip" />
                      <Label htmlFor="profile-backup-format-zip" className="font-normal">
                        ZIP
                      </Label>
                    </div>
                    <div className="flex items-center gap-2">
                      <RadioGroupItem value="tgz" id="profile-backup-format-tgz" />
                      <Label htmlFor="profile-backup-format-tgz" className="font-normal">
                        tar.gz
                      </Label>
                    </div>
                  </RadioGroup>
                </div>
              </div>
              <p className={cn(appMutedText, 'profile-backup-restore-hint')}>{t('profile.restoreBackupHint')}</p>
            </CardContent>
            <CardFooter className="profile-backup-footer flex flex-wrap items-center gap-2 border-t-0 bg-transparent pt-0">
              <Button
                type="button"
                variant="outline"
                disabled={backingUp || (!backupTranscripts && !backupSummaries && !backupSkills)}
                onClick={() => void downloadBackup()}
              >
                {backingUp ? t('common.loading') : t('profile.downloadBackup')}
              </Button>
              <input
                ref={restoreInputRef}
                type="file"
                accept=".zip,.tgz,.tar.gz,application/zip,application/gzip"
                className="profile-backup-file-input"
                onChange={(e) => {
                  const file = e.target.files?.[0]
                  if (file) void restoreBackup(file)
                }}
              />
              <Button
                type="button"
                variant="outline"
                disabled={restoringUp || backingUp}
                onClick={() => restoreInputRef.current?.click()}
              >
                {restoringUp ? t('common.loading') : t('profile.restoreBackup')}
              </Button>
              {restoreMessage ? <p className="ok w-full basis-full">{restoreMessage}</p> : null}
            </CardFooter>
          </Card>
        )}

        <Card className="admin-form-card profile-tokens-card h-full">
          <ProfileCardHeader title={t('profile.tokens')} lead={t('profile.tokensLead')} />
          <CardContent className="flex flex-col gap-3">
            <p className={cn(appMutedText, 'profile-mcp-hint')}>{t('profile.mcpOAuthHint')}</p>
            {!apiAllowed && (
              <div className="profile-alert" role="status">
                {t('profile.apiDisabled')}
              </div>
            )}

            {secret && (
              <div className="profile-secret-card">
                <p className="profile-secret-title">{t('profile.secretOnce')}</p>
                <AppUrlCopyRow value={secret} className="profile-secret-copy-row" />
              </div>
            )}

            {tokenTotpOpen && (
              <div className="profile-secret-card flex flex-col gap-3">
                <p className="profile-secret-title">{t('mfa.tokenStepUp')}</p>
                <AppInputField
                  label={t('mfa.code')}
                  htmlFor="profile-token-totp"
                  type="text"
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  value={tokenTotp}
                  onChange={(e) => setTokenTotp(e.target.value)}
                />
                <div className="flex flex-wrap items-center gap-2">
                  <Button
                    type="button"
                    disabled={creating || !tokenTotp.trim()}
                    onClick={() => void createToken(tokenTotp.trim())}
                  >
                    {creating ? t('common.loading') : t('profile.newToken')}
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => {
                      setTokenTotpOpen(false)
                      setTokenTotp('')
                    }}
                  >
                    {t('common.cancel')}
                  </Button>
                </div>
              </div>
            )}

            <div className="profile-token-create">
              <Label htmlFor="profile-token-name">{t('profile.tokenName')}</Label>
              <div className="profile-token-create-row">
                <Input
                  id="profile-token-name"
                  className="profile-token-create-input"
                  placeholder={t('profile.tokenNamePlaceholder')}
                  value={tokenName}
                  onChange={(e) => setTokenName(e.target.value)}
                  disabled={!apiAllowed || creating}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault()
                      void createToken()
                    }
                  }}
                />
                <AppSubmitButton
                  className="shrink-0"
                  ready={apiAllowed && !creating && Boolean(tokenName.trim())}
                  busy={creating}
                  onClick={() => void createToken()}
                >
                  {creating ? t('common.loading') : t('profile.newToken')}
                </AppSubmitButton>
              </div>
            </div>

            {tokens.length === 0 ? (
              <p className={appStatsEmpty}>{t('profile.noTokens')}</p>
            ) : (
              <>
                {revokedTokens.length > 0 ? (
                  <div className="profile-token-revoked-toggle">
                    <Button
                      type="button"
                      variant="link"
                      className={cn(appMutedText, 'h-auto px-0')}
                      onClick={() => setShowRevokedTokens((open) => !open)}
                    >
                      {showRevokedTokens
                        ? t('profile.hideRevokedTokens')
                        : t('profile.showRevokedTokens', { count: revokedTokens.length })}
                    </Button>
                  </div>
                ) : null}
                {visibleTokens.length === 0 ? (
                  <p className={appStatsEmpty}>{t('profile.noActiveTokens')}</p>
                ) : (
              <ul className="profile-token-list">
                {visibleTokens.map((tok) => (
                  <li key={tok.id} className={`profile-token-item${tok.revoked ? ' is-revoked' : ''}`}>
                    <div className="profile-token-main">
                      <div className="profile-token-name">{tok.name}</div>
                      <div className={cn(appMutedText, 'profile-token-meta')}>
                        <span className="profile-token-prefix">{tok.prefix}</span>
                        <span className="profile-token-date">{fmtDate(tok.created_at)}</span>
                      </div>
                    </div>
                    <div className="profile-token-actions">
                      {tok.revoked ? (
                        <HubBadge tone="muted" className="profile-token-status">
                          {t('profile.revoked')}
                        </HubBadge>
                      ) : (
                        <Button type="button" variant="destructive" onClick={() => void revoke(tok.id)}>
                          {t('profile.revoke')}
                        </Button>
                      )}
                      {tok.blocked_by_tariff ? (
                        <HubBadge tone="pending" className="profile-token-status">
                          {t('profile.blockedTariff')}
                        </HubBadge>
                      ) : null}
                    </div>
                  </li>
                ))}
              </ul>
                )}
              </>
            )}

            {activeTokens.length > 0 && (
              <p className={cn(appMutedText, 'profile-token-count')}>
                {t('profile.tokenCount', { count: activeTokens.length })}
              </p>
            )}
          </CardContent>
        </Card>
      </div>

      {canDeleteAccount && (
        <Card className="admin-form-card profile-delete-account-card border-destructive/30">
          <ProfileCardHeader
            title={<span className="text-destructive">{t('profile.deleteAccount')}</span>}
            lead={t('profile.deleteAccountLead')}
          />
          <CardContent>
            <Button type="button" variant="destructive" onClick={() => void openDeleteAccount()}>
              {t('profile.deleteAccount')}
            </Button>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
