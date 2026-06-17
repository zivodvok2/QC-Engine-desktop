import { create } from 'zustand'
import type { QCConfig, QCResults, UploadResponse } from '../types'
import { DEFAULT_CONFIG } from '../types'
import {
  type SavedProfile,
  loadProfiles,
  persistProfiles,
} from '../utils/configProfiles'
import type { AuthUser } from '../api/auth'

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
  supervisorCol: string
  dateCol: string
  dateTrends: { date: string; flag_count: number }[]
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

  // auth
  authUser: AuthUser | null
  authToken: string | null
  loginOpen: boolean
  loginUser: (user: AuthUser, token: string) => void
  logoutUser: () => void
  openLogin: () => void
  closeLogin: () => void

  // dashboard mode
  dashboardMode: boolean
  dashboardProjectId: number | null
  dashboardView: 'overview' | 'project' | 'interviewers'
  setDashboardMode: (on: boolean) => void
  setDashboardProject: (id: number | null) => void
  setDashboardView: (view: 'overview' | 'project' | 'interviewers') => void

  // session restore
  sessionRestored: boolean
  sessionRestoredAt: string | null
  dismissSessionRestore: () => void
}

const SESSION_KEY = 'sl_session'
const SESSION_TTL_MS = 8 * 60 * 60 * 1000

function _loadSession() {
  try {
    const raw = sessionStorage.getItem(SESSION_KEY)
    if (!raw) return null
    const s = JSON.parse(raw)
    if (!s.ts || Date.now() - s.ts > SESSION_TTL_MS) { sessionStorage.removeItem(SESSION_KEY); return null }
    return s
  } catch { return null }
}

function _saveSession(state: { fileId: string | null; filename: string | null; rowCount: number | null; columnCount: number | null; columnNames: string[]; results: AppState['results']; config: AppState['config'] }) {
  try {
    sessionStorage.setItem(SESSION_KEY, JSON.stringify({ ...state, ts: Date.now() }))
  } catch { /* quota exceeded or private mode */ }
}

const _session = _loadSession()

export const useAppStore = create<AppState>((set) => ({
  fileId: _session?.fileId ?? null,
  filename: _session?.filename ?? null,
  rowCount: _session?.rowCount ?? null,
  columnCount: _session?.columnCount ?? null,
  columnNames: _session?.columnNames ?? [],
  dtypes: {},
  previewRows: [],

  jobId: null,
  jobStatus: 'idle',
  jobProgress: 0,
  jobError: null,

  results: _session?.results ?? null,
  config: _session?.config ? structuredClone(_session.config) : structuredClone(DEFAULT_CONFIG),
  savedProfiles: loadProfiles(),

  logicCheckSets: [{ id: 1, name: 'Check Set 1', rules: [{ id: 1, if_conditions: [{ id: 1, col: '', op: '==', val: '', connector: 'AND' as const }], then_cols: [], then_op: 'is_null', then_val: '', description: '' }], result: null, isRunning: false }],
  slTabState: { baseVar: [], qCols: [], threshold: 0.9, minQ: 3, result: null },
  itvTabState: { intCol: '', redThr: 60, amberThr: 30, flagThr: 10, rows: [], intColName: '', selectedInt: '', supervisorCol: '', dateCol: '', dateTrends: [] },
  supplementalChecks: [],
  groqApiKey: localStorage.getItem('ds_groq_api_key') ?? '',
  authUser: (() => {
    try { return JSON.parse(localStorage.getItem('ds_auth_user') ?? 'null') } catch { return null }
  })(),
  authToken: localStorage.getItem('ds_auth_token') ?? null,
  loginOpen: false,
  activeTab: 'QC Report',
  dashboardMode: false,
  dashboardProjectId: null,
  dashboardView: 'overview' as const,
  sessionRestored: !!_session?.results,
  sessionRestoredAt: _session ? new Date(_session.ts).toLocaleString() : null,
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

  setResults: (r) => set((s) => {
    _saveSession({ fileId: s.fileId, filename: s.filename, rowCount: s.rowCount, columnCount: s.columnCount, columnNames: s.columnNames, results: r, config: s.config })
    return { results: r, jobStatus: 'complete', jobProgress: 100 }
  }),

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

  loginUser: (user, token) => {
    localStorage.setItem('ds_auth_user', JSON.stringify(user))
    localStorage.setItem('ds_auth_token', token)
    set({ authUser: user, authToken: token, loginOpen: false })
  },
  logoutUser: () => {
    localStorage.removeItem('ds_auth_user')
    localStorage.removeItem('ds_auth_token')
    set({ authUser: null, authToken: null })
  },
  openLogin: () => set({ loginOpen: true }),
  closeLogin: () => set({ loginOpen: false }),

  setDashboardMode: (on) => set({ dashboardMode: on }),
  setDashboardProject: (id) => set({ dashboardProjectId: id, dashboardView: id !== null ? 'project' : 'overview' }),
  setDashboardView: (view) => set((s) => ({
    dashboardView: view,
    dashboardProjectId: view !== 'project' ? null : s.dashboardProjectId,
  })),

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

  clearFile: () => {
    sessionStorage.removeItem(SESSION_KEY)
    set({
      fileId: null, filename: null, rowCount: null, columnCount: null,
      columnNames: [], dtypes: {}, previewRows: [],
      jobId: null, jobStatus: 'idle', jobProgress: 0, jobError: null,
      results: null, supplementalChecks: [], activeTab: 'QC Report',
      sessionRestored: false, sessionRestoredAt: null,
    })
  },

  reset: () => {
    sessionStorage.removeItem(SESSION_KEY)
    set({
      fileId: null, filename: null, rowCount: null, columnCount: null,
      columnNames: [], dtypes: {}, previewRows: [],
      jobId: null, jobStatus: 'idle', jobProgress: 0, jobError: null,
      results: null, config: structuredClone(DEFAULT_CONFIG), activeTab: 'QC Report',
      sessionRestored: false, sessionRestoredAt: null,
    })
  },

  dismissSessionRestore: () => set({ sessionRestored: false, sessionRestoredAt: null }),
}))
