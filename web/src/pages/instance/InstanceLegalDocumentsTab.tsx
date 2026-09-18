import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import { api } from '../../api'
import { useAuth } from '../../auth'
import type { InstanceSettings } from '../../types'
import { AdminPage } from '../../components/AdminSection'
import { ConfirmDialog } from '../../components/ConfirmDialog'
import { Segmented } from '../../components/Segmented'
import { MarkdownBody } from '../../markdown'
import {
  LEGAL_DOC_FIELDS,
  LEGAL_DOCUMENT_I18N,
  LEGAL_DOCUMENT_KEYS,
  legalDocsChangeRequiresReacceptance,
  savedLegalDocsFromSettings,
  type LegalDocumentKey,
  type SavedLegalDocs,
} from '../../legalDocuments'
import { showError } from '../../util'
import { useAgreementPreview } from './useAgreementPreview'

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
          rows={12}
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
  const [savedLegalDocs, setSavedLegalDocs] = useState<SavedLegalDocs | null>(null)
  const [legalDocTab, setLegalDocTab] = useState<LegalDocumentKey>('user_agreement')
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [legalSaveBusy, setLegalSaveBusy] = useState(false)
  const [footerSaveBusy, setFooterSaveBusy] = useState(false)

  async function load() {
    const data = await api<InstanceSettings>('/instance/settings')
    setSettings(data)
    setSavedLegalDocs(savedLegalDocsFromSettings(data))
  }

  useEffect(() => {
    load().catch(showError)
  }, [])

  function onLegalSaveClick() {
    if (!settings || !savedLegalDocs) return
    if (legalDocsChangeRequiresReacceptance(savedLegalDocs, settings)) {
      setConfirmOpen(true)
      return
    }
    void saveLegalDocuments()
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
          user_agreement_published: settings.user_agreement_published,
          personal_data_consent_text_en: settings.personal_data_consent_text_en,
          personal_data_consent_text_ru: settings.personal_data_consent_text_ru,
          personal_data_consent_published: settings.personal_data_consent_published,
          privacy_policy_text_en: settings.privacy_policy_text_en,
          privacy_policy_text_ru: settings.privacy_policy_text_ru,
          privacy_policy_published: settings.privacy_policy_published,
        }),
      })
      setSettings(data)
      setSavedLegalDocs(savedLegalDocsFromSettings(data))
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
          landing_footer_published: settings.landing_footer_published,
        }),
      })
      setSettings(data)
      toast.success(t('profile.saved'))
    } catch (e) {
      showError(e)
    } finally {
      setFooterSaveBusy(false)
    }
  }

  if (!settings) return null

  return (
    <AdminPage>
      <div className="card stack">
        <p className="muted">{t('instance.legalDocumentsHint')}</p>
        <Segmented
          variant="segment"
          ariaLabel={t('instance.legalDocumentsTitle')}
          value={legalDocTab}
          onChange={setLegalDocTab}
          options={LEGAL_DOCUMENT_KEYS.map((key) => ({
            value: key,
            label: t(`legalDocuments.tabs.${LEGAL_DOCUMENT_I18N[key]}`),
          }))}
        />
        <p className="muted">
          {t('instance.legalDocumentVersion', {
            version: settings[LEGAL_DOC_FIELDS[legalDocTab].version] ?? 0,
          })}
        </p>
        <label className="profile-check-row">
          <input
            type="checkbox"
            checked={(settings[LEGAL_DOC_FIELDS[legalDocTab].published] as boolean | undefined) ?? true}
            onChange={(e) =>
              setSettings({
                ...settings,
                [LEGAL_DOC_FIELDS[legalDocTab].published]: e.target.checked,
              })
            }
          />
          {t('instance.legalDocumentPublish')}
        </label>
        <AgreementEditorPair
          label={t('instance.userAgreementEn')}
          value={(settings[LEGAL_DOC_FIELDS[legalDocTab].en] as string | null) || ''}
          onChange={(value) =>
            setSettings({ ...settings, [LEGAL_DOC_FIELDS[legalDocTab].en]: value })
          }
        />
        <AgreementEditorPair
          label={t('instance.userAgreementRu')}
          value={(settings[LEGAL_DOC_FIELDS[legalDocTab].ru] as string | null) || ''}
          onChange={(value) =>
            setSettings({ ...settings, [LEGAL_DOC_FIELDS[legalDocTab].ru]: value })
          }
        />
        <div className="row">
          <button
            className="primary"
            type="button"
            disabled={legalSaveBusy}
            onClick={() => onLegalSaveClick()}
          >
            {t('instance.legalDocumentsSave')}
          </button>
        </div>
      </div>

      <div className="card stack">
        <h2 className="legal-section-title">{t('instance.landingExtraTitle')}</h2>
        <p className="muted">{t('instance.landingExtraHint')}</p>
        <label className="profile-check-row">
          <input
            type="checkbox"
            checked={settings.landing_footer_published ?? true}
            onChange={(e) =>
              setSettings({ ...settings, landing_footer_published: e.target.checked })
            }
          />
          {t('instance.legalDocumentPublish')}
        </label>
        <AgreementEditorPair
          label={t('instance.userAgreementEn')}
          value={settings.landing_footer_text_en || ''}
          onChange={(landing_footer_text_en) =>
            setSettings({ ...settings, landing_footer_text_en })
          }
        />
        <AgreementEditorPair
          label={t('instance.userAgreementRu')}
          value={settings.landing_footer_text_ru || ''}
          onChange={(landing_footer_text_ru) =>
            setSettings({ ...settings, landing_footer_text_ru })
          }
        />
        <div className="row">
          <button
            className="primary"
            type="button"
            disabled={footerSaveBusy}
            onClick={() => void saveLandingFooter()}
          >
            {t('instance.landingExtraSave')}
          </button>
        </div>
      </div>

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
