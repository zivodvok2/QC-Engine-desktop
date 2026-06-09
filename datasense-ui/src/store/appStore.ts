import { create } from 'zustand'
import type { QCConfig, QCResults, UploadResponse } from '../types'
import { DEFAULT_CONFIG } from '../types'
import {
  type SavedProfile,
  loadProfiles,
  persistProfiles,
} from '../utils/configProfiles'

type JobStatus = 'idle' | 'queued' | 'running' | 'complete' | 'failed'

// ── Tab state types ───────────────────────────────────────────────────────────

export interface IfCondition {
  id: number
  col: string
  op: string
  val: string
  connector: 'AND' | 'OR'
}

export interface RuleBuilderState {
  id: number
  if_conditions: IfCondition[]
  then_cols: string[]
  then_op: string
  then_val: string
  description: string
}

export interface CheckSet {
  id: number
  name: string
  rules: RuleBuilderState[]
  result: { violation_count: number; flagged_rows: Record<string, unknown>[] } | null
  isRunning: boolean
}

export interface SlTabState {
  baseVar: string[]
  qCols: string[]
  threshold: number
  minQ: number
  result: QCResults | null
}

export interface ItvTabState {
  intCol: string
  redThr: number
  amberThr: number
  flagThr: number
  rows: Record<string, unknown>[]
  intColName: string
  selectedInt: string
}

interface AppState {
  // file
  fileId: string | null
  filename: string | null
  rowCount: number | null
  columnCount: number | null
  columnNames: string[]
  dtypes: Record<string, string>
  previewRows: Record<string, unknown>[]

  // job
  jobId: string | null
  jobStatus: JobStatus
  jobProgress: number
  jobError: string | null

  // results
  results: QCResults | null

  // config
  config: QCConfig

  // groq
  groqApiKey: string

  // ui
  activeTab: string
  demosOpen: boolean
  settingsOpen: boolean
  theme: 'dark' | 'light' | 'midnight'
  accent: 'emerald' | 'blue' | 'purple' | 'orange' | 'pink'

  // saved profiles
  savedProfiles: SavedProfile[]

  // tab state — persists across tab switches
  logicCheckSets: CheckSet[]
  slTabState: SlTabState
  itvTabState: ItvTabState

  // supplemental results from tab runs — shown in QC Report tab
  supplementalChecks: import('../types').CheckResult[]

  // actions
  setFile: (data: UploadResponse) => void
  setPreview: (rows: Record<string, unknown>[], dtypes: Record<string, string>) => void
  setJobId: (id: string) => void
  setJobStatus: (status: JobStatus, progress: number) => void
  setJobError: (err: string) => void
  setResults: (r: QCResults) => void
  updateConfig: (patch: Partial<QCConfig>) => void
  loadConfig: (config: QCConfig) => void
  setGroqApiKey: (key: string) => void
  setActiveTab: (tab: string) => void
  openDemos: () => void
  closeDemos: () => void
  openSettings: () => void
  closeSettings: () => void
  setTheme: (t: 'dark' | 'light' | 'midnight') => void
  setAccent: (a: 'emerald' | 'blue' | 'purple' | 'orange' | 'pink') => void
  saveProfile: (name: string) => void
  deleteProfile: (name: string) => void
  setLogicCheckSets: (sets: CheckSet[]) => void
  setSlTabState: (patch: Partial<SlTabState>) => void
  setItvTabState: (patch: Partial<ItvTabState>) => void
  addSupplementalCheck: (check: import('../types').CheckResult) => void
  clearFile: () => void
  reset: () => void
}

