import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { api } from '../api'
import { isOrgAdmin, useAuth } from '../auth'
import { AppListPagination } from './app/AppListPagination'
import { ListSection } from './app/EntityUi'
import type { SchemaOrgPublicLinkListResponse } from '../openapi'
import type { OrgPublicLinkItem } from '../types'
import { fmtDate, showError } from '../util'
import { Button } from '@/components/ui/button'
import { HubBadge } from './app/AdminUi'
import { AppUrlCopyRow } from './app/AppUrlCopyRow'
import {
  DEFAULT_LIST_PAGE_SIZE,
  listPageBounds,
  type ListPageSize,
} from './app/selectOptions'

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
            <HubBadge tone="success">{t('publicLinks.statusActive')}</HubBadge>
          ) : (
            <HubBadge tone="warning">{t('publicLinks.statusInactive')}</HubBadge>
          )}
          {link.pin_required ? <HubBadge tone="muted">{t('publicLinks.pin')}</HubBadge> : null}
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
          <AppUrlCopyRow value={link.url} />
        ) : (
          <p className="muted public-link-url-missing">—</p>
        )}
        <Button
          type="button"
          variant="outline"
          className="share-revoke-public public-link-revoke"
          disabled={revoking}
          onClick={onRevoke}
        >
          {t('share.revokePublic')}
        </Button>
      </div>
    </article>
  )
}

export function LibraryLinksTab() {
  const { t } = useTranslation()
  const { me } = useAuth()
  const [links, setLinks] = useState<OrgPublicLinkItem[]>([])
  const [revoking, setRevoking] = useState<string | null>(null)
  const [pageSize, setPageSize] = useState<ListPageSize>(DEFAULT_LIST_PAGE_SIZE)
  const [page, setPage] = useState(0)
  const admin = isOrgAdmin(me)

  const sortedLinks = useMemo(
    () => [...links].sort((a, b) => b.created_at.localeCompare(a.created_at)),
    [links],
  )

  const listTotal = sortedLinks.length
  const { safePage, offset } = listPageBounds(listTotal, page, pageSize)
  const pagedLinks = sortedLinks.slice(offset, offset + pageSize)

  async function load() {
    const r = await api<SchemaOrgPublicLinkListResponse>('/org/public-links')
    setLinks(r.items ?? [])
  }

  useEffect(() => {
    load().catch(showError)
  }, [])

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

  const policyOff = me?.org?.allow_public_links === false
  const urlMissing = me?.org?.public_base_url_set === false

  return (
    <>
      {policyOff ? <p className="muted admin-notice">{t('publicLinks.policyOff')}</p> : null}
      {urlMissing ? <p className="muted admin-notice">{t('share.publicUrlMissing')}</p> : null}
      <ListSection
        title={admin ? t('publicLinks.titleAdmin') : t('publicLinks.title')}
        lead={admin ? t('publicLinks.leadAdmin') : t('publicLinks.lead')}
        empty={t('publicLinks.none')}
        isEmpty={listTotal === 0}
        footer={
          listTotal > 0 ? (
            <AppListPagination
              htmlFor="library-links-page-size"
              pageSize={pageSize}
              setPageSize={setPageSize}
              page={safePage}
              setPage={setPage}
              total={listTotal}
            />
          ) : null
        }
      >
        {pagedLinks.map((link) => (
          <PublicLinkRow
            key={link.id}
            link={link}
            admin={admin}
            revoking={revoking === link.id}
            onRevoke={() => void revoke(link.id)}
          />
        ))}
      </ListSection>
    </>
  )
}
