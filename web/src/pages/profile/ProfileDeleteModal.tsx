import { Modal } from '../../components/Modal'
import { Button } from '@/components/ui/button'
import { AppInputField, AppSelectField } from '../../components/app/AppFormControls'
import { userPickerLabel } from '../../userDisplay'
import { useProfilePage } from './ProfilePageContext'

export function ProfileDeleteModal() {
  const {
    t,
    me,
    deleteOpen,
    setDeleteOpen,
    deletePreview,
    deletePassword,
    setDeletePassword,
    deleteTotp,
    setDeleteTotp,
    deleteSuccessor,
    setDeleteSuccessor,
    deleteBusy,
    showLocalAuthDelete,
    confirmDeleteAccount,
  } = useProfilePage()

  if (!deleteOpen || !deletePreview) return null

  return (
    <Modal
      onClose={() => {
        if (deleteBusy) return
        setDeleteOpen(false)
      }}
      closeOnBackdrop={!deleteBusy}
      panelClassName="stack"
    >
      <h2>{t('profile.deleteAccount')}</h2>
      <p className="err">{t('profile.deleteAccountLead')}</p>
      {deletePreview.will_delete_org && <p className="err">{t('profile.deleteAccountWillDeleteOrg')}</p>}
      {deletePreview.requires_successor && (
        <>
          <p className="muted">{t('profile.deleteAccountSuccessorHint')}</p>
          <AppSelectField
            label={t('profile.deleteAccountSuccessor')}
            htmlFor="profile-delete-successor"
            required
            value={deleteSuccessor}
            disabled={deleteBusy}
            onValueChange={setDeleteSuccessor}
            options={[
              ...(deletePreview.candidates.length > 1 ? [{ value: '', label: t('org.target') }] : []),
              ...deletePreview.candidates.map((c) => ({
                value: c.id,
                label: userPickerLabel(c),
              })),
            ]}
          />
        </>
      )}
      {showLocalAuthDelete && (
        <AppInputField
          label={t('profile.deleteAccountPassword')}
          htmlFor="profile-delete-pw"
          type="password"
          required
          autoComplete="current-password"
          value={deletePassword}
          disabled={deleteBusy}
          onChange={(e) => setDeletePassword(e.target.value)}
        />
      )}
      {me?.mfa_enabled && (
        <AppInputField
          label={t('profile.deleteAccountTotp')}
          htmlFor="profile-delete-totp"
          type="text"
          required
          autoComplete="one-time-code"
          value={deleteTotp}
          disabled={deleteBusy}
          onChange={(e) => setDeleteTotp(e.target.value)}
        />
      )}
      <div className="modal-actions flex flex-wrap items-center gap-2">
        <Button
          type="button"
          variant="destructive"
          disabled={
            deleteBusy ||
            (deletePreview.requires_successor && !deleteSuccessor) ||
            (showLocalAuthDelete && !deletePassword) ||
            (Boolean(me?.mfa_enabled) && !deleteTotp.trim())
          }
          onClick={() => void confirmDeleteAccount()}
        >
          {deleteBusy ? t('profile.deleteAccountBusy') : t('profile.deleteAccountConfirm')}
        </Button>
        <Button type="button" disabled={deleteBusy} onClick={() => setDeleteOpen(false)}>
          {t('common.cancel')}
        </Button>
      </div>
    </Modal>
  )
}
