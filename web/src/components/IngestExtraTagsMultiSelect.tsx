import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { ApiError } from '../api'
import {
  USER_TAG_MAX_PER_OBJECT,
  normalizeUserTagName,
  userTagNameErrorKey,
} from '../constants/userTags'
import type { SchemaUserTagListResponse } from '../openapi'
import { showError } from '../util'
import { AppSelect } from './app/AppSelect'
import { Modal } from './Modal'
import { UserTagChipAssigned } from './UserTagChip'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'

type CatalogItem = NonNullable<SchemaUserTagListResponse['items']>[number]

type Props = {
  catalog: CatalogItem[]
  selected: string[]
  disabled?: boolean
  className?: string
  onChange: (names: string[]) => void
}

export function IngestExtraTagsMultiSelect({ catalog, selected, disabled, className, onChange }: Props) {
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)
  const [draftSelected, setDraftSelected] = useState<string[]>([])
  const [draft, setDraft] = useState('')
  const [pickId, setPickId] = useState('')

  useEffect(() => {
    if (!open) return
    setDraftSelected([...selected])
    setDraft('')
    setPickId('')
  }, [open, selected])

  const pickOptions = useMemo(() => {
    const assigned = new Set(draftSelected.map((name) => name.toLowerCase()))
    return catalog
      .filter((tag) => !assigned.has(tag.name.toLowerCase()))
      .map((tag) => ({ value: tag.id, label: tag.name }))
  }, [catalog, draftSelected])

  function tryAdd(name: string) {
    const invalid = userTagNameErrorKey(name)
    if (invalid) {
      showError(new ApiError(invalid, t(`errors.${invalid}`)))
      return
    }
    const normalized = normalizeUserTagName(name)
    if (draftSelected.some((item) => item.toLowerCase() === normalized.toLowerCase())) return
    const next = [...draftSelected, normalized]
    if (next.length > USER_TAG_MAX_PER_OBJECT - 1) {
      showError(new ApiError('user_tag_limit_per_object', t('errors.user_tag_limit_per_object')))
      return
    }
    setDraftSelected(next)
  }

  function addExisting(tagId: string) {
    if (!tagId) return
    const tag = catalog.find((item) => item.id === tagId)
    if (!tag) return
    setPickId('')
    tryAdd(tag.name)
  }

  function addDraftTag() {
    if (!draft.trim()) return
    tryAdd(draft)
    setDraft('')
  }

  function removeTag(name: string) {
    setDraftSelected(draftSelected.filter((item) => item !== name))
  }

  function applyAndClose() {
    onChange(draftSelected)
    setOpen(false)
  }

  const triggerHint =
    selected.length > 0
      ? t('library.ingestExtraTagsCount', { count: selected.length })
      : undefined

  return (
    <>
      <Button
        type="button"
        variant="outline"
        disabled={disabled}
        aria-label={triggerHint ? `${t('library.ingestExtraTags')} — ${triggerHint}` : t('library.ingestExtraTags')}
        className={cn(
          'library-ingest-tags-trigger h-8 shrink-0 px-2.5 font-normal',
          selected.length > 0 && 'border-primary/40',
          className,
        )}
        onClick={() => setOpen(true)}
      >
        <span className="truncate">{t('library.ingestExtraTags')}</span>
        {selected.length > 0 ? (
          <span className="text-muted-foreground tabular-nums">({selected.length})</span>
        ) : null}
      </Button>
      {open ? (
        <Modal
          title={t('library.ingestExtraTags')}
          description={t('library.ingestExtraTagsHint')}
          onClose={() => setOpen(false)}
          footer={
            <Button type="button" onClick={() => applyAndClose()}>
              {t('common.save')}
            </Button>
          }
        >
          <div className="user-tags-editor">
            <div className="user-tags-row">
              <span className="user-tags-label muted text-sm">{t('library.myTags')}</span>
              {pickOptions.length > 0 ? (
                <AppSelect
                  className="user-tags-pick [&_[data-slot=select-trigger]]:shadow-none [&_[data-slot=select-trigger]]:focus-visible:ring-0 [&_[data-slot=select-trigger]]:focus-visible:border-input"
                  value={pickId}
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
                placeholder={t('library.addTagPlaceholder')}
                aria-label={t('library.addTagPlaceholder')}
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault()
                    addDraftTag()
                  }
                }}
              />
              <Button
                type="button"
                size="default"
                variant="outline"
                className="user-tags-add shrink-0"
                disabled={!draft.trim()}
                onClick={() => addDraftTag()}
              >
                {t('library.addTag')}
              </Button>
              {draftSelected.map((name) => (
                <UserTagChipAssigned
                  key={name}
                  name={name}
                  removeLabel={t('library.removeTag', { name })}
                  onRemove={() => removeTag(name)}
                />
              ))}
            </div>
            {catalog.length === 0 && draftSelected.length === 0 ? (
              <p className="muted m-0 text-sm">{t('library.noTagsYet')}</p>
            ) : null}
          </div>
        </Modal>
      ) : null}
    </>
  )
}
