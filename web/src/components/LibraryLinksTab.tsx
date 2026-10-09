import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { api } from '../api'
import { isOrgAdmin, useAuth } from '../auth'
import { AdminTablePager } from './app/AdminDataTable'
import { ListSection } from './app/EntityUi'
import type { SchemaOrgPublicLinkListResponse } from '../openapi'
import type { OrgPublicLinkItem } from '../types'
import { fmtDate, showError } from '../util'
import { Button } from '@/components/ui/button'
import { HubBadge } from './app/AdminUi'
import { AppUrlCopyRow } from './app/AppUrlCopyRow'
import { AppPageSizeField } from './app/AppFormControls'
import { pageSizeOptions } from './app/selectOptions'

const PAGE_SIZES = [10, 50, 100] as const
type PageSize = (typeof PAGE_SIZES)[number]

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
  const [pageSize, setPageSize] = useState<PageSize>(10)
  const [page, setPage] = useState(0)
  const admin = isOrgAdmin(me)

  const sortedLinks = useMemo(
    () => [...links].sort((a, b) => b.created_at.localeCompare(a.created_at)),
    [links],
  )

  const listTotal = sortedLinks.length
  const pageCount = Math.max(1, Math.ceil(listTotal / pageSize))
  const safePage = Math.min(page, pageCount - 1)
  const listFrom = listTotal === 0 ? 0 : safePage * pageSize + 1
  const listTo = Math.min(listTotal, (safePage + 1) * pageSize)
  const pagedLinks = sortedLinks.slice(safePage * pageSize, safePage * pageSize + pageSize)

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

  const pageSizeSelect = (
    <AppPageSizeField
      className="library-list-page-size"
      label={t('task.pageSize')}
      htmlFor="library-links-page-size"
      value={String(pageSize)}
      onValueChange={(v) => {
        setPageSize(Number(v) as PageSize)
        setPage(0)
      }}
      options={pageSizeOptions(PAGE_SIZES)}
    />
  )

  return (
    <>
      {policyOff ? <p className="muted admin-notice">{t('publicLinks.policyOff')}</p> : null}
      {urlMissing ? <p className="muted admin-notice">{t('share.publicUrlMissing')}</p> : null}
      <ListSection
        title={admin ? t('publicLinks.titleAdmin') : t('publicLinks.title')}
        lead={admin ? t('publicLinks.leadAdmin') : t('publicLinks.lead')}
        empty={t('publicLinks.none')}
        isEmpty={listTotal === 0}
        actions={pageSizeSelect}
        footer={
          listTotal > pageSize ? (
            <AdminTablePager>
              <Button
                type="button"
                size="sm"
                variant="outline"
                disabled={safePage === 0}
                onClick={() => setPage(safePage - 1)}
              >
                {t('common.prev')}
              </Button>
              <span className="text-sm text-muted-foreground">
                {t('task.pageRange', { from: listFrom, to: listTo, total: listTotal })}
              </span>
              <Button
                type="button"
                size="sm"
                variant="outline"
                disabled={safePage >= pageCount - 1}
                onClick={() => setPage(safePage + 1)}
              >
                {t('common.next')}
              </Button>
            </AdminTablePager>
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
