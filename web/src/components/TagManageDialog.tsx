import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { ApiError, api } from '../api'
import { normalizeUserTagName, userTagNameErrorKey } from '../constants/userTags'
import type { UserTag } from '../types'
import { showError } from '../util'
import { AppSubmitButton } from './app/AdminUi'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Modal } from './Modal'
import { ConfirmDialog } from './ConfirmDialog'

type Props = {
  onClose: () => void
  onUpdated: () => void
}

export function TagManageDialog({ onClose, onUpdated }: Props) {
  const { t } = useTranslation()
  const [items, setItems] = useState<UserTag[]>([])
  const [loading, setLoading] = useState(true)
  const [renameId, setRenameId] = useState<string | null>(null)
  const [renameDraft, setRenameDraft] = useState('')
  const [deleteId, setDeleteId] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function load() {
    setLoading(true)
    try {
      const r = await api<{ items: UserTag[] }>('/tags')
      setItems(r.items)
    } catch (e) {
      showError(e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [])

  const renameTarget = renameId ? items.find((tag) => tag.id === renameId) : null
  const renameReady = useMemo(() => {
    if (!renameTarget) return false
    if (userTagNameErrorKey(renameDraft)) return false
    return normalizeUserTagName(renameDraft) !== renameTarget.name
  }, [renameDraft, renameTarget])

  async function saveRename(tagId: string) {
    const invalid = userTagNameErrorKey(renameDraft)
    if (invalid) {
      showError(new ApiError(invalid, t(`errors.${invalid}`)))
      return
    }
    const name = normalizeUserTagName(renameDraft)
    const target = items.find((tag) => tag.id === tagId)
    if (!target || name === target.name) {
      setRenameId(null)
      return
    }
    setBusy(true)
    try {
      await api(`/tags/${tagId}`, { method: 'PATCH', body: JSON.stringify({ name }) })
      setRenameId(null)
      await load()
      onUpdated()
    } catch (e) {
      showError(e)
    } finally {
      setBusy(false)
    }
  }

  async function confirmDelete() {
    if (!deleteId) return
    setBusy(true)
    try {
      await api(`/tags/${deleteId}`, { method: 'DELETE' })
      setDeleteId(null)
      await load()
      onUpdated()
    } catch (e) {
      showError(e)
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <Modal
        onClose={onClose}
        closeOnBackdrop={!busy}
        title={t('library.manageTags')}
        description={t('library.manageTagsHint')}
        panelClassName="flex max-h-[min(90dvh,40rem)] flex-col overflow-hidden sm:max-w-lg"
        footer={
          <Button type="button" variant="outline" onClick={onClose} disabled={busy}>
            {t('common.close')}
          </Button>
        }
      >
        <div className="min-h-0 flex-1 overflow-y-auto pr-1">
          {loading ? (
            <p className="muted">{t('common.loading')}</p>
          ) : items.length === 0 ? (
            <p className="muted">{t('library.noTagsYet')}</p>
          ) : (
            <ul className="tag-manage-list">
              {items.map((tag) => (
                <li key={tag.id} className="tag-manage-row">
                  {renameId === tag.id ? (
                    <div className="flex flex-wrap items-center gap-2">
                      <Input
                        className="h-8 flex-1 min-w-[8rem]"
                        value={renameDraft}
                        disabled={busy}
                        autoFocus
                        onChange={(e) => setRenameDraft(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') void saveRename(tag.id)
                          if (e.key === 'Escape') setRenameId(null)
                        }}
                      />
                      <AppSubmitButton
                        size="sm"
                        ready={renameReady}
                        busy={busy}
                        onClick={() => void saveRename(tag.id)}
                      >
                        {t('common.save')}
                      </AppSubmitButton>
                      <Button type="button" size="sm" variant="outline" disabled={busy} onClick={() => setRenameId(null)}>
                        {t('common.cancel')}
                      </Button>
                    </div>
                  ) : (
                    <>
                      <span className="tag-manage-name">{tag.name}</span>
                      <span className="muted text-sm">{t('library.tagUsage', { count: tag.usage_count ?? 0 })}</span>
                      <span className="tag-manage-actions">
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          disabled={busy}
                          onClick={() => {
                            setRenameId(tag.id)
                            setRenameDraft(tag.name)
                          }}
                        >
                          {t('common.rename')}
                        </Button>
                        <Button type="button" size="sm" variant="destructive" disabled={busy} onClick={() => setDeleteId(tag.id)}>
                          {t('common.delete')}
                        </Button>
                      </span>
                    </>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      </Modal>
      {deleteId ? (
        <ConfirmDialog
          message={t('library.deleteTagConfirm', { name: items.find((tag) => tag.id === deleteId)?.name || '' })}
          confirmLabel={t('common.delete')}
          danger
          busy={busy}
          onConfirm={() => void confirmDelete()}
          onClose={() => setDeleteId(null)}
        />
      ) : null}
    </>
  )
}
