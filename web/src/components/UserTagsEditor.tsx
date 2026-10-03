import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { ApiError, api } from '../api'
import {
  USER_TAG_MAX_PER_OBJECT,
  normalizeUserTagName,
  userTagNameErrorKey,
} from '../constants/userTags'
import type { SchemaObjectTagsResponse, SchemaUserTagListResponse, SchemaUserTagBrief } from '../openapi'
import type { LibraryObjectType } from '../types'
import { showError } from '../util'
import { AppSelect } from './app/AppSelect'
import { UserTagChipAssigned } from './UserTagChip'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

type Props = {
  objectType: LibraryObjectType
  objectId: string
  tags: SchemaUserTagBrief[]
  onChange: (tags: SchemaUserTagBrief[]) => void
}

export function UserTagsEditor({ objectType, objectId, tags, onChange }: Props) {
  const { t } = useTranslation()
  const [draft, setDraft] = useState('')
  const [pickId, setPickId] = useState('')
  const [catalog, setCatalog] = useState<NonNullable<SchemaUserTagListResponse['items']>>([])
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    setDraft('')
    setPickId('')
  }, [objectId, objectType])

  useEffect(() => {
    let stop = false
    void api<SchemaUserTagListResponse>('/tags')
      .then((r) => {
        if (!stop) setCatalog(r.items ?? [])
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

  function cleanedTagNames(nextNames: string[]): string[] | null {
    const cleaned: string[] = []
    const seenKeys = new Set<string>()
    for (const raw of nextNames) {
      const invalid = userTagNameErrorKey(raw)
      if (invalid) {
        showError(new ApiError(invalid, t(`errors.${invalid}`)))
        return null
      }
      const name = normalizeUserTagName(raw)
      const key = name.toLowerCase()
      if (seenKeys.has(key)) continue
      seenKeys.add(key)
      cleaned.push(name)
    }
    if (cleaned.length > USER_TAG_MAX_PER_OBJECT) {
      showError(new ApiError('user_tag_limit_per_object', t('errors.user_tag_limit_per_object')))
      return null
    }
    return cleaned
  }

  async function save(nextNames: string[]) {
    const cleaned = cleanedTagNames(nextNames)
    if (!cleaned) return
    setBusy(true)
    try {
      const r = await api<SchemaObjectTagsResponse>('/object-tags', {
        method: 'PUT',
        body: JSON.stringify({ object_type: objectType, object_id: objectId, tags: cleaned }),
      })
      onChange(r.tags ?? [])
      const refreshed = await api<SchemaUserTagListResponse>('/tags')
      setCatalog(refreshed.items ?? [])
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
    if (busy) return
    const invalid = userTagNameErrorKey(draft)
    if (invalid) {
      showError(new ApiError(invalid, t(`errors.${invalid}`)))
      return
    }
    const name = normalizeUserTagName(draft)
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
      <div className="user-tags-row">
        <span className="user-tags-label muted text-sm">{t('library.myTags')}</span>
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
    </div>
  )
}
