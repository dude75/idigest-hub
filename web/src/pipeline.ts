import type { Task } from './types'

export type IngestPipeline = {
  transcribe: boolean
  skillIds: string[]
}

const STORAGE_KEY = 'idigest-ingest-pipeline'
const RUN_KEY = 'idigest-ingest-pipeline-run'

export const DEFAULT_PIPELINE: IngestPipeline = {
  transcribe: false,
  skillIds: [],
}

function readSkillIds(raw: Partial<IngestPipeline & { skill_ids?: string[] }>): string[] {
  if (Array.isArray(raw.skillIds)) return raw.skillIds
  if (Array.isArray(raw.skill_ids)) return raw.skill_ids
  return []
}

export function normalizePipeline(next: IngestPipeline): IngestPipeline {
  if (!next.transcribe) return { transcribe: false, skillIds: [] }
  const skillIds = readSkillIds(next).filter((id): id is string => typeof id === 'string' && id.length > 0)
  return { transcribe: true, skillIds }
}

export function loadPipeline(): IngestPipeline {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return { ...DEFAULT_PIPELINE }
    const parsed = JSON.parse(raw) as Partial<IngestPipeline & { skill_ids?: string[] }>
    return normalizePipeline({
      transcribe: parsed.transcribe === true,
      skillIds: readSkillIds(parsed),
    })
  } catch {
    return { ...DEFAULT_PIPELINE }
  }
}

export function savePipeline(pipeline: IngestPipeline): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(normalizePipeline(pipeline)))
}

export function beginPipelineRun(pipeline: IngestPipeline = loadPipeline()): IngestPipeline {
  const configured = normalizePipeline(pipeline)
  const run: IngestPipeline = {
    transcribe: configured.transcribe,
    skillIds: [...configured.skillIds],
  }
  sessionStorage.setItem(RUN_KEY, JSON.stringify(run))
  return run
}

export function loadPipelineRun(): IngestPipeline | null {
  try {
    const raw = sessionStorage.getItem(RUN_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as Partial<IngestPipeline & { skill_ids?: string[] }>
    return {
      transcribe: parsed.transcribe === true,
      skillIds: readSkillIds(parsed).filter((id): id is string => typeof id === 'string' && id.length > 0),
    }
  } catch {
    return null
  }
}

export function endPipelineRun(): void {
  sessionStorage.removeItem(RUN_KEY)
}

export function activePipeline(): IngestPipeline {
  return loadPipelineRun() ?? loadPipeline()
}

export function pipelineShouldTranscribe(pipeline: IngestPipeline = loadPipeline()): boolean {
  return pipeline.transcribe
}

export function pipelineShouldSummarize(pipeline: IngestPipeline): boolean {
  return pipeline.skillIds.length > 0
}

export type PipelineNavState = { pipeline: IngestPipeline; task?: Task }

export function pipelineNavState(pipeline: IngestPipeline, task?: Task): PipelineNavState {
  const run = loadPipelineRun() ?? normalizePipeline(pipeline)
  return { pipeline: run, task }
}

/** Seed TaskPage state from router navigation (avoids blank UI before first poll). */
export function initialTaskFromNav(
  navState: PipelineNavState | null | undefined,
  taskId: string | undefined,
): Task | null {
  const initial = navState?.task
  if (initial && taskId && initial.task_id === taskId) return initial
  return null
}

export function transcribeRequest(audioId: string, pipeline: IngestPipeline = activePipeline()): {
  audio_id: string
  skill_ids?: string[]
} {
  const body: { audio_id: string; skill_ids?: string[] } = { audio_id: audioId }
  if (pipeline.skillIds.length > 0) {
    body.skill_ids = [...pipeline.skillIds]
  }
  return body
}
