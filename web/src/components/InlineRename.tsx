import { useEffect, useMemo, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { AdminFormActions, AppSubmitButton } from './app/AdminUi'

type Props = {
  value: string
  canEdit: boolean
  busy?: boolean
  onSave: (name: string) => Promise<void>
}

export function InlineRename({ value, canEdit, busy, onSave }: Props) {
  const { t } = useTranslation()
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(value)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (!editing) setDraft(value)
  }, [value, editing])

  useEffect(() => {
    if (editing) inputRef.current?.focus()
  }, [editing])

  const renameReady = useMemo(() => {
    const next = draft.trim()
    return next.length > 0 && next !== value
  }, [draft, value])

  async function save() {
    const next = draft.trim()
    if (!next || next === value) {
      setEditing(false)
      setDraft(value)
      return
    }
    await onSave(next)
    setEditing(false)
  }

  if (editing) {
    return (
      <div className="row inline-rename">
        <input
          ref={inputRef}
          className="inline-rename-input"
          value={draft}
          disabled={busy}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') void save()
            if (e.key === 'Escape') {
              setDraft(value)
              setEditing(false)
            }
          }}
        />
        <AdminFormActions>
          <AppSubmitButton ready={renameReady} busy={busy} onClick={() => void save()}>
            {t('common.save')}
          </AppSubmitButton>
          <Button
            type="button"
            variant="outline"
            disabled={busy}
            onClick={() => {
              setDraft(value)
              setEditing(false)
            }}
          >
            {t('common.cancel')}
          </Button>
        </AdminFormActions>
      </div>
    )
  }

  return (
    <div className="row inline-rename">
      <h1 className="grow">{value}</h1>
      {canEdit && (
        <Button type="button" className="inline-rename-btn" disabled={busy} onClick={() => setEditing(true)}>
          {t('common.rename')}
        </Button>
      )}
    </div>
  )
}
