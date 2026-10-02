import { useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import type { TFunction } from 'i18next'
import type { CallToneSummary, Transcript, Utterance } from '../types'
import { toneEmotionLabel, toneLayerLabel } from '../toneLabels'
import { HubBadge } from './app/AdminUi'

type ValenceKind = 'positive' | 'negative' | 'neutral' | 'unknown'

function valenceKind(value: number | undefined): ValenceKind {
  if (value == null || Number.isNaN(value)) return 'unknown'
  if (value > 0.15) return 'positive'
  if (value < -0.15) return 'negative'
  return 'neutral'
}

function formatValence(value: number | undefined, t: (k: string) => string): string {
  const kind = valenceKind(value)
  if (kind === 'unknown') return '—'
  if (kind === 'positive') return t('transcript.toneValencePositive')
  if (kind === 'negative') return t('transcript.toneValenceNegative')
  return t('transcript.toneValenceNeutral')
}

function valenceBadgeTone(kind: ValenceKind): 'success' | 'warning' | 'muted' {
  if (kind === 'positive') return 'success'
  if (kind === 'negative') return 'warning'
  return 'muted'
}

function ToneValenceStat({
  label,
  value,
  t,
}: {
  label: string
  value: number | undefined
  t: (k: string) => string
}) {
  const kind = valenceKind(value)
  const valueLabel = formatValence(value, t)
  return (
    <div className={`transcript-tone-stat transcript-tone-stat-${kind}`}>
      <span className="transcript-tone-stat-label">{label}</span>
      <HubBadge tone={valenceBadgeTone(kind)} className="transcript-tone-stat-badge">
        {valueLabel}
      </HubBadge>
      {value != null && !Number.isNaN(value) ? (
        <span className="transcript-tone-stat-num">
          {value > 0 ? '+' : ''}
          {value.toFixed(2)}
        </span>
      ) : null}
    </div>
  )
}

function topEmotion(emotions: Record<string, number> | undefined): string | null {
  if (!emotions) return null
  let best: string | null = null
  let score = -1
  for (const [key, val] of Object.entries(emotions)) {
    if (typeof val === 'number' && val > score) {
      score = val
      best = key
    }
  }
  return best
}

export function utteranceValenceClass(u: Utterance): string {
  const v = u.tone?.valence
  if (v == null || Number.isNaN(v)) return ''
  if (v > 0.15) return 'utterance-valence-pos'
  if (v < -0.15) return 'utterance-valence-neg'
  return 'utterance-valence-neutral'
}

export function utteranceValenceStripeClass(u: Utterance): string {
  const tone = utteranceValenceClass(u)
  if (!tone) return ''
  return tone.replace('utterance-valence', 'utterance-stripe')
}

/** Hover text for the left valence stripe on an utterance line. */
export function utteranceValenceHint(u: Utterance, t: TFunction): string | null {
  const kind = valenceKind(u.tone?.valence)
  if (kind === 'unknown') return null
  const value =
    u.tone?.valence != null && !Number.isNaN(u.tone.valence) ? u.tone.valence.toFixed(2) : null
  let hint =
    kind === 'positive'
      ? t('transcript.toneLineHintPositive')
      : kind === 'negative'
        ? t('transcript.toneLineHintNegative')
        : t('transcript.toneLineHintNeutral')
  if (value != null) {
    hint = `${hint} ${t('transcript.toneValenceScore', { value })}`
  }
  return hint
}

function ToneLayersBadges({ layers, t }: { layers: string[]; t: TFunction }) {
  if (layers.length === 0) return null
  return (
    <div className="transcript-tone-layers">
      <span className="transcript-tone-layers-label">{t('transcript.toneSources')}</span>
      <span className="transcript-tone-layers-badges">
        {layers.map((layer) => (
          <HubBadge key={layer} tone="muted" className="transcript-tone-layer-badge">
            {toneLayerLabel(t, layer)}
          </HubBadge>
        ))}
      </span>
    </div>
  )
}

/** Compact tone summary row (under source filename on transcript page). */
export function TranscriptToneSummaryCard({ item }: { item: Transcript }) {
  const { t } = useTranslation()
  const summary: CallToneSummary | null | undefined = item.call_summary
  const layers = item.tone_layers ?? []
  const hasData = Boolean(item.has_tone_analytics && (summary || layers.length > 0))

  if (!item.has_tone_analytics) return null

  if (!hasData) {
    return <p className="transcript-tone-inline muted text-sm">{t('transcript.toneUnavailable')}</p>
  }

  if (!summary) {
    return (
      <div className="transcript-tone-inline transcript-tone-metrics-row">
        <span className="transcript-tone-head-title">{t('transcript.toneTitle')}</span>
        <span className="muted text-sm">{t('transcript.toneUtterancesOnly')}</span>
        <ToneLayersBadges layers={layers} t={t} />
      </div>
    )
  }

  return (
    <div className="transcript-tone-inline transcript-tone-metrics-row">
      <span className="transcript-tone-head-title">{t('transcript.toneTitle')}</span>
      <ToneValenceStat label={t('transcript.toneOpening')} value={summary.opening_valence} t={t} />
      <ToneValenceStat label={t('transcript.toneClosing')} value={summary.closing_valence} t={t} />
      {summary.de_escalation != null ? (
        <div className="transcript-tone-stat transcript-tone-stat-neutral">
          <span className="transcript-tone-stat-label transcript-tone-stat-label-wrap">
            {t('transcript.toneDeEscalationShort')}
          </span>
          <HubBadge tone={summary.de_escalation ? 'success' : 'muted'}>
            {summary.de_escalation ? t('transcript.toneDeEscalationYes') : t('transcript.toneDeEscalationNo')}
          </HubBadge>
        </div>
      ) : null}
      <ToneLayersBadges layers={layers} t={t} />
    </div>
  )
}

export function UtteranceToneChip({ u }: { u: Utterance }) {
  const { t } = useTranslation()
  const emotion = useMemo(() => topEmotion(u.tone?.emotions), [u.tone?.emotions])
  if (!emotion) return null
  return <span className="utterance-tone-chip">{toneEmotionLabel(t, emotion)}</span>
}
