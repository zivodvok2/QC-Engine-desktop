import React, { useRef, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, Legend, PieChart, Pie, Cell,
  LineChart, Line, CartesianGrid, ResponsiveContainer,
} from 'recharts'
import { Upload, Loader2, Download, Trash2 } from 'lucide-react'
import { useAppStore } from '../../../store/appStore'
import {
  getQualityRecords, getUploadLog,
  deleteUpload,
  type QualityRecord, type UploadLogEntry,
} from '../../../api/dashboard'
import { saveQCResults } from '../../../api/projects'
import { getProjects } from '../../../api/projects'

const C = {
  accent: '#00B5A3', critical: '#1B2A4A', warning: '#00B5A3', info: '#1B2A4A',
  purple: '#1B2A4A', muted: '#6B7280', surface: '#FFFFFF', surface2: '#F1F4F8',
  line: '#E2E6ED', tx: '#1B2A4A',
}
const PALETTE = ['#00B5A3', '#1B2A4A', '#00B5A3', '#1B2A4A', '#00B5A3', '#1B2A4A', '#00B5A3', '#1B2A4A']

const UPLOAD_ROLES = new Set(['qc_executive', 'operations_manager', 'qc_officer'])

const TooltipStyle = {
  contentStyle: { backgroundColor: C.surface2, border: `1px solid ${C.line}`, borderRadius: 6, color: C.tx },
  itemStyle: { color: C.tx },
  labelStyle: { color: C.muted },
}

interface Props { projectId: number }