export const useAppStore = create<AppState>((set) => ({
  fileId: null,
  filename: null,
  rowCount: null,
  columnCount: null,
  columnNames: [],
  dtypes: {},
  previewRows: [],

  jobId: null,
  jobStatus: 'idle',
  jobProgress: 0,
  jobError: null,

  results: null,
  config: structuredClone(DEFAULT_CONFIG),
  savedProfiles: loadProfiles(),

  logicCheckSets: [{ id: 1, name: 'Check Set 1', rules: [{ id: 1, if_conditions: [{ id: 1, col: '', op: '==', val: '', connector: 'AND' as const }], then_cols: [], then_op: 'is_null', then_val: '', description: '' }], result: null, isRunning: false }],
  slTabState: { baseVar: [], qCols: [], threshold: 0.9, minQ: 3, result: null },
  itvTabState: { intCol: '', redThr: 60, amberThr: 30, flagThr: 10, rows: [], intColName: '', selectedInt: '' },
  supplementalChecks: [],
  groqApiKey: localStorage.getItem('ds_groq_api_key') ?? '',
  activeTab: 'QC Report',
  demosOpen: false,
  settingsOpen: false,
  theme: (localStorage.getItem('ds_theme') as 'dark' | 'light' | 'midnight') ?? 'dark',
  accent: (localStorage.getItem('ds_accent') as 'emerald' | 'blue' | 'purple' | 'orange' | 'pink') ?? 'emerald',

  setFile: (data) =>
    set({
      fileId: data.file_id,
      filename: data.filename,
      rowCount: data.rows,
      columnCount: data.columns,
      columnNames: data.column_names,
      // reset job on new upload
      jobId: null,
      jobStatus: 'idle',
      jobProgress: 0,
      jobError: null,
      results: null,
    }),

  setPreview: (rows, dtypes) => set({ previewRows: rows, dtypes }),

  setJobId: (id) => set({ jobId: id, jobStatus: 'queued', jobProgress: 0, jobError: null }),

  setJobStatus: (status, progress) => set({ jobStatus: status, jobProgress: progress }),

  setJobError: (err) => set({ jobStatus: 'failed', jobError: err }),

  setResults: (r) => set({ results: r, jobStatus: 'complete', jobProgress: 100 }),

  updateConfig: (patch) =>
    set((s) => ({ config: { ...s.config, ...patch } })),

  loadConfig: (config) => set({ config }),

  saveProfile: (name) =>
    set((s) => {
      const existing = s.savedProfiles.filter((p) => p.name !== name)
      const updated: SavedProfile[] = [
        { name, config: structuredClone(s.config), savedAt: new Date().toISOString() },
        ...existing,
      ]
      persistProfiles(updated)
      return { savedProfiles: updated }
    }),

  deleteProfile: (name) =>
    set((s) => {
      const updated = s.savedProfiles.filter((p) => p.name !== name)
      persistProfiles(updated)
      return { savedProfiles: updated }
    }),

  setLogicCheckSets: (sets) => set({ logicCheckSets: sets }),
  setSlTabState: (patch) => set((s) => ({ slTabState: { ...s.slTabState, ...patch } })),
  setItvTabState: (patch) => set((s) => ({ itvTabState: { ...s.itvTabState, ...patch } })),
  addSupplementalCheck: (check) => set((s) => ({
    supplementalChecks: [...s.supplementalChecks.filter((c) => c.check_name !== check.check_name), check],
  })),

  setGroqApiKey: (key) => {
    localStorage.setItem('ds_groq_api_key', key)
    set({ groqApiKey: key })
  },

  setActiveTab: (tab) => set({ activeTab: tab }),

  openDemos: () => set({ demosOpen: true }),
  closeDemos: () => set({ demosOpen: false }),
  openSettings: () => set({ settingsOpen: true }),
  closeSettings: () => set({ settingsOpen: false }),

  setTheme: (t) => {
    localStorage.setItem('ds_theme', t)
    set({ theme: t })
  },
  setAccent: (a) => {
    localStorage.setItem('ds_accent', a)
    set({ accent: a })
  },

  clearFile: () =>
    set({
      fileId: null, filename: null, rowCount: null, columnCount: null,
      columnNames: [], dtypes: {}, previewRows: [],
      jobId: null, jobStatus: 'idle', jobProgress: 0, jobError: null,
      results: null, supplementalChecks: [], activeTab: 'QC Report',
    }),

  reset: () =>
    set({
      fileId: null, filename: null, rowCount: null, columnCount: null,
      columnNames: [], dtypes: {}, previewRows: [],
      jobId: null, jobStatus: 'idle', jobProgress: 0, jobError: null,
      results: null, config: structuredClone(DEFAULT_CONFIG), activeTab: 'QC Report',
    }),
}))
