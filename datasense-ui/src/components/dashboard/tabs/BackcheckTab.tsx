import React, { useRef, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, ResponsiveContainer, Legend,
} from 'recharts'
import { Upload, Loader2, Trash2, Download } from 'lucide-react'
import { useAppStore } from '../../../store/appStore'
import {
  getBackcheckRecords, getUploadLog, uploadBackcheck, deleteUpload, downloadTemplate,
  type BackcheckRecord, type UploadLogEntry,
} from '../../../api/dashboard'

const C = {
  accent: '#00B5A3', critical: '#1B2A4A', warning: '#00B5A3', info: '#1B2A4A',
  purple: '#1B2A4A', muted: '#6B7280', surface: '#FFFFFF', surface2: '#F1F4F8',
  line: '#E2E6ED', tx: '#1B2A4A',
}
const PALETTE = ['#00B5A3', '#1B2A4A', '#00B5A3', '#1B2A4A', '#00B5A3', '#1B2A4A', '#00B5A3', '#1B2A4A']

const UPLOAD_ROLES = new Set(['qc_executive', 'operations_manager', 'qc_officer'])

const BACKCHECK_ERRORS: Record<string, string> = {
  error_01: 'Fraudulent',
  error_02: 'Diff respondent',
  error_03: 'Wrong quotas',
  error_04: 'Wrong usership',
  error_05: 'Wrong phone',
  error_06: 'Unattainable',
  error_07: 'Eng/Answerph',
  error_08: 'Refused',
  error_09: "Doesn't remember",
  error_10: 'BC abandoned',
  error_11: 'Wrong mode',
  error_12: 'Voice perm.',
  error_13: 'Already part.',
}

const TooltipStyle = {
  contentStyle: { backgroundColor: C.surface2, border: `1px solid ${C.line}`, borderRadius: 6, color: C.tx },
  itemStyle: { color: C.tx },
  labelStyle: { color: C.muted },
}

interface Props { projectId: number; target?: number }

