import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import type { Tariff } from '../types'
import {
  LandingTariffCard,
  landingTariffSubtitleKey,
} from './LandingTariffCard'

const PAGE_SIZE = 3

type Props = {
  tariffs: Tariff[]
  popularIndex: number
}

export function LandingTariffGrid({ tariffs, popularIndex }: Props) {
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
      <div className="landing-pricing-grid" data-visible={visible.length}>
        {visible.map((tr, offset) => {
          const index = start + offset
          return (
            <LandingTariffCard
              key={tr.id}
              tariff={tr}
              popular={index === popularIndex}
              subtitleKey={landingTariffSubtitleKey(index, tariffs.length)}
              to={`/signup?tariff=${encodeURIComponent(tr.id)}`}
            />
          )
        })}
      </div>
      {paged && (
        <div className="landing-pricing-controls">
          <button
            type="button"
            className="landing-pricing-arrow"
            disabled={page === 0}
            aria-label={t('common.prev')}
            onClick={() => setPage((p) => p - 1)}
          >
            ‹
          </button>
          <span className="landing-pricing-page muted" aria-live="polite">
            {t('landing.tariffPage', { current: page + 1, total: pageCount })}
          </span>
          <button
            type="button"
            className="landing-pricing-arrow"
            disabled={page >= pageCount - 1}
            aria-label={t('common.next')}
            onClick={() => setPage((p) => p + 1)}
          >
            ›
          </button>
        </div>
      )}
    </div>
  )
}
