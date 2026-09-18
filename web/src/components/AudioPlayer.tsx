import { forwardRef, useImperativeHandle, useRef } from 'react'

export type AudioPlayerHandle = {
  seekTo: (seconds: number) => void
}

type Props = {
  audioId: string
  className?: string
}

export const AudioPlayer = forwardRef<AudioPlayerHandle, Props>(function AudioPlayer(
  { audioId, className },
  ref,
) {
  const audioRef = useRef<HTMLAudioElement>(null)

  useImperativeHandle(ref, () => ({
    seekTo(seconds: number) {
      const el = audioRef.current
      if (!el) return
      el.currentTime = Math.max(0, seconds)
      void el.play().catch(() => {})
    },
  }))

  return (
    <audio
      ref={audioRef}
      className={className ?? 'audio-player'}
      controls
      src={`/api/v1/audios/${audioId}/file`}
    />
  )
})
