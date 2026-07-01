import React, { useRef, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, ResponsiveContainer, Legend,
} from 'recharts'
import { Upload, Loader2, Trash2, Download } from 'lucide-react'
import { useAppStore } from '../../../store/appStore'
import {
  getPerformanceRecords, getUploadLog, uploadPerformance, deleteUpload, downloadTemplate,
  type PerformanceRecord, type UploadLogEntry,
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

export function PerformanceTab({ projectId }: Props) {
  const { authUser, authToken } = useAppStore()
  const token = authToken ?? ''
  const qc = useQueryClient()
  const fileRef = useRef<HTMLInputElement>(null)
  const [waveLabel, setWaveLabel] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [isExporting, setIsExporting] = useState(false)
  const activeBarRef = useRef<string | null>(null)

  const { data: records = [], isLoading } = useQuery({
    queryKey: ['dash-performance', projectId],
    queryFn: () => getPerformanceRecords(projectId, token),
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
      return uploadPerformance(projectId, file, token, waveLabel || undefined)
    },
    onSuccess: () => {
      setFile(null); setWaveLabel('')
      qc.invalidateQueries({ queryKey: ['dash-performance', projectId] })
      qc.invalidateQueries({ queryKey: ['dash-upload-log', projectId] })
      qc.invalidateQueries({ queryKey: ['dash-summary'] })
    },
  })
  const delMut = useMutation({
    mutationFn: (uid: string) => deleteUpload(uid, 'performance', token),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['dash-performance', projectId] })
      qc.invalidateQueries({ queryKey: ['dash-upload-log', projectId] })
    },
  })

  const canUpload = authUser && UPLOAD_ROLES.has(authUser.role)
  const perfLogs = uploadLog.filter((u: UploadLogEntry) => u.report_type === 'performance')

  const { filters, filtered, activeCount, setFilter, clearFilters, uniqueVals } = useFilters(
    records as Record<string, unknown>[],
    ['interviewer_id', 'region'],
  )

  const filterDefs: FilterDef[] = [
    { key: 'interviewer_id', label: 'Interviewer', type: 'select', options: uniqueVals['interviewer_id'] ?? [] },
    { key: 'region', label: 'Region', type: 'select', options: uniqueVals['region'] ?? [] },
  ]

  const totalCompletes = filtered.reduce((s, r) => s + ((r as PerformanceRecord).interview_completes ?? 0), 0)
  const totalAcc = filtered.reduce((s, r) => s + ((r as PerformanceRecord).accompaniments ?? 0), 0)
  const totalBC = filtered.reduce((s, r) => s + ((r as PerformanceRecord).backcheck_completed ?? 0), 0)
  const totalCancelled = filtered.reduce((s, r) => s + ((r as PerformanceRecord).cancelled_interviews ?? 0), 0)

  // Stacked chart: all interviewers, Completes vs Flags (cancelled)
  const chartData = (filtered as PerformanceRecord[])
    .filter(r => r.interviewer_id)
    .sort((a, b) => ((b.interview_completes ?? 0) + (b.cancelled_interviews ?? 0)) -
      ((a.interview_completes ?? 0) + (a.cancelled_interviews ?? 0)))
    .map(r => ({
      name: r.interviewer_id,
      Completes: r.interview_completes ?? 0,
      Flags: (r.cancelled_interviews ?? 0) + (r.backcheck_completed ?? 0),
      Accompaniments: r.accompaniments ?? 0,
    }))

  const chartH = Math.max(220, chartData.length * 28)

  const handleCsvDownload = () => exportCSV(filtered as Record<string, unknown>[], `performance_${projectId}.csv`)
  const handleExcelDownload = async () => {
    setIsExporting(true)
    try {
      await exportExcel(projectId, 'performance', filtered as Record<string, unknown>[], {
        type: 'bar_stacked', data: chartData, title: 'Performance by Interviewer',
        series: ['Completes', 'Flags', 'Accompaniments'],
      }, token, `performance_report_${projectId}.xlsx`)
    } finally { setIsExporting(false) }
  }

  return (
    <div className="space-y-6">
      {canUpload && (
        <div className="card p-4 space-y-3">
          <div className="flex items-center justify-between">
            <p className="label">Upload Performance Data (Excel)</p>
            <button onClick={() => downloadTemplate('performance', token)} className="btn-ghost flex items-center gap-1.5 text-xs">
              <Download size={12} /> Download template
            </button>
          </div>
          <p className="text-xs text-muted">Accepts iField performance export (with 2 header rows) or the Servallab template.</p>
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

      {perfLogs.length > 0 && (
        <div className="card p-4">
          <p className="label mb-2">Upload History</p>
          <table className="w-full text-xs">
            <thead><tr className="border-b border-line text-muted">
              {['File', 'Wave', 'Rows', 'Date', ''].map(h => <th key={h} className="text-left py-1 pr-3">{h}</th>)}
            </tr></thead>
            <tbody>
              {perfLogs.map((u: UploadLogEntry) => (
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
        <div className="card p-8 text-center text-muted text-sm">No performance records yet. Upload a performance Excel file.</div>
      )}

      {records.length > 0 && (
        <>
          <FilterBar
            filters={filters} defs={filterDefs} onChange={setFilter} onClear={clearFilters}
            activeCount={activeCount} totalRows={records.length} filteredRows={filtered.length}
            onCsvDownload={handleCsvDownload} onExcelDownload={handleExcelDownload} isExporting={isExporting}
          />

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {[
              { label: 'Total Completes', value: totalCompletes, color: 'text-accent' },
              { label: 'Accompaniments', value: totalAcc, color: 'text-tx' },
              { label: 'Backchecks Done', value: totalBC, color: 'text-tx' },
              { label: 'Cancelled / Flagged', value: totalCancelled, color: 'text-critical' },
            ].map(k => (
              <div key={k.label} className="card p-4">
                <p className="label mb-1">{k.label}</p>
                <p className={`text-2xl font-bold font-display ${k.color}`}>{k.value}</p>
              </div>
            ))}
          </div>

          {chartData.length > 0 && (
            <div className="card p-4">
              <p className="label mb-3">Completes vs Flags — all interviewers</p>
              <div style={{ height: chartH }}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={chartData} layout="vertical" margin={{ left: -10, right: 10 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke={C.line} horizontal={false} />
                    <XAxis type="number" tick={{ fill: C.muted, fontSize: 10 }} />
                    <YAxis type="category" dataKey="name" width={72} tick={{ fill: C.muted, fontSize: 9 }} />
                    <Tooltip
                      cursor={false}
                      content={({ active, payload, label }) => {
                        if (!active || !payload?.length) return null
                        const key = activeBarRef.current
                        const item = key ? payload.find((p: any) => p.dataKey === key) : payload[0]
                        if (!item) return null
                        return (
                          <div style={TooltipStyle.contentStyle}>
                            <p style={{ ...TooltipStyle.labelStyle, fontSize: 10, marginBottom: 2 }}>{label}</p>
                            <p style={{ color: item.fill ?? item.color, fontSize: 12, fontWeight: 600 }}>
                              {item.name}: {item.value}
                            </p>
                          </div>
                        )
                      }}
                    />
                    <Legend verticalAlign="top" wrapperStyle={{ fontSize: 11, paddingBottom: 8 }} />
                    <Bar dataKey="Completes" stackId="a" fill={C.accent} radius={[0, 0, 0, 0]}
                      onMouseEnter={() => { activeBarRef.current = 'Completes' }} />
                    <Bar dataKey="Accompaniments" stackId="a" fill="#3B5A9A" radius={[0, 0, 0, 0]}
                      onMouseEnter={() => { activeBarRef.current = 'Accompaniments' }} />
                    <Bar dataKey="Flags" stackId="a" fill="#EF4444" radius={[0, 2, 2, 0]}
                      onMouseEnter={() => { activeBarRef.current = 'Flags' }} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}

          <div className="card p-4">
            <p className="label mb-2">Records ({filtered.length})</p>
            <div className="overflow-x-auto max-h-80">
              <table className="w-full text-xs">
                <thead className="sticky top-0 bg-surface">
                  <tr className="border-b border-line text-muted">
                    {['Interviewer', 'Region', 'Completes', 'Accompaniments', 'BC Done', 'Cancelled', 'First', 'Last'].map(h => (
                      <th key={h} className="text-left py-1 pr-3 whitespace-nowrap">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {(filtered as PerformanceRecord[]).map(r => (
                    <tr key={r.id} className="border-b border-line/30 hover:bg-surface2/50">
                      <td className="py-1 pr-3 font-mono text-tx">{r.interviewer_id ?? '—'}</td>
                      <td className="py-1 pr-3 text-muted">{r.region ?? '—'}</td>
                      <td className="py-1 pr-3 text-accent font-medium">{r.interview_completes}</td>
                      <td className="py-1 pr-3 text-muted">{r.accompaniments}</td>
                      <td className="py-1 pr-3 text-muted">{r.backcheck_completed}</td>
                      <td className={`py-1 pr-3 ${(r.cancelled_interviews ?? 0) > 0 ? 'text-critical font-medium' : 'text-muted'}`}>
                        {r.cancelled_interviews ?? 0}
                      </td>
                      <td className="py-1 pr-3 text-muted">{r.first_interview ?? '—'}</td>
                      <td className="py-1 pr-3 text-muted">{r.last_interview ?? '—'}</td>
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
