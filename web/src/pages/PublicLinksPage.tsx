import { useEffect, useState } from 'react'
import { Link, Navigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { api } from '../api'
import { isOrgAdmin, useAuth } from '../auth'
import { AdminPage, AdminTableCard } from '../components/AdminSection'
import { LIBRARY_DEFAULT } from '../routes'
import type { OrgPublicLinkItem } from '../types'
import { fmtDate, showError } from '../util'

function CopyUrlButton({ url }: { url: string }) {
  const { t } = useTranslation()
  const [copied, setCopied] = useState(false)

  async function copy() {
    try {
      await navigator.clipboard.writeText(url)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1500)
    } catch {
      /* clipboard unavailable */
    }
  }

  return (
    <button type="button" className="public-link-copy" onClick={() => void copy()}>
      {copied ? t('profile.copied') : t('common.copy')}
    </button>
  )
}

function PublicLinkRow({
  link,
  admin,
  revoking,
  onRevoke,
}: {
  link: OrgPublicLinkItem
  admin: boolean
  revoking: boolean
  onRevoke: () => void
}) {
  const { t } = useTranslation()

  return (
    <article className="public-link-row">
      <div className="public-link-head">
        <Link to={`/app/summary/${link.summary_id}`} className="public-link-title">
          {link.summary_title}
        </Link>
        <div className="public-link-badges">
          {link.active ? (
            <span className="badge out">{t('publicLinks.statusActive')}</span>
          ) : (
            <span className="badge err">{t('publicLinks.statusInactive')}</span>
          )}
          {link.pin_required && <span className="badge">{t('publicLinks.pin')}</span>}
        </div>
      </div>
      <dl className="public-link-meta">
        <div className="public-link-meta-item">
          <dt>{t('publicLinks.created')}</dt>
          <dd>{fmtDate(link.created_at)}</dd>
        </div>
        <div className="public-link-meta-item">
          <dt>{t('share.expiry')}</dt>
          <dd>{link.expires_at ? fmtDate(link.expires_at) : t('share.expiry_never')}</dd>
        </div>
        {admin && (
          <div className="public-link-meta-item">
            <dt>{t('org.publicLinksOwner')}</dt>
            <dd className="public-link-owner-email">{link.owner_email}</dd>
          </div>
        )}
      </dl>
      <div className="public-link-actions-row">
        {link.url ? (
          <div className="public-link-url-row">
            <code className="public-link-url" title={link.url}>{link.url}</code>
            <CopyUrlButton url={link.url} />
          </div>
        ) : (
          <p className="muted public-link-url-missing">—</p>
        )}
        <button
          type="button"
          className="danger public-link-revoke"
          disabled={revoking}
          onClick={onRevoke}
        >
          {t('share.revokePublic')}
        </button>
      </div>
    </article>
  )
}

export function PublicLinksPage() {
  const { t } = useTranslation()
  const { me } = useAuth()
  const [links, setLinks] = useState<OrgPublicLinkItem[]>([])
  const [revoking, setRevoking] = useState<string | null>(null)
  const admin = isOrgAdmin(me)
  const hasOrg = Boolean(me?.org)

  async function load() {
    const r = await api<{ items: OrgPublicLinkItem[] }>('/org/public-links')
    setLinks(r.items)
  }

  useEffect(() => {
    if (!hasOrg) return
    load().catch(showError)
  }, [hasOrg])

  async function revoke(linkId: string) {
    setRevoking(linkId)
    try {
      await api(`/org/public-links/${linkId}`, { method: 'DELETE' })
      await load()
    } catch (e) {
      showError(e)
    } finally {
      setRevoking(null)
    }
  }

  if (!hasOrg) return <Navigate to="/app/profile" replace />

  const policyOff = me?.org?.allow_public_links === false
  const urlMissing = me?.org?.public_base_url_set === false

  return (
    <AdminPage>
      {policyOff && (
        <p className="muted admin-notice">{t('publicLinks.policyOff')}</p>
      )}
      {urlMissing && (
        <p className="muted admin-notice">{t('share.publicUrlMissing')}</p>
      )}
      <AdminTableCard
        title={admin ? t('publicLinks.titleAdmin') : t('publicLinks.title')}
        lead={admin ? t('publicLinks.leadAdmin') : t('publicLinks.lead')}
        empty={t('publicLinks.none')}
        isEmpty={links.length === 0}
      >
        <div className="public-links-list">
          {links.map((link) => (
            <PublicLinkRow
              key={link.id}
              link={link}
              admin={admin}
              revoking={revoking === link.id}
              onRevoke={() => void revoke(link.id)}
            />
          ))}
        </div>
      </AdminTableCard>
      {!admin && (
        <p className="muted">
          <Link to={LIBRARY_DEFAULT}>{t('publicLinks.backToLibrary')}</Link>
        </p>
      )}
    </AdminPage>
  )
}
