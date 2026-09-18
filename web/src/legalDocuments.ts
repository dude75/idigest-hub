import type { InstanceSettings } from './types'

export const LEGAL_DOCUMENT_KEYS = ['user_agreement', 'personal_data_consent', 'privacy_policy'] as const

export type LegalDocumentKey = (typeof LEGAL_DOCUMENT_KEYS)[number]

export const LEGAL_DOC_LOCALES = ['ru', 'en', 'es'] as const

export type LegalDocLocale = (typeof LEGAL_DOC_LOCALES)[number]

export type LegalDocument = {
  key: LegalDocumentKey
  version: number
  text: string
  accepted_version: number
  pending: boolean
}

export type SavedLegalDoc = Record<LegalDocLocale, string | null>

export type SavedLegalDocs = Record<LegalDocumentKey, SavedLegalDoc>

export const LEGAL_DOCUMENT_I18N: Record<LegalDocumentKey, string> = {
  user_agreement: 'userAgreement',
  personal_data_consent: 'personalDataConsent',
  privacy_policy: 'privacyPolicy',
}

export const LEGAL_DOC_FIELDS: Record<
  LegalDocumentKey,
  {
    texts: Record<LegalDocLocale, keyof InstanceSettings>
    version: keyof InstanceSettings
    published: keyof InstanceSettings
  }
> = {
  user_agreement: {
    texts: {
      en: 'user_agreement_text_en',
      ru: 'user_agreement_text_ru',
      es: 'user_agreement_text_es',
    },
    version: 'user_agreement_version',
    published: 'user_agreement_published',
  },
  personal_data_consent: {
    texts: {
      en: 'personal_data_consent_text_en',
      ru: 'personal_data_consent_text_ru',
      es: 'personal_data_consent_text_es',
    },
    version: 'personal_data_consent_version',
    published: 'personal_data_consent_published',
  },
  privacy_policy: {
    texts: {
      en: 'privacy_policy_text_en',
      ru: 'privacy_policy_text_ru',
      es: 'privacy_policy_text_es',
    },
    version: 'privacy_policy_version',
    published: 'privacy_policy_published',
  },
}

export const FOOTER_TEXT_FIELDS: Record<LegalDocLocale, keyof InstanceSettings> = {
  en: 'landing_footer_text_en',
  ru: 'landing_footer_text_ru',
  es: 'landing_footer_text_es',
}

export const LEGAL_DOC_LOCALE_LABEL_KEYS: Record<LegalDocLocale, string> = {
  ru: 'instance.userAgreementRu',
  en: 'instance.userAgreementEn',
  es: 'instance.userAgreementEs',
}

function savedLegalDocFromSettings(settings: InstanceSettings, key: LegalDocumentKey): SavedLegalDoc {
  const texts = LEGAL_DOC_FIELDS[key].texts
  return {
    en: settings[texts.en] as string | null,
    ru: settings[texts.ru] as string | null,
    es: settings[texts.es] as string | null,
  }
}

export function savedLegalDocsFromSettings(settings: InstanceSettings): SavedLegalDocs {
  return Object.fromEntries(
    LEGAL_DOCUMENT_KEYS.map((key) => [key, savedLegalDocFromSettings(settings, key)]),
  ) as SavedLegalDocs
}

export function legalDocTextTrim(value: string | null | undefined): string {
  return (value || '').trim()
}

/** Mirrors backend version bump: any non-empty text change requires re-acceptance. */
export function legalDocChangeRequiresReacceptance(saved: SavedLegalDoc, current: SavedLegalDoc): boolean {
  const unchanged = LEGAL_DOC_LOCALES.every(
    (locale) => legalDocTextTrim(saved[locale]) === legalDocTextTrim(current[locale]),
  )
  if (unchanged) return false
  return LEGAL_DOC_LOCALES.some((locale) => legalDocTextTrim(current[locale]))
}

export function legalDocsChangeRequiresReacceptance(saved: SavedLegalDocs, settings: InstanceSettings): boolean {
  const current = savedLegalDocsFromSettings(settings)
  return LEGAL_DOCUMENT_KEYS.some((key) => legalDocChangeRequiresReacceptance(saved[key], current[key]))
}

export type LegalDocsAdminSnapshot = {
  docs: SavedLegalDocs
  published: Record<LegalDocumentKey, boolean>
}

export type FooterAdminSnapshot = Record<LegalDocLocale, string | null> & {
  published: boolean
}

export function legalDocPublished(settings: InstanceSettings, key: LegalDocumentKey): boolean {
  return (settings[LEGAL_DOC_FIELDS[key].published] as boolean | undefined) ?? true
}

export function legalDocsAdminSnapshot(settings: InstanceSettings): LegalDocsAdminSnapshot {
  return {
    docs: savedLegalDocsFromSettings(settings),
    published: Object.fromEntries(
      LEGAL_DOCUMENT_KEYS.map((key) => [key, legalDocPublished(settings, key)]),
    ) as Record<LegalDocumentKey, boolean>,
  }
}

export function footerAdminSnapshot(settings: InstanceSettings): FooterAdminSnapshot {
  return {
    en: settings.landing_footer_text_en,
    ru: settings.landing_footer_text_ru,
    es: settings.landing_footer_text_es,
    published: settings.landing_footer_published ?? true,
  }
}

export function legalDocHasContent(doc: SavedLegalDoc): boolean {
  return LEGAL_DOC_LOCALES.some((locale) => legalDocTextTrim(doc[locale]))
}

function legalDocAdminFieldsEqual(saved: SavedLegalDoc, current: SavedLegalDoc): boolean {
  return LEGAL_DOC_LOCALES.every(
    (locale) => legalDocTextTrim(saved[locale]) === legalDocTextTrim(current[locale]),
  )
}

export function legalDocAdminDirty(
  saved: LegalDocsAdminSnapshot,
  settings: InstanceSettings,
  key: LegalDocumentKey,
): boolean {
  const current = legalDocsAdminSnapshot(settings)
  if (saved.published[key] !== current.published[key]) return true
  return !legalDocAdminFieldsEqual(saved.docs[key], current.docs[key])
}

export function legalDocsAdminDirty(saved: LegalDocsAdminSnapshot, settings: InstanceSettings): boolean {
  return LEGAL_DOCUMENT_KEYS.some((key) => legalDocAdminDirty(saved, settings, key))
}

export function footerAdminDirty(saved: FooterAdminSnapshot, settings: InstanceSettings): boolean {
  const current = footerAdminSnapshot(settings)
  if (saved.published !== current.published) return true
  return LEGAL_DOC_LOCALES.some(
    (locale) => legalDocTextTrim(saved[locale]) !== legalDocTextTrim(current[locale]),
  )
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
