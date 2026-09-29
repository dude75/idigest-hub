import { useEffect, useRef, useState } from 'react'
import { cn } from '@/lib/utils'

const POINTS = 64
const WIDTH = 400
const HEIGHT = 120
const WAVE_CENTER_Y = HEIGHT * 0.54
/** Slightly above the original Siri-style default (~0.34). */
const WAVE_AMP = HEIGHT * 0.4

const LEVEL_HISTORY = 28

const WAVE_LAYERS = [
  {
    phaseSpeed: 0.024,
    freq1: 2.15,
    freq2: 4.8,
    ampScale: 0.42,
    baseOpacity: 0.22,
    attack: 0.1,
    release: 0.028,
    levelLag: 10,
  },
  {
    phaseSpeed: 0.034,
    freq1: 2.55,
    freq2: 5.4,
    ampScale: 0.68,
    baseOpacity: 0.42,
    attack: 0.16,
    release: 0.045,
    levelLag: 5,
  },
  {
    phaseSpeed: 0.044,
    freq1: 2.95,
    freq2: 6.2,
    ampScale: 1,
    baseOpacity: 0.88,
    attack: 0.22,
    release: 0.07,
    levelLag: 0,
  },
] as const

type LayerRender = { d: string; opacity: number }

type Mode = 'starting' | 'recording' | 'paused' | 'idle'

type Props = {
  stream: MediaStream | null
  mode: Mode
  className?: string
}

function clamp(n: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, n))
}

function smoothWavePath(values: number[], width: number): string {
  if (values.length < 2) return ''
  const pts = values.map((v, i) => ({
    x: (i / (values.length - 1)) * width,
    y: WAVE_CENTER_Y - v * WAVE_AMP,
  }))

  let d = `M ${pts[0].x.toFixed(2)} ${pts[0].y.toFixed(2)}`
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = pts[Math.max(0, i - 1)]
    const p1 = pts[i]
    const p2 = pts[i + 1]
    const p3 = pts[Math.min(pts.length - 1, i + 2)]
    const cp1x = p1.x + (p2.x - p0.x) / 6
    const cp1y = p1.y + (p2.y - p0.y) / 6
    const cp2x = p2.x - (p3.x - p1.x) / 6
    const cp2y = p2.y - (p3.y - p1.y) / 6
    d += ` C ${cp1x.toFixed(2)} ${cp1y.toFixed(2)} ${cp2x.toFixed(2)} ${cp2y.toFixed(2)} ${p2.x.toFixed(2)} ${p2.y.toFixed(2)}`
  }
  return d
}

function siriWaveAt(t: number, phase: number, layer: (typeof WAVE_LAYERS)[number]): number {
  const edge = Math.sin(t * Math.PI)
  const body =
    Math.sin(t * Math.PI * layer.freq1 + phase) * 0.64 +
    Math.sin(t * Math.PI * layer.freq2 - phase * 0.78) * 0.26
  return body * edge
}

function buildLayerShape(
  phase: number,
  amplitude: number,
  layer: (typeof WAVE_LAYERS)[number],
): number[] {
  const amp = clamp(amplitude, 0, 1)
  const floor = 0.12 * amp
  return Array.from({ length: POINTS }, (_, i) => {
    const t = i / (POINTS - 1)
    const wave = siriWaveAt(t, phase, layer)
    return wave * (floor + amp * layer.ampScale)
  })
}

function readMicLevel(timeData: Uint8Array): number {
  let sumSq = 0
  for (let i = 0; i < timeData.length; i++) {
    const v = (timeData[i] - 128) / 128
    sumSq += v * v
  }
  const rms = Math.sqrt(sumSq / timeData.length)
  return clamp(Math.pow(rms * 3.2, 0.72), 0, 1)
}

