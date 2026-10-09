import { cn } from '@/lib/utils'

/** Shared chrome for link / file / mic hit areas in ingest studio cards. */
export function ingestStudioHitSurfaceClassName(className?: string) {
  return cn('ingest-studio-hit-surface ingest-studio-link-zone', className)
}
