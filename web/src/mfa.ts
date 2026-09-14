const CHALLENGE_KEY = 'mfa_challenge_id'

export function readMfaChallengeId(): string | null {
  try {
    return sessionStorage.getItem(CHALLENGE_KEY)
  } catch {
    return null
  }
}

export function clearMfaChallengeId(): void {
  try {
    sessionStorage.removeItem(CHALLENGE_KEY)
  } catch {
    /* ignore */
  }
}

export function storeMfaChallengeId(id: string): void {
  try {
    sessionStorage.setItem(CHALLENGE_KEY, id)
  } catch {
    /* ignore */
  }
}
