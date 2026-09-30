import type { ReactNode } from 'react'
import { AppHoverHint } from '@/components/app/AppHoverHint'
import {
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { cn } from '@/lib/utils'

/** shadcn-style admin tables (instance tariffs, workers, …). */
export function AdminDataTable({
  caption,
  className,
  children,
}: {
  caption?: ReactNode
  className?: string
  children: ReactNode
}) {
  return (
    <Table className={className}>
      {caption ? <TableCaption>{caption}</TableCaption> : null}
      {children}
    </Table>
  )
}

export {
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
}

export const adminTableHeadNum = 'text-right'
export const adminTableHeadActions = 'w-[1%] text-right'
export const adminTableCellPrimary = 'font-medium whitespace-normal'
export const adminTableCellMuted = 'text-muted-foreground whitespace-normal'
export const adminTableCellNum = 'text-right tabular-nums'
export const adminTableCellActions = 'w-[1%] text-right whitespace-nowrap'
export const adminTableCellBadges = cn('whitespace-normal min-w-[9rem] max-w-[16rem]')

export const adminTruncateHintClass =
  'cursor-help underline decoration-dotted decoration-muted-foreground/60 underline-offset-2'

/** Truncated table/list text with HoverCard detail (replaces native `title`). */
export function AdminTruncateHint({
  hint,
  className,
  contentClassName,
  children,
}: {
  hint?: ReactNode
  className?: string
  contentClassName?: string
  children: ReactNode
}) {
  const el = <span className={cn('block truncate', adminTruncateHintClass, className)}>{children}</span>
  if (hint == null || hint === '') {
    return el
  }
  return (
    <AppHoverHint content={hint} contentClassName={contentClassName}>
      {el}
    </AppHoverHint>
  )
}

export function AdminTableCellHint({
  hint,
  className,
  hintClassName,
  contentClassName,
  children,
}: {
  hint?: ReactNode
  className?: string
  hintClassName?: string
  contentClassName?: string
  children: ReactNode
}) {
  return (
    <TableCell className={className}>
      <AdminTruncateHint hint={hint} className={hintClassName} contentClassName={contentClassName}>
        {children}
      </AdminTruncateHint>
    </TableCell>
  )
}

export function AdminTableHeadHint({
  hint,
  className,
  children,
}: {
  hint?: string
  className?: string
  children: ReactNode
}) {
  if (!hint) {
    return <TableHead className={className}>{children}</TableHead>
  }
  return (
    <TableHead className={className}>
      <AppHoverHint content={hint}>
        <span className="cursor-help underline decoration-dotted decoration-muted-foreground/60 underline-offset-2">
          {children}
        </span>
      </AppHoverHint>
    </TableHead>
  )
}

/** Pager row under flush tables (audit, tasks, …). */
export function AdminTablePager({
  children,
  className,
}: {
  children: ReactNode
  className?: string
}) {
  return (
    <div className={cn('flex flex-wrap items-center justify-end gap-2 border-t px-4 py-3', className)}>
      {children}
    </div>
  )
}
