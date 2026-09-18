import type { InstanceSettings } from './types'

export const LEGAL_DOCUMENT_KEYS = ['user_agreement', 'personal_data_consent', 'privacy_policy'] as const

export type LegalDocumentKey = (typeof LEGAL_DOCUMENT_KEYS)[number]

export type LegalDocument = {
  key: LegalDocumentKey
  version: number
  text: string
  accepted_version: number
  pending: boolean
}

export type SavedLegalDoc = { en: string | null; ru: string | null }

export type SavedLegalDocs = Record<LegalDocumentKey, SavedLegalDoc>

export const LEGAL_DOCUMENT_I18N: Record<LegalDocumentKey, string> = {
  user_agreement: 'userAgreement',
  personal_data_consent: 'personalDataConsent',
  privacy_policy: 'privacyPolicy',
}

export const LEGAL_DOC_FIELDS: Record<
  LegalDocumentKey,
  {
    en: keyof InstanceSettings
    ru: keyof InstanceSettings
    version: keyof InstanceSettings
    published: keyof InstanceSettings
  }
> = {
  user_agreement: {
    en: 'user_agreement_text_en',
    ru: 'user_agreement_text_ru',
    version: 'user_agreement_version',
    published: 'user_agreement_published',
  },
  personal_data_consent: {
    en: 'personal_data_consent_text_en',
    ru: 'personal_data_consent_text_ru',
    version: 'personal_data_consent_version',
    published: 'personal_data_consent_published',
  },
  privacy_policy: {
    en: 'privacy_policy_text_en',
    ru: 'privacy_policy_text_ru',
    version: 'privacy_policy_version',
    published: 'privacy_policy_published',
  },
}

export function savedLegalDocsFromSettings(settings: InstanceSettings): SavedLegalDocs {
  return {
    user_agreement: {
      en: settings.user_agreement_text_en,
      ru: settings.user_agreement_text_ru,
    },
    personal_data_consent: {
      en: settings.personal_data_consent_text_en,
      ru: settings.personal_data_consent_text_ru,
    },
    privacy_policy: {
      en: settings.privacy_policy_text_en,
      ru: settings.privacy_policy_text_ru,
    },
  }
}

export function legalDocTextTrim(value: string | null | undefined): string {
  return (value || '').trim()
}

/** Mirrors backend version bump: any non-empty text change requires re-acceptance. */
export function legalDocChangeRequiresReacceptance(saved: SavedLegalDoc, current: SavedLegalDoc): boolean {
  const oldEn = legalDocTextTrim(saved.en)
  const oldRu = legalDocTextTrim(saved.ru)
  const newEn = legalDocTextTrim(current.en)
  const newRu = legalDocTextTrim(current.ru)
  if (newEn === oldEn && newRu === oldRu) return false
  if (!newEn && !newRu) return false
  return true
}

export function legalDocsChangeRequiresReacceptance(saved: SavedLegalDocs, settings: InstanceSettings): boolean {
  const current = savedLegalDocsFromSettings(settings)
  return LEGAL_DOCUMENT_KEYS.some((key) => legalDocChangeRequiresReacceptance(saved[key], current[key]))
}

export function legalDocDownloadName(key: LegalDocumentKey, version: number): string {
  return `${key.replace(/_/g, '-')}-v${version}.md`
}

export const LEGAL_DOCUMENT_SLUGS: Record<LegalDocumentKey, string> = {
  user_agreement: 'user-agreement',
  personal_data_consent: 'personal-data-consent',
  privacy_policy: 'privacy-policy',
}

const SLUG_TO_KEY = Object.fromEntries(
  LEGAL_DOCUMENT_KEYS.map((key) => [LEGAL_DOCUMENT_SLUGS[key], key]),
) as Record<string, LegalDocumentKey>

export function legalDocKeyFromSlug(slug: string): LegalDocumentKey | null {
  return SLUG_TO_KEY[slug] ?? null
}

export function legalDocPath(key: LegalDocumentKey): string {
  return `/legal/${LEGAL_DOCUMENT_SLUGS[key]}`
}

export type PublicLegalDocument = {
  key: LegalDocumentKey
  version: number
  text: string
}
