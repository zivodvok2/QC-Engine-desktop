// ── API response shapes ────────────────────────────────────────────────────────

export interface UploadResponse {
  file_id: string;
  filename: string;
  rows: number;
  columns: number;
  column_names: string[];
}

export interface ColumnsResponse {
  columns: string[];
  dtypes: Record<string, string>;
  sample: Record<string, unknown>[];
}

export interface RunResponse {
  job_id: string;
  status: string;
}

export interface JobStatus {
  job_id: string;
  status: 'queued' | 'running' | 'complete' | 'failed';
  progress: number;
  error?: string;
}

export interface CheckResult {
  check_name: string;
  issue_type: string;
  severity: 'critical' | 'warning' | 'info';
  flag_count: number;
  flagged_rows: Record<string, unknown>[];
}

export interface QCResults {
  job_id: string;
  total_flags: number;
  flagged_by_severity: Record<string, number>;
  checks: CheckResult[];
}

export interface LogicValidateResponse {
  violation_count: number;
  flagged_rows: Record<string, unknown>[];
}

export interface EDABarData   { name: unknown; [key: string]: unknown }
export interface EDAHistBin   { bin: string; count: number }
export interface EDAScatterPt { x: unknown; y: unknown; [key: string]: unknown }
export interface EDAHeatmap   { columns: string[]; matrix: (number | null)[][] }

export interface EDAResponse {
  chart_type: string;
  data: unknown;
  metadata: Record<string, unknown>;
}

// ── QC config shape (mirrors backend) ─────────────────────────────────────────

export interface RangeRule   { column: string; min?: number; max?: number }
export interface PatternRule { column: string; pattern: string; description?: string }

export interface LogicCondition {
  column: string;
  operator: string;
  value?: unknown;
}

export interface LogicRule {
  description?: string;
  if_conditions?: LogicCondition[];
  then_conditions?: LogicCondition[];
  // legacy flat format
  if_column?: string;
  if_value?: unknown;
  then_column?: string;
  then_condition?: string;
}

export interface QCConfig {
  missing_threshold: number;
  range_rules: RangeRule[];
  logic_rules: LogicRule[];
  pattern_rules: PatternRule[];
  duplicate_check: { enabled: boolean; subset_columns: string[] };
  interview_duration: { enabled: boolean; column: string; min_expected: number; max_expected: number };
  straightlining: {
    enabled: boolean;
    question_columns: string[];
    threshold: number;
    min_questions: number;
    interviewer_column?: string;
  };
  interviewer_duration_check: {
    enabled: boolean;
    interviewer_column: string;
    duration_column: string;
    multiplier: number;
    min_interviews: number;
  };
  interviewer_productivity_check: {
    enabled: boolean;
    interviewer_column: string;
    multiplier: number;
    date_column?: string;
  };
  consent_eligibility_check: {
    enabled: boolean;
    screener_column: string;
    disqualify_operator: string;
    disqualify_value: string;
    subsequent_columns: string[];
  };
  fabrication_check: {
    enabled: boolean;
    id_column?: string;
    numeric_columns: string[];
    interviewer_column?: string;
    variance_threshold: number;
    sequence_run_length: number;
  };
  near_duplicate_check: {
    enabled: boolean;
    id_column?: string;
    unique_columns: string[];
    combo_columns: string[];
    max_combo_count: number;
  };
  verbatim_check: {
    enabled: boolean;
    verbatim_columns: string[];
    model: string;
    min_score: number;
    sample_size: number;
    groq_api_key?: string;
  };
}

export const DEFAULT_CONFIG: QCConfig = {
  missing_threshold: 0.1,
  range_rules: [],
  logic_rules: [],
  pattern_rules: [],
  duplicate_check: { enabled: true, subset_columns: [] },
  interview_duration: { enabled: false, column: 'duration_minutes', min_expected: 5, max_expected: 120 },
  straightlining: { enabled: false, question_columns: [], threshold: 0.9, min_questions: 3, interviewer_column: '' },
  interviewer_duration_check: { enabled: false, interviewer_column: '', duration_column: 'duration_minutes', multiplier: 1.5, min_interviews: 3 },
  interviewer_productivity_check: { enabled: false, interviewer_column: '', multiplier: 1.5 },
  consent_eligibility_check: { enabled: false, screener_column: '', disqualify_operator: '!=', disqualify_value: '', subsequent_columns: [] },
  fabrication_check: { enabled: false, id_column: undefined, numeric_columns: [], interviewer_column: undefined, variance_threshold: 0.1, sequence_run_length: 5 },
  near_duplicate_check: { enabled: false, id_column: undefined, unique_columns: [], combo_columns: [], max_combo_count: 3 },
  verbatim_check: { enabled: false, verbatim_columns: [], model: 'llama-3.1-8b-instant', min_score: 2, sample_size: 50 },
};
