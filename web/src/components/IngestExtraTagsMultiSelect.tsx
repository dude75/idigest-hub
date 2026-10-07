import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { TagsIcon } from 'lucide-react'
import { ApiError } from '../api'
import {
  USER_TAG_MAX_PER_OBJECT,
  normalizeUserTagName,
  userTagNameErrorKey,
} from '../constants/userTags'
import type { SchemaUserTagListResponse } from '../openapi'
import { showError } from '../util'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Popover,
  PopoverContent,
  PopoverDescription,
  PopoverHeader,
  PopoverTitle,
  PopoverTrigger,
} from '@/components/ui/popover'
import { cn } from '@/lib/utils'

type CatalogItem = NonNullable<SchemaUserTagListResponse['items']>[number]

type Props = {
  catalog: CatalogItem[]
  selected: string[]
  disabled?: boolean
  onChange: (names: string[]) => void
}

function selectedKeys(selected: string[]): Set<string> {
  return new Set(selected.map((name) => name.toLowerCase()))
}

export function IngestExtraTagsMultiSelect({ catalog, selected, disabled, onChange }: Props) {
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)
  const [draft, setDraft] = useState('')

  const keys = useMemo(() => selectedKeys(selected), [selected])

  const orphanSelected = useMemo(
    () =>
      selected.filter(
        (name) => !catalog.some((tag) => tag.name.toLowerCase() === name.toLowerCase()),
      ),
    [catalog, selected],
  )

  const listItems = useMemo(() => {
    const rows: { key: string; name: string; id?: string }[] = catalog.map((tag) => ({
      key: tag.id,
      id: tag.id,
      name: tag.name,
    }))
    for (const name of orphanSelected) {
      rows.push({ key: `orphan:${name.toLowerCase()}`, name })
    }
    return rows.sort((a, b) => a.name.localeCompare(b.name, undefined, { sensitivity: 'base' }))
  }, [catalog, orphanSelected])

  function tryAdd(name: string) {
    if (disabled) return
    const invalid = userTagNameErrorKey(name)
    if (invalid) {
      showError(new ApiError(invalid, t(`errors.${invalid}`)))
      return
    }
    const normalized = normalizeUserTagName(name)
    if (keys.has(normalized.toLowerCase())) return
    const next = [...selected, normalized]
    if (next.length > USER_TAG_MAX_PER_OBJECT - 1) {
      showError(new ApiError('user_tag_limit_per_object', t('errors.user_tag_limit_per_object')))
      return
    }
    onChange(next)
  }

  function setChecked(name: string, checked: boolean) {
    if (disabled) return
    if (checked) {
      tryAdd(name)
      return
    }
    onChange(selected.filter((item) => item.toLowerCase() !== name.toLowerCase()))
  }

  const triggerLabel =
    selected.length > 0
      ? t('library.ingestExtraTagsCount', { count: selected.length })
      : t('library.ingestExtraTags')

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger
        render={
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={disabled}
            className={cn(
              'library-ingest-tags-trigger shrink-0 gap-1.5 font-normal',
              selected.length > 0 && 'border-primary/40',
            )}
          />
        }
      >
        <TagsIcon className="size-3.5 shrink-0 opacity-70" aria-hidden />
        <span className="max-w-[8rem] truncate sm:max-w-[10rem]">{triggerLabel}</span>
      </PopoverTrigger>
      <PopoverContent className="library-ingest-tags-menu w-[min(18rem,calc(100vw-2rem))] gap-2 p-3" align="start">
        <PopoverHeader className="gap-1">
          <PopoverTitle>{t('library.ingestExtraTags')}</PopoverTitle>
          <PopoverDescription className="text-xs leading-snug">
            {t('library.ingestExtraTagsHint')}
          </PopoverDescription>
        </PopoverHeader>
        {listItems.length > 0 ? (
          <ul className="library-ingest-tags-list max-h-48 overflow-y-auto rounded-md border border-border p-1">
            {listItems.map((row) => {
              const checked = keys.has(row.name.toLowerCase())
              const inputId = `ingest-tag-${row.key}`
              return (
                <li key={row.key}>
                  <div className="flex items-center gap-2 rounded-sm px-2 py-1.5 hover:bg-muted/60">
                    <Checkbox
                      id={inputId}
                      checked={checked}
                      disabled={disabled}
                      onCheckedChange={(value) => setChecked(row.name, Boolean(value))}
                    />
                    <Label htmlFor={inputId} className="min-w-0 flex-1 truncate font-normal">
                      {row.name}
                    </Label>
                  </div>
                </li>
              )
            })}
          </ul>
        ) : (
          <p className="muted text-xs">{t('library.noTagsYet')}</p>
        )}
        <div className="flex gap-2">
          <Input
            className="h-8 shadow-none"
            value={draft}
            disabled={disabled}
            placeholder={t('library.addTagPlaceholder')}
            aria-label={t('library.addTagPlaceholder')}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault()
                if (!draft.trim()) return
                tryAdd(draft)
                setDraft('')
              }
            }}
          />
          <Button
            type="button"
            size="sm"
            variant="outline"
            className="shrink-0"
            disabled={disabled || !draft.trim()}
            onClick={() => {
              tryAdd(draft)
              setDraft('')
            }}
          >
            {t('library.addTag')}
          </Button>
        </div>
      </PopoverContent>
    </Popover>
  )
}
