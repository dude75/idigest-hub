import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'

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
        <button className="primary" type="button" disabled={busy} onClick={() => void save()}>
          {t('common.save')}
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() => {
            setDraft(value)
            setEditing(false)
          }}
        >
          {t('common.cancel')}
        </button>
      </div>
    )
  }

  return (
    <div className="row inline-rename">
      <h1 className="grow">{value}</h1>
      {canEdit && (
        <button type="button" className="inline-rename-btn" disabled={busy} onClick={() => setEditing(true)}>
          {t('common.rename')}
        </button>
      )}
    </div>
  )
}
