import type { QCConfig } from '../types'
import { DEFAULT_CONFIG } from '../types'

export const PROFILE_STORAGE_KEY = 'ds_profiles'

export interface SavedProfile {
  name: string
  config: QCConfig
  savedAt: string
}

// Strips _info/_comment fields added by the template so they don't break the config shape
function stripMeta(obj: unknown): unknown {
  if (Array.isArray(obj)) return obj.map(stripMeta)
  if (obj && typeof obj === 'object') {
    return Object.fromEntries(
      Object.entries(obj as Record<string, unknown>)
        .filter(([k]) => !k.startsWith('_'))
        .map(([k, v]) => [k, stripMeta(v)])
    )
  }
  return obj
}

function deepMerge(base: QCConfig, override: Partial<QCConfig>): QCConfig {
  const result = structuredClone(base) as unknown as Record<string, unknown>
  for (const key of Object.keys(override) as (keyof QCConfig)[]) {
    const val = override[key]
    if (val === undefined || val === null) continue
    const baseVal = base[key]
    if (
      typeof val === 'object' &&
      !Array.isArray(val) &&
      typeof baseVal === 'object' &&
      !Array.isArray(baseVal)
    ) {
      result[key] = { ...(baseVal as object), ...(val as object) }
    } else {
      result[key] = val
    }
  }
  return result as unknown as QCConfig
}

export function downloadJson(data: unknown, filename: string) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

export async function parseConfigFile(file: File): Promise<QCConfig> {
  const text = await file.text()
  const raw = JSON.parse(text)
  const cleaned = stripMeta(raw) as Partial<QCConfig>
  return deepMerge(DEFAULT_CONFIG, cleaned)
}

export function loadProfiles(): SavedProfile[] {
  try {
    return JSON.parse(localStorage.getItem(PROFILE_STORAGE_KEY) ?? '[]')
  } catch {
    return []
  }
}

export function persistProfiles(profiles: SavedProfile[]) {
  localStorage.setItem(PROFILE_STORAGE_KEY, JSON.stringify(profiles))
}

// ── Template ──────────────────────────────────────────────────────────────────
// _info fields are stripped on import — they exist purely as in-file documentation
export const BLANK_TEMPLATE = {
  _info: "Servallab QC Config — set enabled: true for each check you want, fill in your column names. _info fields are ignored on import.",

  missing_threshold: 0.1,

  straightlining: {
    _info: "Flags respondents who give the same answer across all grid/scale question columns.",
    enabled: false,
    question_columns: ["q1", "q2", "q3", "q4", "q5"],
    threshold: 0.9,
    min_questions: 3,
    interviewer_column: "interviewer_id",
  },

  logic_rules: [
    {
      _info: "Add one block per rule. Operators: >, <, >=, <=, ==, !=, is_null, not_null, in_list, not_in_list",
      description: "Consented respondents must answer Q1",
      if_conditions: [{ column: "consent", operator: "==", value: "yes" }],
      then_conditions: [{ column: "q1", operator: "not_null" }],
    },
  ],

  range_rules: [
    { column: "age", min: 18, max: 99 },
  ],

  pattern_rules: [
    { column: "phone", pattern: "^\\d{10}$", description: "10-digit phone number" },
  ],

  duplicate_check: {
    _info: "Flags exact duplicate rows, optionally scoped to a subset of columns.",
    enabled: true,
    subset_columns: ["respondent_id"],
  },

  interview_duration: {
    _info: "Flags interviews shorter or longer than expected (in minutes).",
    enabled: false,
    column: "duration_minutes",
    min_expected: 5,
    max_expected: 120,
  },

  interviewer_duration_check: {
    _info: "Flags interviewers whose average duration is suspiciously low or high vs the group median.",
    enabled: false,
    interviewer_column: "interviewer_id",
    duration_column: "duration_minutes",
    multiplier: 1.5,
    min_interviews: 3,
  },

  interviewer_productivity_check: {
    _info: "Flags interviewers with an abnormally high number of completed interviews.",
    enabled: false,
    interviewer_column: "interviewer_id",
    multiplier: 1.5,
  },

  consent_eligibility_check: {
    _info: "Flags ineligible respondents who still have answers in subsequent question columns.",
    enabled: false,
    screener_column: "eligible",
    disqualify_operator: "!=",
    disqualify_value: "yes",
    subsequent_columns: ["q1", "q2", "q3"],
  },

  fabrication_check: {
    _info: "Detects suspiciously repetitive or patterned numeric answers suggesting data fabrication.",
    enabled: false,
    id_column: "respondent_id",
    numeric_columns: ["q1", "q2", "q3", "q4"],
    interviewer_column: "interviewer_id",
    variance_threshold: 0.1,
    sequence_run_length: 5,
  },

  verbatim_check: {
    _info: "AI grammar quality scoring for open-ended responses. Requires a Groq API key (set in Settings).",
    enabled: false,
    verbatim_columns: ["open_end_1", "open_end_2"],
    min_score: 2,
    sample_size: 50,
  },
}
