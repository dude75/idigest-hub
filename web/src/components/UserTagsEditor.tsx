import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '../api'
import type { LibraryObjectType, UserTag } from '../types'
import { showError } from '../util'
import { AppSelect } from './app/AppSelect'
import { UserTagChipAssigned } from './UserTagChip'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

type Props = {
  objectType: LibraryObjectType
  objectId: string
  tags: UserTag[]
  onChange: (tags: UserTag[]) => void
}

export function UserTagsEditor({ objectType, objectId, tags, onChange }: Props) {
  const { t } = useTranslation()
  const [draft, setDraft] = useState('')
  const [pickId, setPickId] = useState('')
  const [catalog, setCatalog] = useState<UserTag[]>([])
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    setDraft('')
    setPickId('')
  }, [objectId, objectType])

  useEffect(() => {
    let stop = false
    void api<{ items: UserTag[] }>('/tags')
      .then((r) => {
        if (!stop) setCatalog(r.items)
      })
      .catch(showError)
    return () => {
      stop = true
    }
  }, [objectId, objectType, tags])

  const pickOptions = useMemo(() => {
    const assigned = new Set(tags.map((tag) => tag.name.toLowerCase()))
    return catalog
      .filter((tag) => !assigned.has(tag.name.toLowerCase()))
      .map((tag) => ({ value: tag.id, label: tag.name }))
  }, [catalog, tags])

  async function save(nextNames: string[]) {
    setBusy(true)
    try {
      const r = await api<{ tags: UserTag[] }>('/object-tags', {
        method: 'PUT',
        body: JSON.stringify({ object_type: objectType, object_id: objectId, tags: nextNames }),
      })
      onChange(r.tags)
      const refreshed = await api<{ items: UserTag[] }>('/tags')
      setCatalog(refreshed.items)
    } catch (e) {
      showError(e)
    } finally {
      setBusy(false)
    }
  }

  function addExisting(tagId: string) {
    if (!tagId || busy) return
    const tag = catalog.find((item) => item.id === tagId)
    if (!tag) return
    setPickId('')
    void save([...tags.map((item) => item.name), tag.name])
  }

  function addTag() {
    const name = draft.trim()
    if (!name || busy) return
    const exists = tags.some((tag) => tag.name.toLowerCase() === name.toLowerCase())
    if (exists) {
      setDraft('')
      return
    }
    void save([...tags.map((tag) => tag.name), name])
    setDraft('')
  }

  function removeTag(tagId: string) {
    if (busy) return
    void save(tags.filter((tag) => tag.id !== tagId).map((tag) => tag.name))
  }

  return (
    <div className="user-tags-editor">
      <span className="user-tags-label muted text-sm">{t('library.myTags')}</span>
      <div className="user-tags-controls">
        {pickOptions.length > 0 ? (
          <AppSelect
            className="user-tags-pick [&_[data-slot=select-trigger]]:shadow-none [&_[data-slot=select-trigger]]:focus-visible:ring-0 [&_[data-slot=select-trigger]]:focus-visible:border-input"
            value={pickId}
            disabled={busy}
            placeholder={t('library.pickTag')}
            options={pickOptions}
            size="sm"
            onValueChange={(value) => {
              setPickId(value)
              if (value) addExisting(value)
            }}
          />
        ) : null}
        <Input
          className="user-tags-input shadow-none focus-visible:border-input focus-visible:ring-0"
          value={draft}
          disabled={busy}
          placeholder={t('library.addTagPlaceholder')}
          aria-label={t('library.addTagPlaceholder')}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault()
              addTag()
            }
          }}
        />
        <Button
          type="button"
          size="sm"
          variant="outline"
          className="user-tags-add shrink-0"
          disabled={busy || !draft.trim()}
          onClick={() => addTag()}
        >
          {t('library.addTag')}
        </Button>
      </div>
      {tags.map((tag) => (
        <UserTagChipAssigned
          key={tag.id}
          name={tag.name}
          disabled={busy}
          removeLabel={t('library.removeTag', { name: tag.name })}
          onRemove={() => removeTag(tag.id)}
        />
      ))}
    </div>
  )
}
