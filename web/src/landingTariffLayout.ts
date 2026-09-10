import type { Tariff } from './types'

export function sortTariffsForLanding(tariffs: Tariff[]): Tariff[] {
  return [...tariffs].sort((a, b) => {
    const creditDiff = Number(a.signup_credit) - Number(b.signup_credit)
    if (creditDiff !== 0) return creditDiff
    return a.name.localeCompare(b.name)
  })
}

export function pickPopularTariffId(
  tariffs: Tariff[],
  random: () => number = Math.random,
): string | null {
  const eligible = tariffs.filter((t) => !t.archived)
  if (eligible.length === 0) return null

  const maxCount = Math.max(...eligible.map((t) => t.org_count ?? 0))
  const tied = eligible.filter((t) => (t.org_count ?? 0) === maxCount)
  return tied[Math.floor(random() * tied.length)]!.id
}

export function arrangeTariffsForLanding(
  tariffs: Tariff[],
  random: () => number = Math.random,
): {
  ordered: Tariff[]
  popularTariffId: string | null
} {
  if (tariffs.length === 0) return { ordered: [], popularTariffId: null }

  const popularTariffId = pickPopularTariffId(tariffs, random)
  if (!popularTariffId || tariffs.length === 1) {
    return { ordered: sortTariffsForLanding(tariffs), popularTariffId }
  }

  const popular = tariffs.find((t) => t.id === popularTariffId)!
  const others = sortTariffsForLanding(tariffs.filter((t) => t.id !== popularTariffId))

  if (tariffs.length <= 3) {
    const mid = Math.floor(tariffs.length / 2)
    const ordered = [...others]
    ordered.splice(mid, 0, popular)
    return { ordered, popularTariffId }
  }

  const ordered = others.length >= 2
    ? [others[0]!, popular, others[1]!, ...others.slice(2)]
    : [others[0]!, popular]

  return { ordered, popularTariffId }
}

export function landingTariffSubtitleKey(index: number, total: number): 'regular' | 'standard' | 'expert' {
  if (total <= 1) return 'regular'
  if (index === 0) return 'regular'
  if (index === total - 1) return 'expert'
  return 'standard'
}
