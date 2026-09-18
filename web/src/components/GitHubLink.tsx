import { useTranslation } from 'react-i18next'

export const GITHUB_REPO_URL = 'https://github.com/dude75/idigest-hub'

type Props = {
  variant?: 'icon' | 'footer'
  className?: string
}

function GitHubIcon() {
  return (
    <svg className="github-icon" aria-hidden="true" viewBox="0 0 19 19">
      <use href="/icons.svg#github-icon" />
    </svg>
  )
}

export function GitHubLink({ variant = 'icon', className }: Props) {
  const { t } = useTranslation()
  const label = t('common.github')

  return (
    <a
      href={GITHUB_REPO_URL}
      target="_blank"
      rel="noopener noreferrer"
      className={`github-link github-link-${variant}${className ? ` ${className}` : ''}`}
      aria-label={variant === 'icon' ? label : undefined}
    >
      <GitHubIcon />
      {variant === 'footer' && <span>{label}</span>}
    </a>
  )
}
