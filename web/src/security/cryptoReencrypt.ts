export type DekListReencrypt = {
  items: { status: string }[]
  reencrypt_available?: boolean
  running_job_id?: string | null
}

export function isCryptoReencryptJobRunning(
  deks: DekListReencrypt | null,
  latestJobStatus?: string | null,
): boolean {
  if (deks?.running_job_id) return true
  return latestJobStatus === 'queued' || latestJobStatus === 'running'
}

/** More than one DEK and server allows starting a re-encrypt job. */
export function canStartCryptoReencrypt(deks: DekListReencrypt | null): boolean {
  if (!deks || deks.items.length <= 1) return false
  return deks.reencrypt_available ?? deks.items.some((d) => d.status === 'retiring')
}
