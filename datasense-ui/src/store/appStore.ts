import { create } from 'zustand'
import type { QCConfig, QCResults, UploadResponse } from '../types'
import { DEFAULT_CONFIG } from '../types'

type JobStatus = 'idle' | 'queued' | 'running' | 'complete' | 'failed'

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

  // actions
  setFile: (data: UploadResponse) => void
  setPreview: (rows: Record<string, unknown>[], dtypes: Record<string, string>) => void
  setJobId: (id: string) => void
  setJobStatus: (status: JobStatus, progress: number) => void
  setJobError: (err: string) => void
  setResults: (r: QCResults) => void
  updateConfig: (patch: Partial<QCConfig>) => void
  setGroqApiKey: (key: string) => void
  setActiveTab: (tab: string) => void
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
  groqApiKey: localStorage.getItem('ds_groq_api_key') ?? '',
  activeTab: 'QC Report',

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

  setGroqApiKey: (key) => {
    localStorage.setItem('ds_groq_api_key', key)
    set({ groqApiKey: key })
  },

  setActiveTab: (tab) => set({ activeTab: tab }),

  reset: () =>
    set({
      fileId: null, filename: null, rowCount: null, columnCount: null,
      columnNames: [], dtypes: {}, previewRows: [],
      jobId: null, jobStatus: 'idle', jobProgress: 0, jobError: null,
      results: null, config: structuredClone(DEFAULT_CONFIG), activeTab: 'QC Report',
    }),
}))
