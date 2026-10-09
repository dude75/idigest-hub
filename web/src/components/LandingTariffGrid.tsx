import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import type { Tariff } from '../types'
import {
  Pagination,
  PaginationContent,
  PaginationItem,
  PaginationNext,
  PaginationPrevious,
} from '@/components/ui/pagination'
import {
  LandingTariffCard,
  landingTariffSubtitleKey,
} from './LandingTariffCard'
import { LandingOpenSourceTariffCard } from './LandingOpenSourceTariffCard'

const PAGE_SIZE = 3

type Props = {
  tariffs: Tariff[]
  popularTariffId: string | null
}

export function LandingTariffGrid({ tariffs, popularTariffId }: Props) {
  const { t } = useTranslation()
  const [page, setPage] = useState(0)
  const pageCount = Math.ceil(tariffs.length / PAGE_SIZE)
  const paged = pageCount > 1
  const start = page * PAGE_SIZE
  const visible = tariffs.slice(start, start + PAGE_SIZE)

  useEffect(() => {
    if (page >= pageCount) setPage(Math.max(0, pageCount - 1))
  }, [page, pageCount])

  return (
    <div className="landing-pricing-carousel">
      <div className="landing-pricing-grid" data-visible={1 + visible.length}>
        <LandingOpenSourceTariffCard />
        {visible.map((tr, offset) => {
          const index = start + offset
          return (
            <LandingTariffCard
              key={tr.id}
              tariff={tr}
              popular={tr.id === popularTariffId}
              subtitleKey={landingTariffSubtitleKey(index, tariffs.length)}
              to={`/signup?tariff=${encodeURIComponent(tr.id)}`}
            />
          )
        })}
      </div>
      {paged && (
        <div className="landing-pricing-controls">
          <Pagination className="mx-0 w-auto">
            <PaginationContent>
              <PaginationItem>
                <PaginationPrevious
                  text={t('common.prev')}
                  disabled={page === 0}
                  onClick={() => setPage((p) => p - 1)}
                />
              </PaginationItem>
              <PaginationItem>
                <span className="landing-pricing-page muted px-2 tabular-nums" aria-live="polite">
                  {t('landing.tariffPage', { current: page + 1, total: pageCount })}
                </span>
              </PaginationItem>
              <PaginationItem>
                <PaginationNext
                  text={t('common.next')}
                  disabled={page >= pageCount - 1}
                  onClick={() => setPage((p) => p + 1)}
                />
              </PaginationItem>
            </PaginationContent>
          </Pagination>
        </div>
      )}
    </div>
  )
}
