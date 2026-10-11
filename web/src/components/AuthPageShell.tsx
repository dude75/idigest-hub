import type { ReactNode } from 'react'
import { AppBrand } from './AppBrand'
import { BackToLandingLink } from './BackToLandingLink'
import { GitHubLink } from './GitHubLink'
import { LanguageSwitcher } from './LanguageSwitcher'

type Props = {
  children: ReactNode
  /** Same content column as `/app/*` (`main.page`, 1080px). */
  appPage?: boolean
}

export function AuthPageShell({ children, appPage }: Props) {
  return (
    <div className="auth-layout">
      <header className="auth-topbar topbar">
        <AppBrand />
        <div className="right row">
          <BackToLandingLink />
          <GitHubLink />
          <LanguageSwitcher />
        </div>
      </header>
      <main className={appPage ? 'page' : 'auth-page'}>{children}</main>
    </div>
  )
}