export function MicrophoneLevelVisualizer({ stream, mode, className }: Props) {
  const [layers, setLayers] = useState<LayerRender[]>(() =>
    WAVE_LAYERS.map((layer) => ({ d: '', opacity: layer.baseOpacity * 0.35 })),
  )

  const phaseRef = useRef<number[]>(WAVE_LAYERS.map(() => 0))
  const layerAmpRef = useRef<number[]>(WAVE_LAYERS.map(() => 0.08))
  const micLevelRef = useRef(0.08)
  const levelHistoryRef = useRef<number[]>([])

  useEffect(() => {
    let raf = 0
    let analyser: AnalyserNode | null = null
    let timeData: Uint8Array | null = null
    let audioCtx: AudioContext | null = null

    const micLive = (mode === 'recording' || mode === 'paused') && stream

    if (micLive) {
      audioCtx = new AudioContext()
      void audioCtx.resume()
      const source = audioCtx.createMediaStreamSource(stream)
      analyser = audioCtx.createAnalyser()
      analyser.fftSize = 1024
      analyser.smoothingTimeConstant = 0.88
      source.connect(analyser)
      timeData = new Uint8Array(analyser.fftSize)
    }

    const pushLevel = (level: number) => {
      const history = levelHistoryRef.current
      history.unshift(level)
      if (history.length > LEVEL_HISTORY) history.pop()
    }

    const levelAtLag = (lag: number): number => {
      const history = levelHistoryRef.current
      const idx = clamp(lag, 0, history.length - 1)
      return history[idx] ?? micLevelRef.current
    }

    const tick = () => {
      const ambient = mode === 'starting' || mode === 'idle'
      const paused = mode === 'paused'
      const micAnalyser = micLive ? analyser : null
      const micTimeData = micLive ? timeData : null
      const micVisualActive = micAnalyser != null && micTimeData != null

      let driveLevel = micLevelRef.current

      if (audioCtx?.state === 'suspended') {
        void audioCtx.resume()
      }

      if (micVisualActive && mode === 'recording') {
        micAnalyser.getByteTimeDomainData(micTimeData as Uint8Array<ArrayBuffer>)
        const raw = readMicLevel(micTimeData)
        micLevelRef.current += (raw - micLevelRef.current) * 0.18
        pushLevel(micLevelRef.current)
        driveLevel = micLevelRef.current
      } else if (paused) {
        pushLevel(micLevelRef.current * 0.92)
        micLevelRef.current *= 0.985
        driveLevel = micLevelRef.current
      } else if (ambient) {
        const pulse = 0.22 + Math.sin(phaseRef.current[0] * 0.9) * 0.08
        micLevelRef.current += (pulse - micLevelRef.current) * 0.04
        pushLevel(micLevelRef.current)
        driveLevel = micLevelRef.current
      }

      const nextLayers: LayerRender[] = WAVE_LAYERS.map((layer, index) => {
        const phaseStep = ambient ? layer.phaseSpeed * (mode === 'starting' ? 1.15 : 0.85) : layer.phaseSpeed
        phaseRef.current[index] += phaseStep

        const target = micVisualActive || paused ? levelAtLag(layer.levelLag) : driveLevel
        const current = layerAmpRef.current[index]
        const rate = target >= current ? layer.attack : layer.release
        layerAmpRef.current[index] += (target - current) * rate

        const amp = layerAmpRef.current[index]
        const shape = buildLayerShape(phaseRef.current[index], amp, layer)
        const opacity = layer.baseOpacity * clamp(0.18 + amp * 1.05, 0.12, 1)

        return {
          d: smoothWavePath(shape, WIDTH),
          opacity,
        }
      })

      setLayers(nextLayers)
      raf = requestAnimationFrame(tick)
    }

    raf = requestAnimationFrame(tick)

    return () => {
      cancelAnimationFrame(raf)
      if (audioCtx) {
        void audioCtx.close()
      }
    }
  }, [mode, stream])

  const recording = mode === 'recording'
  const paused = mode === 'paused'
  const strokeClass = recording ? 'stroke-red-500' : paused ? 'stroke-amber-500' : 'stroke-primary/55'

  return (
    <div className={cn('relative w-full', className)} aria-hidden="true">
      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        className="h-[5rem] w-full overflow-visible"
        preserveAspectRatio="none"
      >
        {WAVE_LAYERS.map((layer, index) => (
          <path
            key={layer.levelLag}
            d={layers[index]?.d ?? ''}
            fill="none"
            strokeWidth={1.1}
            strokeLinecap="round"
            strokeLinejoin="round"
            vectorEffect="non-scaling-stroke"
            strokeOpacity={layers[index]?.opacity ?? layer.baseOpacity}
            className={cn(
              strokeClass,
              index === WAVE_LAYERS.length - 1 && recording && 'drop-shadow-[0_0_5px_rgba(239,68,68,0.32)]',
            )}
          />
        ))}
      </svg>
    </div>
  )
}
