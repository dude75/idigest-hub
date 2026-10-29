import { Card, CardContent } from '@/components/ui/card'
import { ProfileCardHeader } from './ProfileCardHeader'
import { AppCheckboxRow, AppInputField, AppSelectField } from '../../components/app/AppFormControls'
import {
  diarizationOptionsForAsr,
  resolveEffectiveAsr,
  resolveEffectiveDiarization,
} from '../../transcribeModels'
import { resolveEffectiveSummarizeModel } from '../../summarizeModels'
import { useProfilePage } from './ProfilePageContext'
import { ProfileSection, ProfileSectionDivider } from './ProfileSection'
import { appMutedText } from '../../components/app/appTypography'

export function ProfileModelsTab() {
  const {
    t,
    me,
    showTranscribeSection,
    showSummarizeSection,
    showCaptureSection,
    asrModel,
    setAsrModelLocal,
    diarizationModel,
    setDiarizationModelLocal,
    toneAnalytics,
    setToneAnalyticsLocal,
    availableDiarizationModels,
    transcribeComboValid,
    transcribeReady,
    transcribeOk,
    setTranscribeOk,
    tariffAllowsTone,
    saveTranscribePrefs,
    summarizeModel,
    setSummarizeModelLocal,
    summarizeModelValid,
    summarizeReady,
    summarizeOk,
    setSummarizeOk,
    saveSummarizePrefs,
    captureBotName,
    setCaptureBotNameLocal,
    captureBotDirty,
    captureBotOk,
    setCaptureBotOk,
    captureBotEffective,
    saveCaptureBotPrefs,
  } = useProfilePage()

  if (!me) return null

  return (
    <Card className="admin-form-card">
      <ProfileCardHeader title={t('profile.tabModels')} lead={t('profile.tabModelsLead')} />
      <CardContent className="flex flex-col gap-6">
        {showTranscribeSection && (
          <ProfileSection
            title={t('profile.transcribeTitle')}
            description={t('profile.transcribeHint')}
            saveReady={transcribeReady}
            onSave={() => void saveTranscribePrefs()}
            saved={transcribeOk}
          >
            {(me.transcribe_models.asr_models.length > 0 ||
              me.transcribe_models.diarization_models.length > 0) && (
              <div className="grid gap-3 sm:grid-cols-2">
                <AppSelectField
                  label={t('instance.asr')}
                  htmlFor="profile-asr"
                  value={asrModel}
                  onValueChange={(nextAsr) => {
                    setTranscribeOk(false)
                    setAsrModelLocal(nextAsr)
                    const effectiveAsr = resolveEffectiveAsr(nextAsr, me.transcribe_prefs)
                    const allowedDiar = diarizationOptionsForAsr(me.transcribe_models, effectiveAsr)
                    if (
                      diarizationModel !== 'inherit' &&
                      diarizationModel !== 'off' &&
                      !allowedDiar.includes(diarizationModel)
                    ) {
                      setDiarizationModelLocal('inherit')
                    }
                  }}
                  options={[
                    {
                      value: 'inherit',
                      label: t('profile.dateTimeInherit', { value: me.transcribe_prefs.instance_asr_model }),
                    },
                    ...me.transcribe_models.asr_models.map((modelId) => ({ value: modelId, label: modelId })),
                  ]}
                />
                <AppSelectField
                  label={t('instance.diarization')}
                  htmlFor="profile-diarization"
                  value={diarizationModel}
                  onValueChange={(next) => {
                    setTranscribeOk(false)
                    setDiarizationModelLocal(next)
                  }}
                  options={[
                    {
                      value: 'inherit',
                      label: t('profile.transcribeDiarizationInherit', {
                        value: me.transcribe_prefs.instance_diarization_model || t('instance.diarizationOff'),
                      }),
                    },
                    { value: 'off', label: t('instance.diarizationOff') },
                    ...availableDiarizationModels.map((modelId) => ({ value: modelId, label: modelId })),
                  ]}
                />
              </div>
            )}
            {me.org ? (
              <div>
                <AppCheckboxRow
                  id="profile-tone-analytics"
                  label={t('profile.toneAnalytics', {
                    state: toneAnalytics && tariffAllowsTone ? t('profile.toneOn') : t('profile.toneOff'),
                  })}
                  checked={tariffAllowsTone && toneAnalytics}
                  disabled={!tariffAllowsTone}
                  onCheckedChange={(checked) => {
                    setTranscribeOk(false)
                    setToneAnalyticsLocal(checked)
                  }}
                />
                <p className={appMutedText}>
                  {tariffAllowsTone ? t('profile.toneAnalyticsHint') : t('profile.toneTariffLocked')}
                </p>
              </div>
            ) : null}
            {(me.transcribe_models.asr_models.length > 0 || me.transcribe_models.diarization_models.length > 0) && (
              <p className={appMutedText}>
                {t('profile.transcribePreview', {
                  asr: resolveEffectiveAsr(asrModel, me.transcribe_prefs),
                  diarization:
                    resolveEffectiveDiarization(diarizationModel, me.transcribe_prefs) ||
                    t('instance.diarizationOff'),
                })}
              </p>
            )}
            {!transcribeComboValid ? <p className="err">{t('profile.transcribeComboInvalid')}</p> : null}
          </ProfileSection>
        )}

        {showSummarizeSection && (
          <>
            {showTranscribeSection ? <ProfileSectionDivider /> : null}
            <ProfileSection
              title={t('profile.summarizeTitle')}
              description={t('profile.summarizeHint')}
              saveReady={summarizeReady}
              onSave={() => void saveSummarizePrefs()}
              saved={summarizeOk}
            >
              <AppSelectField
                label={t('instance.summarizeModelLabel')}
                htmlFor="profile-summarize"
                value={summarizeModel}
                onValueChange={(next) => {
                  setSummarizeOk(false)
                  setSummarizeModelLocal(next)
                }}
                options={[
                  {
                    value: 'inherit',
                    label: t('profile.dateTimeInherit', {
                      value: me.summarize_prefs.instance_summarize_model || t('instance.summarizeModelUnset'),
                    }),
                  },
                  ...me.summarize_models.summarize_models.map((modelId) => ({ value: modelId, label: modelId })),
                ]}
              />
              <p className={appMutedText}>
                {t('profile.summarizePreview', {
                  model:
                    resolveEffectiveSummarizeModel(summarizeModel, me.summarize_prefs) ||
                    t('instance.summarizeModelUnset'),
                })}
              </p>
              {!summarizeModelValid ? <p className="err">{t('profile.summarizeModelInvalid')}</p> : null}
            </ProfileSection>
          </>
        )}

        {showCaptureSection && (
          <>
            {showTranscribeSection || showSummarizeSection ? <ProfileSectionDivider /> : null}
            <ProfileSection
              title={t('profile.captureBotTitle')}
              description={t('profile.captureBotHint')}
              saveReady={captureBotDirty}
              onSave={() => void saveCaptureBotPrefs()}
              saved={captureBotOk}
            >
              <AppInputField
                label={t('org.captureBotDisplayName')}
                htmlFor="profile-capture-bot"
                type="text"
                value={captureBotName}
                maxLength={128}
                placeholder={t('profile.captureBotInherit', { value: me.capture_prefs.org_bot_display_name })}
                onChange={(e) => {
                  setCaptureBotOk(false)
                  setCaptureBotNameLocal(e.target.value)
                }}
              />
              <p className={appMutedText}>{t('org.captureBotDisplayNameHint')}</p>
              <p className={appMutedText}>{t('profile.captureBotPreview', { name: captureBotEffective })}</p>
            </ProfileSection>
          </>
        )}
      </CardContent>
    </Card>
  )
}
