export const LIBRARY_TABS = ['audio', 'transcripts', 'summaries'] as const
export type LibraryTab = (typeof LIBRARY_TABS)[number]

export function libraryPath(tab: LibraryTab = 'audio'): string {
  return `/app/library/${tab}`
}

export const LIBRARY_DEFAULT = libraryPath('audio')

export function isLibraryTab(value: string | undefined): value is LibraryTab {
  return LIBRARY_TABS.includes(value as LibraryTab)
}
