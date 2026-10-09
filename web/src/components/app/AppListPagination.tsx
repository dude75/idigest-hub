import { useTranslation } from 'react-i18next'
import { Field, FieldLabel } from '@/components/ui/field'
import {
  Pagination,
  PaginationContent,
  PaginationItem,
  PaginationNext,
  PaginationPrevious,
} from '@/components/ui/pagination'
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { cn } from '@/lib/utils'
import { AdminTablePager } from './AdminDataTable'
import {
  LIST_PAGE_SIZE_OPTIONS,
  type ListPageSize,
} from './selectOptions'

type AppListPaginationProps = {
  htmlFor: string
  pageSize: ListPageSize
  setPageSize: (size: ListPageSize) => void
  page: number
  setPage: (page: number) => void
  total: number
  className?: string
}

/** Строк на странице + «1–10 из N» + prev/next (shadcn icons-only). */
export function AppListPagination({
  htmlFor,
  pageSize,
  setPageSize,
  page,
  setPage,
  total,
  className,
}: AppListPaginationProps) {
  const { t } = useTranslation()
  const pageCount = Math.max(1, Math.ceil(total / pageSize))
  const from = total === 0 ? 0 : page * pageSize + 1
  const to = Math.min(total, (page + 1) * pageSize)

  return (
    <AdminTablePager className={cn('justify-end', className)}>
      <div className="flex min-w-0 flex-wrap items-center gap-4">
        <Field orientation="horizontal" className="w-fit shrink-0 gap-3">
          <FieldLabel htmlFor={htmlFor} className="text-sm font-normal">
            {t('task.rowsPerPage')}
          </FieldLabel>
          <Select
            value={String(pageSize)}
            onValueChange={(next) => {
              if (next == null) return
              setPageSize(Number(next) as ListPageSize)
              setPage(0)
            }}
            items={LIST_PAGE_SIZE_OPTIONS}
          >
            <SelectTrigger className="w-20" id={htmlFor}>
              <SelectValue />
            </SelectTrigger>
            <SelectContent align="start">
              <SelectGroup>
                {LIST_PAGE_SIZE_OPTIONS.map((opt) => (
                  <SelectItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectGroup>
            </SelectContent>
          </Select>
        </Field>
        <Pagination className="mx-0 w-auto shrink-0">
          <PaginationContent>
            <PaginationItem>
              <PaginationPrevious
                text={t('common.prev')}
                disabled={page === 0}
                onClick={() => setPage(page - 1)}
              />
            </PaginationItem>
            <PaginationItem>
              <span className="px-2 text-sm text-muted-foreground tabular-nums">
                {t('task.pageRange', { from, to, total })}
              </span>
            </PaginationItem>
            <PaginationItem>
              <PaginationNext
                text={t('common.next')}
                disabled={page >= pageCount - 1}
                onClick={() => setPage(page + 1)}
              />
            </PaginationItem>
          </PaginationContent>
        </Pagination>
      </div>
    </AdminTablePager>
  )
}
