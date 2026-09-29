import type { ReactNode } from 'react'
import {
  Tabs as ShadcnTabs,
  TabsList,
  TabsTrigger,
} from '@/components/ui/tabs'
import { cn } from '@/lib/utils'

export { TabsList, TabsTrigger } from '@/components/ui/tabs'

export type TabButtonItem = { id: string; label: string; active: boolean; onClick: () => void }

type Props = {
  items: TabButtonItem[]
  ariaLabel?: string
  className?: string
  variant?: 'default' | 'line'
}

/** Controlled tabs with custom triggers (e.g. legal document type picker). */
export function AppTabs({
  value,
  onValueChange,
  ariaLabel,
  className,
  listClassName,
  children,
}: {
  value: string
  onValueChange: (value: string) => void
  ariaLabel?: string
  className?: string
  listClassName?: string
  children: ReactNode
}) {
  return (
    <ShadcnTabs
      value={value}
      onValueChange={onValueChange}
      className={cn('mb-4 w-full gap-2', className)}
    >
      <TabsList aria-label={ariaLabel} className={listClassName}>
        {children}
      </TabsList>
    </ShadcnTabs>
  )
}

/** App tab bar — thin wrapper over `@/components/ui/tabs` (same as instance/security). */
export function Tabs({ items, ariaLabel, className, variant = 'default' }: Props) {
  if (items.length === 0) return null

  const activeId = items.find((item) => item.active)?.id ?? items[0]!.id

  return (
    <ShadcnTabs
      value={activeId}
      onValueChange={(value) => {
        items.find((item) => item.id === value)?.onClick()
      }}
      className={cn(variant === 'line' ? 'w-full gap-0' : 'mb-4 w-full gap-2', className)}
    >
      <TabsList variant={variant} aria-label={ariaLabel}>
        {items.map((item) => (
          <TabsTrigger key={item.id} value={item.id}>
            {item.label}
          </TabsTrigger>
        ))}
      </TabsList>
    </ShadcnTabs>
  )
}
