/** Shallow JSON compare for form snapshots (settings objects, form state). */
export function jsonDirty(current: unknown, saved: unknown): boolean {
  return JSON.stringify(current) !== JSON.stringify(saved)
}
