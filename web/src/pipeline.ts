import type { Me, Task } from './types'
import { requestTone } from './toneAnalytics'

export type IngestPipeline = {
  transcribe: boolean
  skillIds: string[]
}

const STORAGE_KEY = 'idigest-ingest-pipeline'
const SUMMARIZE_SKILLS_KEY = 'idigest-summarize-skills'
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

export function loadSummarizeSkillIds(): string[] {
  try {
    const raw = localStorage.getItem(SUMMARIZE_SKILLS_KEY)
    if (raw) {
      const parsed = JSON.parse(raw) as unknown
      if (Array.isArray(parsed)) {
        return parsed.filter((id): id is string => typeof id === 'string' && id.length > 0)
      }
    }
  } catch {
    /* ignore */
  }
  return loadPipeline().skillIds
}

export function saveSummarizeSkillIds(skillIds: string[]): void {
  localStorage.setItem(
    SUMMARIZE_SKILLS_KEY,
    JSON.stringify(skillIds.filter((id) => id.length > 0)),
  )
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

/** Summarize-only run from transcript page (not persisted in library pipeline settings). */
export function beginSummarizePipelineRun(skillIds: string[]): IngestPipeline {
  const run: IngestPipeline = {
    transcribe: false,
    skillIds: skillIds.filter((id) => id.length > 0),
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

function readTaskSkillIds(task: Task): string[] {
  if (!Array.isArray(task.skill_ids)) return []
  return task.skill_ids.filter((id): id is string => typeof id === 'string' && id.length > 0)
}

/** Pipeline steps for task poll UI — from session run or the task record, not library defaults. */
export function pipelineForTask(task: Task | null): IngestPipeline {
  if (!task) return { ...DEFAULT_PIPELINE }

  if (task.type === 'summarize') {
    const skillIds = readTaskSkillIds(task)
    return { transcribe: false, skillIds }
  }

  if (task.type === 'transcribe') {
    return { transcribe: true, skillIds: readTaskSkillIds(task) }
  }

  if (task.type === 'import' || task.type === 'capture') {
    if (task.meta?.pipeline_transcribe !== true) {
      return { transcribe: false, skillIds: [] }
    }
    return { transcribe: true, skillIds: readTaskSkillIds(task) }
  }

  return { ...DEFAULT_PIPELINE }
}

export function pipelineForProgress(task: Task | null): IngestPipeline {
  return loadPipelineRun() ?? pipelineForTask(task)
}

export function pipelineShouldTranscribe(pipeline: IngestPipeline = loadPipeline()): boolean {
  return pipeline.transcribe
}

export function pipelineShouldSummarize(pipeline: IngestPipeline): boolean {
  return pipeline.skillIds.length > 0
}

export type PipelineNavState = { pipeline: IngestPipeline; task?: Task }

export function pipelineNavState(pipeline: IngestPipeline, task?: Task): PipelineNavState {
  const run =
    loadPipelineRun() ??
    (pipeline.skillIds.length > 0 && !pipeline.transcribe ? pipeline : normalizePipeline(pipeline))
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

export function transcribeRequest(
  audioId: string,
  pipeline: IngestPipeline = activePipeline(),
  me?: Me | null,
): {
  audio_id: string
  skill_ids?: string[]
  tone: boolean
} {
  const body: { audio_id: string; skill_ids?: string[]; tone: boolean } = {
    audio_id: audioId,
    tone: requestTone(me),
  }
  if (pipeline.skillIds.length > 0) {
    body.skill_ids = [...pipeline.skillIds]
  }
  return body
}

export function captureRequest(
  meetingUrl: string,
  pin: string,
  pipeline: IngestPipeline = activePipeline(),
  me?: Me | null,
): {
  meeting_url: string
  pin: string
  transcribe?: boolean
  skill_ids?: string[]
  tone?: boolean
} {
  const body: {
    meeting_url: string
    pin: string
    transcribe?: boolean
    skill_ids?: string[]
    tone?: boolean
  } = { meeting_url: meetingUrl, pin }
  if (pipelineShouldTranscribe(pipeline)) {
    body.transcribe = true
    body.tone = requestTone(me)
    if (pipeline.skillIds.length > 0) {
      body.skill_ids = [...pipeline.skillIds]
    }
  }
  return body
}

export function importRequest(url: string, pipeline: IngestPipeline = activePipeline(), me?: Me | null): {
  url: string
  transcribe?: boolean
  skill_ids?: string[]
  tone?: boolean
} {
  const body: { url: string; transcribe?: boolean; skill_ids?: string[]; tone?: boolean } = { url }
  if (pipelineShouldTranscribe(pipeline)) {
    body.transcribe = true
    body.tone = requestTone(me)
    if (pipeline.skillIds.length > 0) {
      body.skill_ids = [...pipeline.skillIds]
    }
  }
  return body
}