export function QualityReportTab({ projectId }: Props) {
  const { authUser, authToken, fileId, filename } = useAppStore()
  const token = authToken ?? ''
  const qc = useQueryClient()

  const [waveLabel, setWaveLabel] = useState('')
  const [selectedProjectId, setSelectedProjectId] = useState<number | null>(null)

  const { data: records = [], isLoading } = useQuery({
    queryKey: ['dash-quality', projectId],
    queryFn: () => getQualityRecords(projectId, token),
    enabled: !!token,
  })

  const { data: uploadLog = [] } = useQuery({
    queryKey: ['dash-upload-log', projectId],
    queryFn: () => getUploadLog(projectId, token),
    enabled: !!token,
  })

  const { data: projects = [] } = useQuery({
    queryKey: ['projects'],
    queryFn: () => getProjects(token),
    enabled: !!token && !!authUser && UPLOAD_ROLES.has(authUser.role),
  })

  const saveMut = useMutation({
    mutationFn: () => {
      if (!fileId || !filename) throw new Error('No file loaded')
      return saveQCResults(selectedProjectId ?? projectId, fileId, filename, token, waveLabel || undefined)
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['dash-quality', projectId] })
      qc.invalidateQueries({ queryKey: ['dash-upload-log', projectId] })
      qc.invalidateQueries({ queryKey: ['dash-summary'] })
    },
  })

  const delMut = useMutation({
    mutationFn: (uid: string) => deleteUpload(uid, 'quality_report', token),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['dash-quality', projectId] })
      qc.invalidateQueries({ queryKey: ['dash-upload-log', projectId] })
      qc.invalidateQueries({ queryKey: ['dash-summary'] })
    },
  })

  // KPIs
  const total = records.length
  const approved = records.filter((r: QualityRecord) => r.approval_status === 'Approved').length
  const pending = records.filter((r: QualityRecord) => r.approval_status === 'Pending').length
  const cancelled = records.filter((r: QualityRecord) => r.approval_status === 'Cancelled').length
  const flagged = records.filter((r: QualityRecord) => r.duration_flag === 'Flag').length

  // Pie chart data
  const pieData = [
    { name: 'Approved', value: approved },
    { name: 'Pending', value: pending },
    { name: 'Cancelled', value: cancelled },
  ].filter(d => d.value > 0)
  const pieColors = [C.accent, C.warning, C.critical]

  // Errors by interviewer (duration flag + straight lining)
  const byItv: Record<string, { duration_flag: number; straight_lining: number }> = {}
  records.forEach((r: QualityRecord) => {
    const id = r.interviewer_id ?? 'Unknown'
    if (!byItv[id]) byItv[id] = { duration_flag: 0, straight_lining: 0 }
    if (r.duration_flag === 'Flag') byItv[id].duration_flag++
    if (r.straight_lining === 'Flag') byItv[id].straight_lining++
  })
  const errorData = Object.entries(byItv)
    .map(([name, v]) => ({ name, ...v }))
    .sort((a, b) => (b.duration_flag + b.straight_lining) - (a.duration_flag + a.straight_lining))
    .slice(0, 15)

  // Interviews per day
  const byDay: Record<string, number> = {}
  records.forEach((r: QualityRecord) => {
    if (r.interview_date) byDay[r.interview_date] = (byDay[r.interview_date] ?? 0) + 1
  })
  const dayData = Object.entries(byDay)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([date, count]) => ({ date, count }))

  const canUpload = authUser && UPLOAD_ROLES.has(authUser.role)
  const qcReady = !!fileId

  const handleExport = () => {
    const json = JSON.stringify(records.slice(0, 200), null, 2)
    const blob = new Blob([json], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `quality_records_${projectId}.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="space-y-6">
      {/* Upload section */}
      {canUpload && qcReady && (
        <div className="card p-4 space-y-3">
          <p className="label">Save QC Results from Current File</p>
          <div className="flex flex-wrap gap-3 items-end">
            <div>
              <label className="label mb-1 block">Project</label>
              <select
                value={selectedProjectId ?? projectId}
                onChange={e => setSelectedProjectId(Number(e.target.value))}
                className="bg-surface2 border border-line rounded-lg px-3 py-2 text-sm text-tx"
              >
                {projects.map(p => (
                  <option key={p.id} value={p.id}>{p.name}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="label mb-1 block">Wave Label (optional)</label>
              <input
                value={waveLabel}
                onChange={e => setWaveLabel(e.target.value)}
                placeholder="e.g. Wave 1"
                className="bg-surface2 border border-line rounded-lg px-3 py-2 text-sm text-tx placeholder:text-muted w-40"
              />
            </div>
            <button
              onClick={() => saveMut.mutate()}
              disabled={saveMut.isPending}
              className="btn-primary flex items-center gap-2"
            >
              {saveMut.isPending ? <Loader2 size={14} className="animate-spin" /> : <Upload size={14} />}
              Save to DB
            </button>
            {saveMut.isSuccess && <span className="text-xs text-accent">Saved!</span>}
            {saveMut.isError && <span className="text-xs text-critical">{String(saveMut.error)}</span>}
          </div>
        </div>
      )}

      {/* Upload history */}
      {uploadLog.filter((u: UploadLogEntry) => u.report_type === 'quality_report').length > 0 && (
        <div className="card p-4">
          <p className="label mb-2">Upload History</p>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-line text-muted">
                  <th className="text-left py-1 pr-3">File</th>
                  <th className="text-left py-1 pr-3">Wave</th>
                  <th className="text-left py-1 pr-3">Rows</th>
                  <th className="text-left py-1 pr-3">By</th>
                  <th className="text-left py-1 pr-3">Date</th>
                  {canUpload && <th />}
                </tr>
              </thead>
              <tbody>
                {uploadLog.filter((u: UploadLogEntry) => u.report_type === 'quality_report').map((u: UploadLogEntry) => (
                  <tr key={u.id} className="border-b border-line/40">
                    <td className="py-1 pr-3 text-tx">{u.filename}</td>
                    <td className="py-1 pr-3 text-muted">{u.wave_label ?? '—'}</td>
                    <td className="py-1 pr-3 text-muted">{u.row_count}</td>
                    <td className="py-1 pr-3 text-muted">{u.uploader_name ?? '—'}</td>
                    <td className="py-1 pr-3 text-muted">{u.upload_date?.slice(0, 10)}</td>
                    {canUpload && (
                      <td className="py-1">
                        <button
                          onClick={() => delMut.mutate(u.upload_id)}
                          className="p-1 text-muted hover:text-critical transition-colors"
                          title="Delete upload"
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
        </div>
      )}

      {isLoading && (
        <div className="flex items-center gap-2 text-muted text-sm">
          <Loader2 size={14} className="animate-spin" /> Loading records…
        </div>
      )}

      {!isLoading && records.length === 0 && (
        <div className="card p-8 text-center text-muted text-sm">
          No quality records yet. Upload a QC results file to get started.
        </div>
      )}

      {records.length > 0 && (
        <>
          {/* KPI cards */}
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
            {[
              { label: 'Total Submitted', value: total, color: 'text-tx' },
              { label: 'Approved', value: approved, color: 'text-accent' },
              { label: 'Pending', value: pending, color: 'text-warning' },
              { label: 'Cancelled', value: cancelled, color: 'text-critical' },
              { label: 'Flagged (Duration)', value: flagged, color: 'text-critical' },
            ].map(k => (
              <div key={k.label} className="card p-4">
                <p className="label mb-1">{k.label}</p>
                <p className={`text-2xl font-bold font-display ${k.color}`}>{k.value}</p>
              </div>
            ))}
          </div>

          {/* Charts */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {/* Approval status pie */}
            <div className="card p-4">
              <p className="label mb-3">Approval Status</p>
              <ResponsiveContainer width="100%" height={220}>
                <PieChart>
                  <Pie data={pieData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={80} label>
                    {pieData.map((_, i) => <Cell key={i} fill={pieColors[i % pieColors.length]} />)}
                  </Pie>
                  <Tooltip {...TooltipStyle} />
                  <Legend wrapperStyle={{ color: C.muted, fontSize: 11 }} />
                </PieChart>
              </ResponsiveContainer>
            </div>

            {/* Errors by interviewer */}
            {errorData.length > 0 && (
              <div className="card p-4">
                <p className="label mb-3">Errors by Interviewer</p>
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart data={errorData} margin={{ left: -20 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke={C.line} />
                    <XAxis dataKey="name" tick={{ fill: C.muted, fontSize: 10 }} />
                    <YAxis tick={{ fill: C.muted, fontSize: 10 }} />
                    <Tooltip {...TooltipStyle} />
                    <Legend wrapperStyle={{ color: C.muted, fontSize: 11 }} />
                    <Bar dataKey="duration_flag" name="Duration Flag" fill={C.critical} radius={[2, 2, 0, 0]} />
                    <Bar dataKey="straight_lining" name="Straight Lining" fill={C.warning} radius={[2, 2, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>

          {/* Interviews per day */}
          {dayData.length > 1 && (
            <div className="card p-4">
              <p className="label mb-3">Interviews per Day</p>
              <ResponsiveContainer width="100%" height={200}>
                <LineChart data={dayData} margin={{ left: -20 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke={C.line} />
                  <XAxis dataKey="date" tick={{ fill: C.muted, fontSize: 10 }} />
                  <YAxis tick={{ fill: C.muted, fontSize: 10 }} />
                  <Tooltip {...TooltipStyle} />
                  <Line type="monotone" dataKey="count" stroke={C.accent} dot={false} strokeWidth={2} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Data table */}
          <div className="card p-4">
            <div className="flex items-center justify-between mb-3">
              <p className="label">Records (first 200)</p>
              <button onClick={handleExport} className="btn-ghost flex items-center gap-1 text-xs">
                <Download size={12} /> Export JSON
              </button>
            </div>
            <div className="overflow-x-auto max-h-80">
              <table className="w-full text-xs">
                <thead className="sticky top-0 bg-surface">
                  <tr className="border-b border-line text-muted">
                    {['Instance ID', 'Interviewer', 'Date', 'Duration', 'Dur Flag', 'SL', 'Status', 'Region'].map(h => (
                      <th key={h} className="text-left py-1 pr-3 whitespace-nowrap">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {records.slice(0, 200).map((r: QualityRecord) => (
                    <tr key={r.id} className="border-b border-line/30 hover:bg-surface2/50">
                      <td className="py-1 pr-3 text-tx font-mono">{r.instance_id ?? '—'}</td>
                      <td className="py-1 pr-3 text-muted">{r.interviewer_id ?? '—'}</td>
                      <td className="py-1 pr-3 text-muted">{r.interview_date ?? '—'}</td>
                      <td className="py-1 pr-3 text-muted">{r.duration_minutes?.toFixed(1) ?? '—'}</td>
                      <td className="py-1 pr-3">
                        {r.duration_flag === 'Flag'
                          ? <span className="badge-critical">Flag</span>
                          : <span className="text-muted">{r.duration_flag ?? '—'}</span>}
                      </td>
                      <td className="py-1 pr-3">
                        {r.straight_lining === 'Flag'
                          ? <span className="badge-warning">Flag</span>
                          : <span className="text-muted">{r.straight_lining ?? '—'}</span>}
                      </td>
                      <td className="py-1 pr-3">
                        {r.approval_status === 'Approved'
                          ? <span className="text-accent">{r.approval_status}</span>
                          : r.approval_status === 'Cancelled'
                          ? <span className="text-critical">{r.approval_status}</span>
                          : <span className="text-warning">{r.approval_status ?? '—'}</span>}
                      </td>
                      <td className="py-1 pr-3 text-muted">{r.region ?? '—'}</td>
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
