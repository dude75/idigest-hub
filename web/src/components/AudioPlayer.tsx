import { forwardRef, useCallback, useEffect, useImperativeHandle, useRef, useState } from 'react'
import { Pause, Play, Volume2, VolumeX } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { cn } from '@/lib/utils'

export type AudioPlayerHandle = {
  seekTo: (seconds: number) => void
}

type Props = {
  audioId: string
  className?: string
}

const RATES = [1, 1.25, 1.5, 2] as const

function fmt(sec: number): string {
  if (!Number.isFinite(sec)) return '0:00'
  const s = Math.max(0, Math.floor(sec))
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
}

export const AudioPlayer = forwardRef<AudioPlayerHandle, Props>(function AudioPlayer(
  { audioId, className },
  ref,
) {
  const { t } = useTranslation()
  const audioRef = useRef<HTMLAudioElement>(null)
  const draggingRef = useRef(false)

  const [playing, setPlaying] = useState(false)
  const [muted, setMuted] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)
  const [rateIndex, setRateIndex] = useState(0)
  const [scrubFill, setScrubFill] = useState('0%')

  const src = `/api/v1/audios/${audioId}/file`
  const rate = RATES[rateIndex]

  const updateFill = useCallback((time: number, dur: number) => {
    const pct = dur > 0 ? Math.min(100, (time / dur) * 100) : 0
    setScrubFill(`${pct}%`)
  }, [])

  useImperativeHandle(ref, () => ({
    seekTo(seconds: number) {
      const el = audioRef.current
      if (!el) return
      el.currentTime = Math.max(0, seconds)
      setCurrentTime(el.currentTime)
      updateFill(el.currentTime, el.duration)
      void el.play().catch(() => {})
    },
  }))

  useEffect(() => {
    const el = audioRef.current
    if (!el) return
    el.playbackRate = rate
  }, [rate, audioId])

  useEffect(() => {
    const el = audioRef.current
    if (!el) return

    const onPlay = () => setPlaying(true)
    const onPause = () => setPlaying(false)
    const onDuration = () => {
      setDuration(el.duration)
      updateFill(el.currentTime, el.duration)
    }
    const onTime = () => {
      if (draggingRef.current) return
      setCurrentTime(el.currentTime)
      updateFill(el.currentTime, el.duration)
    }

    el.addEventListener('play', onPlay)
    el.addEventListener('pause', onPause)
    el.addEventListener('loadedmetadata', onDuration)
    el.addEventListener('durationchange', onDuration)
    el.addEventListener('timeupdate', onTime)

    setPlaying(!el.paused)
    setMuted(el.muted)
    setCurrentTime(el.currentTime)
    setDuration(Number.isFinite(el.duration) ? el.duration : 0)
    updateFill(el.currentTime, el.duration)

    return () => {
      el.removeEventListener('play', onPlay)
      el.removeEventListener('pause', onPause)
      el.removeEventListener('loadedmetadata', onDuration)
      el.removeEventListener('durationchange', onDuration)
      el.removeEventListener('timeupdate', onTime)
    }
  }, [audioId, updateFill])

  const togglePlay = () => {
    const el = audioRef.current
    if (!el) return
    if (el.paused) void el.play().catch(() => {})
    else el.pause()
  }

  const toggleMute = () => {
    const el = audioRef.current
    if (!el) return
    el.muted = !el.muted
    setMuted(el.muted)
  }

  const onScrubInput = (value: number) => {
    const el = audioRef.current
    if (!el) return
    el.currentTime = value
    setCurrentTime(value)
    updateFill(value, el.duration)
  }

  const clock =
    `${fmt(currentTime)} / ${Number.isFinite(duration) && duration > 0 ? fmt(duration) : '0:00'}`

  return (
    <div className={cn('audio-player', className)}>
      <button
        type="button"
        className="audio-player__play"
        aria-label={playing ? t('audio.playerPause') : t('audio.playerPlay')}
        onClick={togglePlay}
      >
        {playing ? <Pause className="size-[18px]" fill="currentColor" aria-hidden /> : <Play className="size-[18px]" fill="currentColor" aria-hidden />}
      </button>
      <span className="audio-player__time">{clock}</span>
      <input
        className="audio-player__scrub"
        type="range"
        min={0}
        max={Number.isFinite(duration) && duration > 0 ? duration : 0}
        step={0.01}
        value={currentTime}
        style={{ ['--scrub-fill' as string]: scrubFill }}
        aria-label={t('audio.playerSeek')}
        onPointerDown={() => {
          draggingRef.current = true
        }}
        onPointerUp={() => {
          draggingRef.current = false
        }}
        onChange={(e) => onScrubInput(Number(e.target.value))}
      />
      <button
        type="button"
        className="audio-player__mute"
        aria-label={muted ? t('audio.playerUnmute') : t('audio.playerMute')}
        aria-pressed={muted}
        onClick={toggleMute}
      >
        {muted ? <VolumeX className="size-[18px]" aria-hidden /> : <Volume2 className="size-[18px]" aria-hidden />}
      </button>
      <button
        type="button"
        className="audio-player__rate"
        aria-label={t('audio.playerSpeed')}
        onClick={() => setRateIndex((i) => (i + 1) % RATES.length)}
      >
        {rate}×
      </button>
      <audio ref={audioRef} className="sr-only" preload="metadata" src={src} />
    </div>
  )
})
