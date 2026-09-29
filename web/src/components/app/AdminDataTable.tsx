import type { ReactNode } from 'react'
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
