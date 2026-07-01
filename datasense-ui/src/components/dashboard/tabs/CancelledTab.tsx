import React, { useRef, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, ResponsiveContainer,
} from 'recharts'
import { Upload, Loader2, Trash2, Download } from 'lucide-react'
import { useAppStore } from '../../../store/appStore'
import {
  getCancelledRecords, getUploadLog, uploadCancelled, deleteUpload, downloadTemplate,
  type CancelledRecord, type UploadLogEntry,
} from '../../../api/dashboard'
import { FilterBar, useFilters, exportCSV, exportExcel, type FilterDef } from '../utils/tabUtils'

const C = {
  accent: '#00B5A3', critical: '#1B2A4A', muted: '#6B7280',
  surface: '#FFFFFF', surface2: '#F1F4F8', line: '#E2E6ED', tx: '#1B2A4A',
}
const TooltipStyle = {
  contentStyle: { backgroundColor: C.surface2, border: `1px solid ${C.line}`, borderRadius: 6, color: C.tx },
  itemStyle: { color: C.tx }, labelStyle: { color: C.muted },
}
const UPLOAD_ROLES = new Set(['qc_executive', 'operations_manager', 'qc_officer'])

interface Props { projectId: number }

export function CancelledTab({ projectId }: Props) {
  const { authUser, authToken } = useAppStore()
  const token = authToken ?? ''
  const qc = useQueryClient()
  const fileRef = useRef<HTMLInputElement>(null)
  const [waveLabel, setWaveLabel] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [isExporting, setIsExporting] = useState(false)

  const { data: records = [], isLoading } = useQuery({
    queryKey: ['dash-cancelled', projectId],
    queryFn: () => getCancelledRecords(projectId, token),
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
      return uploadCancelled(projectId, file, token, waveLabel || undefined)
    },
    onSuccess: () => {
      setFile(null); setWaveLabel('')
      qc.invalidateQueries({ queryKey: ['dash-cancelled', projectId] })
      qc.invalidateQueries({ queryKey: ['dash-upload-log', projectId] })
    },
  })
  const delMut = useMutation({
    mutationFn: (uid: string) => deleteUpload(uid, 'cancelled_interviews', token),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['dash-cancelled', projectId] })
      qc.invalidateQueries({ queryKey: ['dash-upload-log', projectId] })
    },
  })

  const canUpload = authUser && UPLOAD_ROLES.has(authUser.role)
  const cancelledLogs = uploadLog.filter((u: UploadLogEntry) => u.report_type === 'cancelled_interviews')

  const { filters, filtered, activeCount, setFilter, clearFilters, uniqueVals } = useFilters(
    records as Record<string, unknown>[],
    ['interviewer_id', 'region', 'interviewer_performance'],
  )

  const filterDefs: FilterDef[] = [
    { key: 'interviewer_id', label: 'Interviewer', type: 'select', options: uniqueVals['interviewer_id'] ?? [] },
    { key: 'region', label: 'Region', type: 'select', options: uniqueVals['region'] ?? [] },
    { key: 'interviewer_performance', label: 'Performance', type: 'select', options: uniqueVals['interviewer_performance'] ?? [] },
    { key: 'date_from', label: 'Date from', type: 'date' },
    { key: 'date_to', label: 'Date to', type: 'date' },
  ]

  const byRegion = (filtered as CancelledRecord[]).reduce<Record<string, number>>((acc, r) => {
    if (r.region) acc[r.region] = (acc[r.region] ?? 0) + 1
    return acc
  }, {})
  const byInterviewer = (filtered as CancelledRecord[]).reduce<Record<string, number>>((acc, r) => {
    if (r.interviewer_id) acc[r.interviewer_id] = (acc[r.interviewer_id] ?? 0) + 1
    return acc
  }, {})

  const regionData = Object.entries(byRegion).sort((a, b) => b[1] - a[1])
    .map(([name, count]) => ({ name, count }))
  const interviewerData = Object.entries(byInterviewer).sort((a, b) => b[1] - a[1])
    .map(([name, count]) => ({ name, count }))

  const handleCsvDownload = () => exportCSV(filtered as Record<string, unknown>[], `cancelled_${projectId}.csv`)
  const handleExcelDownload = async () => {
    setIsExporting(true)
    try {
      await exportExcel(projectId, 'cancelled', filtered as Record<string, unknown>[], {
        type: 'bar', data: regionData, x: 'name', y: 'count', title: 'Cancelled by Region',
      }, token, `cancelled_report_${projectId}.xlsx`)
    } finally { setIsExporting(false) }
  }

  return (
    <div className="space-y-6">
      {canUpload && (
        <div className="card p-4 space-y-3">
          <div className="flex items-center justify-between">
            <p className="label">Upload Cancelled Interviews (Excel)</p>
            <button onClick={() => downloadTemplate('cancelled', token)} className="btn-ghost flex items-center gap-1.5 text-xs">
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

      {cancelledLogs.length > 0 && (
        <div className="card p-4">
          <p className="label mb-2">Upload History</p>
          <table className="w-full text-xs">
            <thead><tr className="border-b border-line text-muted">
              {['File', 'Wave', 'Rows', 'Date', ''].map(h => <th key={h} className="text-left py-1 pr-3">{h}</th>)}
            </tr></thead>
            <tbody>
              {cancelledLogs.map((u: UploadLogEntry) => (
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
        <div className="card p-8 text-center text-muted text-sm">No cancelled interview records yet.</div>
      )}

      {records.length > 0 && (
        <>
          <FilterBar
            filters={filters} defs={filterDefs} onChange={setFilter} onClear={clearFilters}
            activeCount={activeCount} totalRows={records.length} filteredRows={filtered.length}
            onCsvDownload={handleCsvDownload} onExcelDownload={handleExcelDownload} isExporting={isExporting}
          />

          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            <div className="card p-4"><p className="label mb-1">Total Cancelled</p>
              <p className="text-2xl font-bold font-display text-critical">{filtered.length}</p></div>
            <div className="card p-4"><p className="label mb-1">Unique Interviewers</p>
              <p className="text-2xl font-bold font-display text-tx">
                {new Set((filtered as CancelledRecord[]).map(r => r.interviewer_id).filter(Boolean)).size}
              </p></div>
            <div className="card p-4"><p className="label mb-1">Regions</p>
              <p className="text-2xl font-bold font-display text-muted">{Object.keys(byRegion).length}</p></div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {regionData.length > 0 && (
              <div className="card p-4">
                <p className="label mb-3">Cancelled by Region</p>
                <ResponsiveContainer width="100%" height={200}>
                  <BarChart data={regionData} margin={{ left: -20 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke={C.line} />
                    <XAxis dataKey="name" tick={{ fill: C.muted, fontSize: 10 }} />
                    <YAxis tick={{ fill: C.muted, fontSize: 10 }} />
                    <Tooltip {...TooltipStyle} />
                    <Bar dataKey="count" name="Cancelled" fill={C.critical} radius={[2, 2, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
            {interviewerData.length > 0 && (
              <div className="card p-4">
                <p className="label mb-3">Cancelled by Interviewer</p>
                <ResponsiveContainer width="100%" height={200}>
                  <BarChart data={interviewerData} layout="vertical" margin={{ left: -10 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke={C.line} horizontal={false} />
                    <XAxis type="number" tick={{ fill: C.muted, fontSize: 10 }} />
                    <YAxis type="category" dataKey="name" width={70} tick={{ fill: C.muted, fontSize: 9 }} />
                    <Tooltip {...TooltipStyle} />
                    <Bar dataKey="count" name="Cancelled" fill={C.accent} radius={[0, 2, 2, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>

          <div className="card p-4">
            <p className="label mb-2">Records ({filtered.length})</p>
            <div className="overflow-x-auto max-h-80">
              <table className="w-full text-xs">
                <thead className="sticky top-0 bg-surface">
                  <tr className="border-b border-line text-muted">
                    {['Instance', 'Interviewer', 'Region', 'Date', 'Duration (min)', 'Performance'].map(h => (
                      <th key={h} className="text-left py-1 pr-3 whitespace-nowrap">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {(filtered as CancelledRecord[]).map(r => (
                    <tr key={r.id} className="border-b border-line/30 hover:bg-surface2/50">
                      <td className="py-1 pr-3 font-mono text-muted">{r.instance_id ?? '—'}</td>
                      <td className="py-1 pr-3 text-tx">{r.interviewer_id ?? '—'}</td>
                      <td className="py-1 pr-3 text-muted">{r.region ?? '—'}</td>
                      <td className="py-1 pr-3 text-muted">{r.interview_date ?? '—'}</td>
                      <td className="py-1 pr-3 text-muted">{r.interview_length?.toFixed(1) ?? '—'}</td>
                      <td className="py-1 pr-3 text-muted">{r.interviewer_performance ?? '—'}</td>
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
