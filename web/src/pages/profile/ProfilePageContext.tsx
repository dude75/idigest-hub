import { createContext, useContext, type ReactNode } from 'react'
import type { ProfilePageModel } from './useProfilePageModel'
import { useProfilePageModel } from './useProfilePageModel'

const ProfilePageContext = createContext<ProfilePageModel | null>(null)

export function ProfilePageProvider({ children }: { children: ReactNode }) {
  const model = useProfilePageModel()
  return <ProfilePageContext.Provider value={model}>{children}</ProfilePageContext.Provider>
}

export function useProfilePage() {
  const ctx = useContext(ProfilePageContext)
  if (!ctx) throw new Error('useProfilePage must be used within ProfilePageProvider')
  return ctx
}
