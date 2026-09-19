import { useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import { api } from '../../api'
import { useAuth } from '../../auth'
import type { InstanceSettings } from '../../types'
import { AdminFormCard, AdminPage } from '../../components/AdminSection'
import { ConfirmDialog } from '../../components/ConfirmDialog'
import { Segmented } from '../../components/Segmented'
import { MarkdownBody } from '../../markdown'
import {
  FOOTER_TEXT_FIELDS,
  LEGAL_DOC_FIELDS,
  LEGAL_DOC_LOCALES,
  LEGAL_DOC_LOCALE_LABEL_KEYS,
  LEGAL_DOCUMENT_I18N,
  LEGAL_DOCUMENT_KEYS,
  footerAdminDirty,
  footerAdminSnapshot,
  legalDocAdminDirty,
  legalDocChangeRequiresReacceptance,
  legalDocHasContent,
  legalDocPath,
  legalDocPublished,
  legalDocsAdminDirty,
  legalDocsAdminSnapshot,
  legalDocsChangeRequiresReacceptance,
  savedLegalDocsFromSettings,
  type FooterAdminSnapshot,
  type LegalDocLocale,
  type LegalDocumentKey,
  type LegalDocsAdminSnapshot,
} from '../../legalDocuments'
import { showError } from '../../util'
import { useAgreementPreview } from './useAgreementPreview'
import { LegalDocumentHistoryModal } from './LegalDocumentHistoryModal'

const LEGAL_LANG_OPTIONS = LEGAL_DOC_LOCALES.map((value) => ({
  value,
  labelKey: `lang.${value}` as const,
}))

function AgreementEditorPair({
  label,
  value,
  onChange,
}: {
  label: string
  value: string
  onChange: (value: string) => void
}) {
  const { t } = useTranslation()
  const preview = useAgreementPreview(value)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const [paneHeight, setPaneHeight] = useState<number | null>(null)

  useEffect(() => {
    const el = textareaRef.current
    if (!el) return
    const syncHeight = () => setPaneHeight(el.offsetHeight)
    syncHeight()
    const observer = new ResizeObserver(syncHeight)
    observer.observe(el)
    return () => observer.disconnect()
  }, [])

  const paneStyle = paneHeight ? { height: paneHeight } : undefined

  return (
    <div className="agreement-editor-row">
      <label className="agreement-editor-field">
        <span>{label}</span>
        <textarea
          ref={textareaRef}
          className="agreement-editor-input"
          rows={14}
          style={paneStyle}
          value={value}
          onChange={(e) => onChange(e.target.value)}
        />
      </label>
      <div className="agreement-editor-field">
        <span className="muted">{t('instance.userAgreementPreview')}</span>
        <div className="agreement-text agreement-preview" style={paneStyle}>
          {preview.trim() ? (
            <MarkdownBody text={preview} />
          ) : (
            <p className="muted agreement-preview-empty">{t('agreement.empty')}</p>
          )}
        </div>
      </div>
    </div>
  )
}

export function InstanceLegalDocumentsTab() {
  const { t } = useTranslation()
  const { refresh } = useAuth()
  const [settings, setSettings] = useState<InstanceSettings | null>(null)
  const [savedLegalSnapshot, setSavedLegalSnapshot] = useState<LegalDocsAdminSnapshot | null>(null)
  const [savedFooterSnapshot, setSavedFooterSnapshot] = useState<FooterAdminSnapshot | null>(null)
  const [legalDocTab, setLegalDocTab] = useState<LegalDocumentKey>('user_agreement')
  const [editLang, setEditLang] = useState<LegalDocLocale>('ru')
  const [footerLang, setFooterLang] = useState<LegalDocLocale>('ru')
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [legalSaveBusy, setLegalSaveBusy] = useState(false)
  const [historyOpen, setHistoryOpen] = useState(false)
  const [footerSaveBusy, setFooterSaveBusy] = useState(false)
  const [loading, setLoading] = useState(true)

  async function load() {
    setLoading(true)
    try {
      const data = await api<InstanceSettings>('/instance/settings')
      setSettings(data)
      setSavedLegalSnapshot(legalDocsAdminSnapshot(data))
      setSavedFooterSnapshot(footerAdminSnapshot(data))
    } catch (e) {
      showError(e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [])

  const legalDirty = useMemo(
    () => (settings && savedLegalSnapshot ? legalDocsAdminDirty(savedLegalSnapshot, settings) : false),
    [savedLegalSnapshot, settings],
  )

  const footerDirty = useMemo(
    () => (settings && savedFooterSnapshot ? footerAdminDirty(savedFooterSnapshot, settings) : false),
    [savedFooterSnapshot, settings],
  )

  const currentDocDirty = useMemo(
    () =>
      settings && savedLegalSnapshot
        ? legalDocAdminDirty(savedLegalSnapshot, settings, legalDocTab)
        : false,
    [legalDocTab, savedLegalSnapshot, settings],
  )

  const currentDocWillReaccept = useMemo(() => {
    if (!settings || !savedLegalSnapshot) return false
    return legalDocChangeRequiresReacceptance(
      savedLegalSnapshot.docs[legalDocTab],
      savedLegalDocsFromSettings(settings)[legalDocTab],
    )
  }, [legalDocTab, savedLegalSnapshot, settings])

  function onLegalSaveClick() {
    if (!settings || !savedLegalSnapshot) return
    if (legalDocsChangeRequiresReacceptance(savedLegalSnapshot.docs, settings)) {
      setConfirmOpen(true)
      return
    }
    void saveLegalDocuments()
  }

  function resetLegalEdits() {
    if (!settings || !savedLegalSnapshot) return
    const { docs, published } = savedLegalSnapshot
    setSettings({
      ...settings,
      user_agreement_text_en: docs.user_agreement.en,
      user_agreement_text_ru: docs.user_agreement.ru,
      user_agreement_text_es: docs.user_agreement.es,
      user_agreement_published: published.user_agreement,
      personal_data_consent_text_en: docs.personal_data_consent.en,
      personal_data_consent_text_ru: docs.personal_data_consent.ru,
      personal_data_consent_text_es: docs.personal_data_consent.es,
      personal_data_consent_published: published.personal_data_consent,
      privacy_policy_text_en: docs.privacy_policy.en,
      privacy_policy_text_ru: docs.privacy_policy.ru,
      privacy_policy_text_es: docs.privacy_policy.es,
      privacy_policy_published: published.privacy_policy,
    })
  }

  function resetFooterEdits() {
    if (!settings || !savedFooterSnapshot) return
    setSettings({
      ...settings,
      landing_footer_text_en: savedFooterSnapshot.en,
      landing_footer_text_ru: savedFooterSnapshot.ru,
      landing_footer_text_es: savedFooterSnapshot.es,
      landing_footer_published: savedFooterSnapshot.published,
    })
  }

  async function saveLegalDocuments() {
    if (!settings) return
    setLegalSaveBusy(true)
    try {
      const data = await api<InstanceSettings>('/instance/settings', {
        method: 'PATCH',
        body: JSON.stringify({
          user_agreement_text_en: settings.user_agreement_text_en,
          user_agreement_text_ru: settings.user_agreement_text_ru,
          user_agreement_text_es: settings.user_agreement_text_es,
          user_agreement_published: settings.user_agreement_published,
          personal_data_consent_text_en: settings.personal_data_consent_text_en,
          personal_data_consent_text_ru: settings.personal_data_consent_text_ru,
          personal_data_consent_text_es: settings.personal_data_consent_text_es,
          personal_data_consent_published: settings.personal_data_consent_published,
          privacy_policy_text_en: settings.privacy_policy_text_en,
          privacy_policy_text_ru: settings.privacy_policy_text_ru,
          privacy_policy_text_es: settings.privacy_policy_text_es,
          privacy_policy_published: settings.privacy_policy_published,
        }),
      })
      setSettings(data)
      setSavedLegalSnapshot(legalDocsAdminSnapshot(data))
      setConfirmOpen(false)
      toast.success(t('profile.saved'))
      await refresh()
    } catch (e) {
      showError(e)
    } finally {
      setLegalSaveBusy(false)
    }
  }

  async function saveLandingFooter() {
    if (!settings) return
    setFooterSaveBusy(true)
    try {
      const data = await api<InstanceSettings>('/instance/settings', {
        method: 'PATCH',
        body: JSON.stringify({
          landing_footer_text_en: settings.landing_footer_text_en,
          landing_footer_text_ru: settings.landing_footer_text_ru,
          landing_footer_text_es: settings.landing_footer_text_es,
          landing_footer_published: settings.landing_footer_published,
        }),
      })
      setSettings(data)
      setSavedFooterSnapshot(footerAdminSnapshot(data))
      toast.success(t('profile.saved'))
    } catch (e) {
      showError(e)
    } finally {
      setFooterSaveBusy(false)
    }
  }

  if (loading) {
    return (
      <AdminPage>
        <p className="muted">{t('common.loading')}</p>
      </AdminPage>
    )
  }

  if (!settings || !savedLegalSnapshot || !savedFooterSnapshot) return null

  const docFields = LEGAL_DOC_FIELDS[legalDocTab]
  const docPublished = legalDocPublished(settings, legalDocTab)
  const savedDoc = savedLegalSnapshot.docs[legalDocTab]
  const showPreviewLink =
    savedLegalSnapshot.published[legalDocTab] && legalDocHasContent(savedDoc)
  const editField = docFields.texts[editLang]
  const editValue = (settings[editField] as string | null) || ''
  const footerField = FOOTER_TEXT_FIELDS[footerLang]
  const footerValue = (settings[footerField] as string | null) || ''

  return (
    <AdminPage>
      <AdminFormCard title={t('instance.legalDocumentsTitle')} lead={t('instance.legalDocumentsHint')}>
        <div className="legal-doc-tabs auth-segment" role="tablist" aria-label={t('instance.legalDocumentsTitle')}>
          {LEGAL_DOCUMENT_KEYS.map((key) => {
            const snapshot = savedLegalDocsFromSettings(settings)[key]
            const hasContent = legalDocHasContent(snapshot)
            const published = legalDocPublished(settings, key)
            const changed = legalDocAdminDirty(savedLegalSnapshot, settings, key)
            return (
              <button
                key={key}
                type="button"
                role="tab"
                aria-selected={legalDocTab === key}
                className={legalDocTab === key ? 'active' : undefined}
                onClick={() => setLegalDocTab(key)}
              >
                <span className="legal-doc-tab-label">
                  {t(`legalDocuments.tabs.${LEGAL_DOCUMENT_I18N[key]}`)}
                </span>
                <span className="legal-doc-tab-badges">
                  {!hasContent ? <span className="badge warn">{t('instance.legalDocumentEmpty')}</span> : null}
                  {!published ? <span className="badge">{t('instance.legalDocumentHidden')}</span> : null}
                  {changed ? <span className="badge wait">{t('instance.legalDocumentChanged')}</span> : null}
                </span>
              </button>
            )
          })}
        </div>

        <div className="legal-doc-toolbar">
          <div className="legal-doc-toolbar-meta">
            <span className="badge">
              {t('instance.legalDocumentVersion', {
                version: settings[docFields.version] ?? 0,
              })}
            </span>
            {currentDocDirty ? (
              <span className="badge wait">{t('instance.legalDocumentUnsaved')}</span>
            ) : null}
            {currentDocWillReaccept && currentDocDirty ? (
              <span className="badge warn">{t('instance.legalDocumentReaccept')}</span>
            ) : null}
          </div>
          <div className="legal-doc-toolbar-actions">
            <label className="profile-check-row legal-doc-publish">
              <input
                type="checkbox"
                checked={docPublished}
                onChange={(e) =>
                  setSettings({
                    ...settings,
                    [docFields.published]: e.target.checked,
                  })
                }
              />
              {t('instance.legalDocumentPublish')}
            </label>
            {showPreviewLink ? (
              <Link
                className="btn legal-doc-preview-link"
                to={legalDocPath(legalDocTab)}
                target="_blank"
                rel="noopener noreferrer"
              >
                {t('instance.legalDocumentPreviewLink')}
              </Link>
            ) : null}
            <button type="button" className="btn" onClick={() => setHistoryOpen(true)}>
              {t('instance.legalDocumentHistory')}
            </button>
          </div>
        </div>

        <Segmented
          variant="outline"
          ariaLabel={t('instance.legalDocumentLanguage')}
          value={editLang}
          onChange={setEditLang}
          options={LEGAL_LANG_OPTIONS.map((opt) => ({
            value: opt.value,
            label: t(opt.labelKey),
          }))}
        />

        <AgreementEditorPair
          label={t(LEGAL_DOC_LOCALE_LABEL_KEYS[editLang])}
          value={editValue}
          onChange={(value) =>
            setSettings({
              ...settings,
              [editField]: value,
            })
          }
        />

        <div className="row legal-doc-actions">
          <button
            className="primary"
            type="button"
            disabled={legalSaveBusy || !legalDirty}
            onClick={() => onLegalSaveClick()}
          >
            {t('instance.legalDocumentsSave')}
          </button>
          {legalDirty ? (
            <button type="button" disabled={legalSaveBusy} onClick={() => resetLegalEdits()}>
              {t('common.cancel')}
            </button>
          ) : null}
        </div>
      </AdminFormCard>

      <AdminFormCard title={t('instance.landingExtraTitle')} lead={t('instance.landingExtraHint')}>
        <div className="legal-doc-toolbar">
          <div className="legal-doc-toolbar-meta">
            {footerDirty ? <span className="badge wait">{t('instance.legalDocumentUnsaved')}</span> : null}
          </div>
          <label className="profile-check-row legal-doc-publish">
            <input
              type="checkbox"
              checked={settings.landing_footer_published ?? true}
              onChange={(e) =>
                setSettings({ ...settings, landing_footer_published: e.target.checked })
              }
            />
            {t('instance.legalDocumentPublish')}
          </label>
        </div>

        <Segmented
          variant="outline"
          ariaLabel={t('instance.legalDocumentLanguage')}
          value={footerLang}
          onChange={setFooterLang}
          options={LEGAL_LANG_OPTIONS.map((opt) => ({
            value: opt.value,
            label: t(opt.labelKey),
          }))}
        />

        <AgreementEditorPair
          label={t(LEGAL_DOC_LOCALE_LABEL_KEYS[footerLang])}
          value={footerValue}
          onChange={(value) =>
            setSettings({
              ...settings,
              [footerField]: value,
            })
          }
        />

        <div className="row legal-doc-actions">
          <button
            className="primary"
            type="button"
            disabled={footerSaveBusy || !footerDirty}
            onClick={() => void saveLandingFooter()}
          >
            {t('instance.landingExtraSave')}
          </button>
          {footerDirty ? (
            <button type="button" disabled={footerSaveBusy} onClick={() => resetFooterEdits()}>
              {t('common.cancel')}
            </button>
          ) : null}
        </div>
      </AdminFormCard>

      {historyOpen ? (
        <LegalDocumentHistoryModal documentKey={legalDocTab} onClose={() => setHistoryOpen(false)} />
      ) : null}

      {confirmOpen ? (
        <ConfirmDialog
          message={t('instance.legalDocumentsSaveConfirm')}
          confirmLabel={t('instance.legalDocumentsSave')}
          busy={legalSaveBusy}
          onConfirm={() => void saveLegalDocuments()}
          onClose={() => {
            if (!legalSaveBusy) setConfirmOpen(false)
          }}
        />
      ) : null}
    </AdminPage>
  )
}
