import type { ReactNode } from 'react'

export function EntityToolbar({ children }: { children: ReactNode }) {
  return <div className="row entity-toolbar">{children}</div>
}

export function EntityHint({ children }: { children: ReactNode }) {
  return <p className="muted entity-hint">{children}</p>
}
