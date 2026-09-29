import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '../api'
import { useAuth } from '../auth'
import { AppBrand } from './AppBrand'
import { GitHubLink } from './GitHubLink'
import { LanguageSwitcher } from './LanguageSwitcher'
import { resolveAuthContinuationPath } from '../routes'
import type { Tariff } from '../types'
import { ButtonLink } from '@/components/ui/button-link'

export function LandingHeader() {
  const { t } = useTranslation()
  const { me } = useAuth()
  const [tariffs, setTariffs] = useState<Tariff[]>([])
  const enterAppPath = me ? resolveAuthContinuationPath(me) : null

  useEffect(() => {
    api<{ items: Tariff[] }>('/auth/signup-tariffs')
      .then((r) => setTariffs(r.items))
      .catch(() => setTariffs([]))
  }, [])

  return (
    <header className="landing-topbar topbar">
      <AppBrand />
      <nav className="landing-nav" aria-label="Landing">
        <a href="/#how">{t('landing.navHow')}</a>
        <a href="/#features">{t('landing.navFeatures')}</a>
        {tariffs.length > 0 && <a href="/#pricing">{t('landing.navPricing')}</a>}
        <a href="/#faq">{t('landing.navFaq')}</a>
      </nav>
      <div className="right row">
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
