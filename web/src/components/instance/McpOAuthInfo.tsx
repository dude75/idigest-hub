import { useTranslation } from 'react-i18next'
import { FieldDescription } from '@/components/ui/field'

type Props = {
  publicBaseUrl: string | null | undefined
}

export function McpOAuthInfo({ publicBaseUrl }: Props) {
  const { t } = useTranslation()
  const base = (publicBaseUrl || '').trim().replace(/\/$/, '')
  const mcpUrl = base ? `${base}/mcp` : null
  const resourceMeta = base ? `${base}/.well-known/oauth-protected-resource/mcp` : null

  return (
    <div className="rounded-lg border border-border bg-muted/30 p-3 text-sm">
      <p className="m-0 font-medium text-foreground">{t('instance.mcpOAuthSection')}</p>
      <FieldDescription className="mt-1">{t('instance.mcpOAuthLead')}</FieldDescription>
      {mcpUrl ? (
        <ul className="mt-2 space-y-1 pl-4 text-muted-foreground">
          <li>
            <span className="text-foreground">{t('instance.mcpResourceUrl')}:</span>{' '}
            <code className="text-xs">{mcpUrl}</code>
          </li>
          <li>
            <span className="text-foreground">{t('instance.mcpResourceMeta')}:</span>{' '}
            <code className="text-xs">{resourceMeta}</code>
          </li>
        </ul>
      ) : (
        <FieldDescription className="mt-2">{t('instance.mcpPublicUrlRequired')}</FieldDescription>
      )}
    </div>
  )
}