export function BackcheckTab({ projectId, target = 0.20 }: Props) {
  const { authUser, authToken } = useAppStore()
  const token = authToken ?? ''
  const qc = useQueryClient()

  const fileRef = useRef<HTMLInputElement>(null)
  const [waveLabel, setWaveLabel] = useState('')
  const [file, setFile] = useState<File | null>(null)

  const { data: records = [], isLoading } = useQuery({
    queryKey: ['dash-backcheck', projectId],
    queryFn: () => getBackcheckRecords(projectId, token),
    enabled: !!token,
  })

  const { data: uploadLog = [] } = useQuery({
    queryKey: ['dash-upload-log', projectId],
    queryFn: () => getUploadLog(projectId, token),
    enabled: !!token,
  })

  const uploadMut = useMutation({
    mutationFn: () => {
      if (!file) throw new Error('No file selected')
      return uploadBackcheck(projectId, file, token, waveLabel || undefined)
    },
    onSuccess: () => {
      setFile(null)
      setWaveLabel('')
      qc.invalidateQueries({ queryKey: ['dash-backcheck', projectId] })
      qc.invalidateQueries({ queryKey: ['dash-upload-log', projectId] })
      qc.invalidateQueries({ queryKey: ['dash-summary'] })
    },
  })

  const delMut = useMutation({
    mutationFn: (uid: string) => deleteUpload(uid, 'backcheck', token),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['dash-backcheck', projectId] })
      qc.invalidateQueries({ queryKey: ['dash-upload-log', projectId] })
      qc.invalidateQueries({ queryKey: ['dash-summary'] })
    },
  })

  const canUpload = authUser && UPLOAD_ROLES.has(authUser.role)

  // KPIs
  const bcCount = records.length
  const bcLogs = uploadLog.filter((u: UploadLogEntry) => u.report_type === 'backcheck')

  // Error type aggregation
  const errorTotals: Record<string, number> = {}
  records.forEach((r: BackcheckRecord) => {
    for (let i = 1; i <= 13; i++) {
      const key = `error_${String(i).padStart(2, '0')}` as keyof BackcheckRecord
      const val = r[key] as number
      if (val > 0) {
        errorTotals[key] = (errorTotals[key] ?? 0) + val
      }
    }
  })
  const errorData = Object.entries(errorTotals)
    .map(([key, count]) => ({ name: BACKCHECK_ERRORS[key] ?? key, count }))
    .sort((a, b) => b.count - a.count)

  return (
    <div className="space-y-6">
      {/* Upload section */}
      {canUpload && (
        <div className="card p-4 space-y-3">
          <div className="flex items-center justify-between">
            <p className="label">Upload Back-check Data (Excel)</p>
            <button
              onClick={() => downloadTemplate('backcheck', token)}
              className="btn-ghost flex items-center gap-1.5 text-xs"
              title="Download the Excel template with the correct column headers"
            >
              <Download size={12} /> Download template
            </button>
          </div>
          <div className="flex flex-wrap gap-3 items-end">
            <div>
              <label className="label mb-1 block">File</label>
              <input
                ref={fileRef}
                type="file"
                accept=".xlsx,.xls"
                onChange={e => setFile(e.target.files?.[0] ?? null)}
                className="text-sm text-muted"
              />
            </div>
            <div>
              <label className="label mb-1 block">Wave Label</label>
              <input
                value={waveLabel}
                onChange={e => setWaveLabel(e.target.value)}
                placeholder="e.g. Wave 1"
                className="bg-surface2 border border-line rounded-lg px-3 py-2 text-sm text-tx placeholder:text-muted w-36"
              />
            </div>
            <button
              onClick={() => uploadMut.mutate()}
              disabled={!file || uploadMut.isPending}
              className="btn-primary flex items-center gap-2"
            >
              {uploadMut.isPending ? <Loader2 size={14} className="animate-spin" /> : <Upload size={14} />}
              Upload
            </button>
            {uploadMut.isSuccess && <span className="text-xs text-accent">Uploaded!</span>}
            {uploadMut.isError && <span className="text-xs text-critical">{String(uploadMut.error)}</span>}
          </div>
        </div>
      )}

      {/* Upload history */}
      {bcLogs.length > 0 && (
        <div className="card p-4">
          <p className="label mb-2">Upload History</p>
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-line text-muted">
                <th className="text-left py-1 pr-3">File</th>
                <th className="text-left py-1 pr-3">Wave</th>
                <th className="text-left py-1 pr-3">Rows</th>
                <th className="text-left py-1 pr-3">Date</th>
                {canUpload && <th />}
              </tr>
            </thead>
            <tbody>
              {bcLogs.map((u: UploadLogEntry) => (
                <tr key={u.id} className="border-b border-line/40">
                  <td className="py-1 pr-3 text-tx">{u.filename}</td>
                  <td className="py-1 pr-3 text-muted">{u.wave_label ?? '—'}</td>
                  <td className="py-1 pr-3 text-muted">{u.row_count}</td>
                  <td className="py-1 pr-3 text-muted">{u.upload_date?.slice(0, 10)}</td>
                  {canUpload && (
                    <td>
                      <button
                        onClick={() => delMut.mutate(u.upload_id)}
                        className="p-1 text-muted hover:text-critical transition-colors"
                      >
                        <Trash2 size={12} />
                      </button>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {isLoading && (
        <div className="flex items-center gap-2 text-muted text-sm">
          <Loader2 size={14} className="animate-spin" /> Loading…
        </div>
      )}

      {!isLoading && records.length === 0 && (
        <div className="card p-8 text-center text-muted text-sm">
          No back-check records yet. Upload a back-check Excel file.
        </div>
      )}

      {records.length > 0 && (
        <>
          {/* KPI cards */}
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            <div className="card p-4">
              <p className="label mb-1">BC Records</p>
              <p className="text-2xl font-bold font-display text-accent">{bcCount}</p>
            </div>
            <div className="card p-4">
              <p className="label mb-1">BC Target</p>
              <p className="text-2xl font-bold font-display text-muted">{Math.round(target * 100)}%</p>
            </div>
            <div className="card p-4">
              <p className="label mb-1">Total Error Counts</p>
              <p className="text-2xl font-bold font-display text-warning">
                {Object.values(errorTotals).reduce((a, b) => a + b, 0)}
              </p>
            </div>
          </div>

          {/* Error chart */}
          {errorData.length > 0 && (
            <div className="card p-4">
              <p className="label mb-3">Errors by Type</p>
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={errorData} margin={{ left: -20 }} layout="vertical">
                  <CartesianGrid strokeDasharray="3 3" stroke={C.line} horizontal={false} />
                  <XAxis type="number" tick={{ fill: C.muted, fontSize: 10 }} />
                  <YAxis type="category" dataKey="name" width={110} tick={{ fill: C.muted, fontSize: 10 }} />
                  <Tooltip {...TooltipStyle} />
                  <Bar dataKey="count" fill={C.critical} radius={[0, 2, 2, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Data table */}
          <div className="card p-4">
            <p className="label mb-2">Records (first 200)</p>
            <div className="overflow-x-auto max-h-80">
              <table className="w-full text-xs">
                <thead className="sticky top-0 bg-surface">
                  <tr className="border-b border-line text-muted">
                    {['BC Instance', 'Orig Instance', 'Interviewer', 'Backchecker', 'Date', 'BC Date', 'Status'].map(h => (
                      <th key={h} className="text-left py-1 pr-3 whitespace-nowrap">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {records.slice(0, 200).map((r: BackcheckRecord) => (
                    <tr key={r.id} className="border-b border-line/30 hover:bg-surface2/50">
                      <td className="py-1 pr-3 font-mono text-tx">{r.bc_instance_id ?? '—'}</td>
                      <td className="py-1 pr-3 font-mono text-muted">{r.original_instance_id ?? '—'}</td>
                      <td className="py-1 pr-3 text-muted">{r.interviewer_id ?? '—'}</td>
                      <td className="py-1 pr-3 text-muted">{r.backchecker_id ?? '—'}</td>
                      <td className="py-1 pr-3 text-muted">{r.interview_date ?? '—'}</td>
                      <td className="py-1 pr-3 text-muted">{r.backcheck_date ?? '—'}</td>
                      <td className="py-1 pr-3 text-muted">{r.interview_status ?? '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
