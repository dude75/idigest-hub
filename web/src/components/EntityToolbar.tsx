import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'
import { appMutedText } from '@/components/app/appTypography'

export function EntityToolbar({ children }: { children: ReactNode }) {
  return <div className="row entity-toolbar">{children}</div>
}

export function EntityHint({ children }: { children: ReactNode }) {
  return <p className={cn(appMutedText, 'entity-hint')}>{children}</p>
}
