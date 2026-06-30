import React, { useRef, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid, ResponsiveContainer,
  ReferenceLine,
} from 'recharts'
import { Upload, Loader2, Trash2, Download } from 'lucide-react'
import { useAppStore } from '../../../store/appStore'
import {
  getTimingRecords, getUploadLog, uploadTiming, deleteUpload, downloadTemplate,
  type TimingRecord, type UploadLogEntry,
} from '../../../api/dashboard'

const C = {
  accent: '#00B5A3', critical: '#1B2A4A', warning: '#00B5A3', muted: '#6B7280',
  surface: '#FFFFFF', surface2: '#F1F4F8', line: '#E2E6ED', tx: '#1B2A4A',
}
const TooltipStyle = {
  contentStyle: { backgroundColor: C.surface2, border: `1px solid ${C.line}`, borderRadius: 6, color: C.tx },
  itemStyle: { color: C.tx }, labelStyle: { color: C.muted },
}
const UPLOAD_ROLES = new Set(['qc_executive', 'operations_manager', 'qc_officer'])

interface Props { projectId: number; loiMin?: number }

export function TimingTab({ projectId, loiMin = 0 }: Props) {
  const { authUser, authToken } = useAppStore()
  const token = authToken ?? ''
  const qc = useQueryClient()
  const fileRef = useRef<HTMLInputElement>(null)
  const [waveLabel, setWaveLabel] = useState('')
  const [file, setFile] = useState<File | null>(null)

  const { data: records = [], isLoading } = useQuery({
    queryKey: ['dash-timing', projectId],
    queryFn: () => getTimingRecords(projectId, token),
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
      return uploadTiming(projectId, file, token, waveLabel || undefined)
    },
    onSuccess: () => {
      setFile(null); setWaveLabel('')
      qc.invalidateQueries({ queryKey: ['dash-timing', projectId] })
      qc.invalidateQueries({ queryKey: ['dash-upload-log', projectId] })
    },
  })

  const delMut = useMutation({
    mutationFn: (uid: string) => deleteUpload(uid, 'timing', token),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['dash-timing', projectId] })
      qc.invalidateQueries({ queryKey: ['dash-upload-log', projectId] })
    },
  })

  const canUpload = authUser && UPLOAD_ROLES.has(authUser.role)
  const timingLogs = uploadLog.filter((u: UploadLogEntry) => u.report_type === 'timing')

  const durations = records.map((r: TimingRecord) => r.duration_minutes).filter((d): d is number => d !== null)
  const avg = durations.length > 0 ? durations.reduce((a, b) => a + b, 0) / durations.length : 0
  const median = durations.length > 0
    ? [...durations].sort((a, b) => a - b)[Math.floor(durations.length / 2)]
    : 0
  const belowLoi = loiMin > 0 ? durations.filter(d => d < loiMin).length : 0

  const chartData = records
    .filter((r: TimingRecord) => r.interview_date && r.duration_minutes !== null)
    .sort((a: TimingRecord, b: TimingRecord) => (a.interview_date ?? '').localeCompare(b.interview_date ?? ''))
    .slice(0, 300)
    .map((r: TimingRecord) => ({ date: r.interview_date, duration: r.duration_minutes }))

  return (
    <div className="space-y-6">
      {canUpload && (
        <div className="card p-4 space-y-3">
          <div className="flex items-center justify-between">
            <p className="label">Upload Timing Data (Excel)</p>
            <button onClick={() => downloadTemplate('timing', token)} className="btn-ghost flex items-center gap-1.5 text-xs">
              <Download size={12} /> Download template
            </button>
          </div>
          <div className="flex flex-wrap gap-3 items-end">
            <div>
              <label className="label mb-1 block">File</label>
              <input ref={fileRef} type="file" accept=".xlsx,.xls" onChange={e => setFile(e.target.files?.[0] ?? null)} className="text-sm text-muted" />
            </div>
            <div>
              <label className="label mb-1 block">Wave Label</label>
              <input value={waveLabel} onChange={e => setWaveLabel(e.target.value)} placeholder="e.g. Wave 1"
                className="bg-surface2 border border-line rounded-lg px-3 py-2 text-sm text-tx placeholder:text-muted w-36" />
            </div>
            <button onClick={() => uploadMut.mutate()} disabled={!file || uploadMut.isPending} className="btn-primary flex items-center gap-2">
              {uploadMut.isPending ? <Loader2 size={14} className="animate-spin" /> : <Upload size={14} />} Upload
            </button>
            {uploadMut.isSuccess && <span className="text-xs text-accent">Uploaded!</span>}
            {uploadMut.isError && <span className="text-xs text-critical">{String(uploadMut.error)}</span>}
          </div>
        </div>
      )}

      {timingLogs.length > 0 && (
        <div className="card p-4">
          <p className="label mb-2">Upload History</p>
          <table className="w-full text-xs">
            <thead><tr className="border-b border-line text-muted">
              {['File', 'Wave', 'Rows', 'Date', ''].map(h => <th key={h} className="text-left py-1 pr-3">{h}</th>)}
            </tr></thead>
            <tbody>
              {timingLogs.map((u: UploadLogEntry) => (
                <tr key={u.id} className="border-b border-line/40">
                  <td className="py-1 pr-3 text-tx">{u.filename}</td>
                  <td className="py-1 pr-3 text-muted">{u.wave_label ?? '—'}</td>
                  <td className="py-1 pr-3 text-muted">{u.row_count}</td>
                  <td className="py-1 pr-3 text-muted">{u.upload_date?.slice(0, 10)}</td>
                  {canUpload && <td><button onClick={() => delMut.mutate(u.upload_id)} className="p-1 text-muted hover:text-critical"><Trash2 size={12} /></button></td>}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {isLoading && <div className="flex items-center gap-2 text-muted text-sm"><Loader2 size={14} className="animate-spin" /> Loading…</div>}

      {!isLoading && records.length === 0 && (
        <div className="card p-8 text-center text-muted text-sm">No timing records yet. Upload a timing Excel file.</div>
      )}

      {records.length > 0 && (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {[
              { label: 'Total Records', value: records.length, color: 'text-tx' },
              { label: 'Average (min)', value: avg.toFixed(1), color: 'text-accent' },
              { label: 'Median (min)', value: median.toFixed(1), color: 'text-info' },
              { label: loiMin > 0 ? `Below ${loiMin} min LOI` : 'Below avg', value: belowLoi, color: belowLoi > 0 ? 'text-critical' : 'text-muted' },
            ].map(k => (
              <div key={k.label} className="card p-4">
                <p className="label mb-1">{k.label}</p>
                <p className={`text-2xl font-bold font-display ${k.color}`}>{k.value}</p>
              </div>
            ))}
          </div>

          {chartData.length > 0 && (
            <div className="card p-4">
              <p className="label mb-3">Duration over time</p>
              <ResponsiveContainer width="100%" height={240}>
                <LineChart data={chartData} margin={{ left: -20 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke={C.line} />
                  <XAxis dataKey="date" tick={{ fill: C.muted, fontSize: 9 }} />
                  <YAxis tick={{ fill: C.muted, fontSize: 10 }} />
                  <Tooltip {...TooltipStyle} />
                  <Line type="monotone" dataKey="duration" stroke={C.accent} dot={false} strokeWidth={1.5} />
                  {avg > 0 && <ReferenceLine y={avg} stroke={C.warning} strokeDasharray="4 4" label={{ value: 'avg', fill: C.warning, fontSize: 9 }} />}
                  {loiMin > 0 && <ReferenceLine y={loiMin} stroke={C.critical} strokeDasharray="4 4" label={{ value: 'LOI min', fill: C.critical, fontSize: 9 }} />}
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}

          <div className="card p-4">
            <p className="label mb-2">Records (first 200)</p>
            <div className="overflow-x-auto max-h-80">
              <table className="w-full text-xs">
                <thead className="sticky top-0 bg-surface">
                  <tr className="border-b border-line text-muted">
                    {['Instance', 'Interviewer', 'Region', 'Date', 'Duration (min)'].map(h => (
                      <th key={h} className="text-left py-1 pr-3 whitespace-nowrap">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {records.slice(0, 200).map((r: TimingRecord) => (
                    <tr key={r.id} className="border-b border-line/30 hover:bg-surface2/50">
                      <td className="py-1 pr-3 font-mono text-muted">{r.instance_id ?? '—'}</td>
                      <td className="py-1 pr-3 text-tx">{r.interviewer_id ?? '—'}</td>
                      <td className="py-1 pr-3 text-muted">{r.region ?? '—'}</td>
                      <td className="py-1 pr-3 text-muted">{r.interview_date ?? '—'}</td>
                      <td className={`py-1 pr-3 font-mono ${loiMin > 0 && (r.duration_minutes ?? 0) < loiMin ? 'text-critical' : 'text-accent'}`}>
                        {r.duration_minutes?.toFixed(1) ?? '—'}
                      </td>
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
