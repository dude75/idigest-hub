import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '../api'
import { useAuth } from '../auth'
import { AppBrand } from './AppBrand'
import { GitHubLink } from './GitHubLink'
import { LanguageSwitcher } from './LanguageSwitcher'
import { resolveAuthContinuationPath } from '../routes'
import type { SchemaTariffListResponse } from '../openapi'
import type { Tariff } from '../types'
import { cn } from '@/lib/utils'
import { appMuted } from './app/appTypography'
import { ButtonLink } from '@/components/ui/button-link'

export function LandingHeader() {
  const { t } = useTranslation()
  const { me } = useAuth()
  const [tariffs, setTariffs] = useState<Tariff[]>([])
  const enterAppPath = me ? resolveAuthContinuationPath(me) : null

  useEffect(() => {
    api<SchemaTariffListResponse>('/auth/signup-tariffs')
      .then((r) => setTariffs(r.items ?? []))
      .catch(() => setTariffs([]))
  }, [])

  const landingNavLink = cn(appMuted, 'transition-colors hover:text-foreground')

  return (
    <header className="landing-topbar topbar">
      <AppBrand />
      <nav className="landing-nav" aria-label="Landing">
        <a href="/#how" className={landingNavLink}>{t('landing.navHow')}</a>
        <a href="/#features" className={landingNavLink}>{t('landing.navFeatures')}</a>
        {tariffs.length > 0 && (
          <a href="/#pricing" className={landingNavLink}>
            {t('landing.navPricing')}
          </a>
        )}
        <a href="/#faq" className={landingNavLink}>{t('landing.navFaq')}</a>
      </nav>
      <div className="right flex flex-wrap items-center gap-2">
        <GitHubLink />
        <LanguageSwitcher />
        {me ? (
          <ButtonLink to={enterAppPath!} size="sm">
            {t('landing.enterSystem')}
          </ButtonLink>
        ) : (
          <>
            <ButtonLink to="/login" variant="outline" size="sm">
              {t('auth.login')}
            </ButtonLink>
            <ButtonLink to="/signup" size="sm">
              {t('auth.signup')}
            </ButtonLink>
          </>
        )}
      </div>
    </header>
  )
}
