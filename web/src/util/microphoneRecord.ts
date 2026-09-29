/** Align with hub MIN_CAPTURE / small artifact rejection. */
export const MIN_RECORDING_UPLOAD_BYTES = 512

export type RecordingUploadExt = '.webm' | '.m4a'

export function waitForMediaRecorderStop(recorder: MediaRecorder): Promise<void> {
  if (recorder.state === 'inactive') return Promise.resolve()
  return new Promise((resolve, reject) => {
    recorder.addEventListener('stop', () => resolve(), { once: true })
    recorder.addEventListener('error', () => reject(new Error('record_failed')), { once: true })
    try {
      recorder.stop()
    } catch (e) {
      reject(e)
    }
  })
}

export function detachMediaRecorder(recorder: MediaRecorder | null): void {
  if (!recorder) return
  recorder.ondataavailable = null
  recorder.onerror = null
}

export function recordingExtensionForMime(mime: string): RecordingUploadExt {
  const base = mime.split(';', 1)[0].trim().toLowerCase()
  if (base === 'audio/mp4' || base === 'audio/x-m4a') return '.m4a'
  return '.webm'
}

export function recordingFilenameForMime(mime: string): string {
  const ext = recordingExtensionForMime(mime)
  const d = new Date()
  const pad = (n: number) => String(n).padStart(2, '0')
  const stamp = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}-${pad(d.getHours())}${pad(d.getMinutes())}${pad(d.getSeconds())}`
  return `recording-${stamp}${ext}`
}

export function mediaBlobToRecordingFile(blob: Blob, mime: string): File {
  const normalized = mime.split(';', 1)[0].trim() || blob.type.split(';', 1)[0].trim()
  const type = normalized || 'audio/webm'
  return new File([blob], recordingFilenameForMime(type), { type })
}

export function pickMediaRecorderMimeType(): string | undefined {
  if (typeof MediaRecorder === 'undefined') return undefined
  for (const candidate of ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4']) {
    if (MediaRecorder.isTypeSupported(candidate)) return candidate
  }
  return undefined
}

export async function listAudioInputDevices(): Promise<MediaDeviceInfo[]> {
  const devices = await navigator.mediaDevices.enumerateDevices()
  return devices.filter((d) => d.kind === 'audioinput')
}

export function mediaStreamStopTracks(stream: MediaStream | null): void {
  stream?.getTracks().forEach((t) => t.stop())
}
