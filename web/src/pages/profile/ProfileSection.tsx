import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { FieldLegend, FieldSet } from '@/components/ui/field'
import { Separator } from '@/components/ui/separator'
import { AdminFormActions, AppSubmitButton } from '../../components/app/AdminUi'

type ProfileSectionProps = {
  title: string
  /** In-page anchor on the section heading (`#id` in URL). */
  headingId?: string
  description?: ReactNode
  children: ReactNode
  saveReady?: boolean
  onSave?: () => void
  saved?: boolean
  saveLabel?: string
  savedLabel?: string
  trailing?: ReactNode
}

export function ProfileSection({
  title,
  headingId,
  description,
  children,
  saveReady,
  onSave,
  saved,
  saveLabel,
  savedLabel,
  trailing,
}: ProfileSectionProps) {
  const { t } = useTranslation()
  const showSave = onSave != null
  const resolvedSaveLabel = saveLabel ?? t('common.save')
  const resolvedSavedLabel = savedLabel ?? t('profile.saved')

  return (
    <FieldSet className="gap-3">
      <div className="profile-section-head">
        <FieldLegend
          id={headingId}
          variant="label"
          className="profile-section-title profile-section-heading-anchor mb-0"
        >
          {title}
        </FieldLegend>
        {description ? <p className="profile-section-lead admin-lead">{description}</p> : null}
      </div>
      <div className="flex flex-col gap-3">{children}</div>
      {showSave ? (
        <AdminFormActions className="profile-actions">
          <AppSubmitButton ready={Boolean(saveReady)} onClick={onSave}>
            {resolvedSaveLabel}
          </AppSubmitButton>
          {saved ? <p className="ok">{resolvedSavedLabel}</p> : null}
        </AdminFormActions>
      ) : null}
      {trailing}
    </FieldSet>
  )
}

export function ProfileSectionDivider() {
  return <Separator className="my-1" />
}
