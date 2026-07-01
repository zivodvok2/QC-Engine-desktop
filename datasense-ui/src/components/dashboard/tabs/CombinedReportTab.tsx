import React from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  PieChart, Pie, Cell, Tooltip, Legend,
  BarChart, Bar, XAxis, YAxis, CartesianGrid, ResponsiveContainer,
} from 'recharts'
import { Download, Loader2, FileCheck } from 'lucide-react'
import { useAppStore } from '../../../store/appStore'
import {
  getQualityRecords, getBackcheckRecords, getListenInRecords,
  downloadCombinedReport,
  type QualityRecord, type BackcheckRecord, type ListenInRecord,
} from '../../../api/dashboard'
import { getDashboardSummary, type ProjectSummary } from '../../../api/dashboard'
import { FilterBar, useFilters, type FilterDef } from '../utils/tabUtils'

const C = {
  accent: '#00B5A3', critical: '#1B2A4A', warning: '#00B5A3', info: '#1B2A4A',
  purple: '#1B2A4A', muted: '#6B7280', surface: '#FFFFFF', surface2: '#F1F4F8',
  line: '#E2E6ED', tx: '#1B2A4A',
}

const BACKCHECK_ERRORS: Record<string, string> = {
  error_01: 'Fraudulent', error_02: 'Diff respondent', error_03: 'Wrong quotas',
  error_04: 'Wrong usership', error_05: 'Wrong phone', error_06: 'Unattainable',
  error_07: 'Eng/Answerphone', error_08: 'Refused', error_09: "Doesn't remember",
  error_10: 'BC abandoned', error_11: 'Wrong mode', error_12: 'Voice perm.',
  error_13: 'Already part.',
}

const TooltipStyle = {
  contentStyle: { backgroundColor: C.surface2, border: `1px solid ${C.line}`, borderRadius: 6, color: C.tx },
  itemStyle: { color: C.tx },
  labelStyle: { color: C.muted },
}

interface Props { projectId: number }

export function CombinedReportTab({ projectId }: Props) {
  const { authToken } = useAppStore()
  const token = authToken ?? ''
  const [downloading, setDownloading] = React.useState(false)
  const [pptDownloading, setPptDownloading] = React.useState(false)

  const { data: summary = [] } = useQuery({
    queryKey: ['dash-summary'],
    queryFn: () => getDashboardSummary(token),
    enabled: !!token,
  })
  const project: ProjectSummary | undefined = (summary as ProjectSummary[]).find(p => p.id === projectId)

  const { data: quality = [], isLoading: qLoading } = useQuery({
    queryKey: ['dash-quality', projectId],
    queryFn: () => getQualityRecords(projectId, token),
    enabled: !!token,
  })

  const { data: backcheck = [], isLoading: bLoading } = useQuery({
    queryKey: ['dash-backcheck', projectId],
    queryFn: () => getBackcheckRecords(projectId, token),
    enabled: !!token,
  })

  const { data: listenin = [], isLoading: lLoading } = useQuery({
    queryKey: ['dash-listenin', projectId],
    queryFn: () => getListenInRecords(projectId, token),
    enabled: !!token,
  })

  const isLoading = qLoading || bLoading || lLoading

  // ── Filters on quality records ─────────────────────────────────────────────────
  const { filters, filtered: filteredQ, activeCount, setFilter, clearFilters, uniqueVals } = useFilters(
    quality as Record<string, unknown>[],
    ['interviewer_id', 'region', 'approval_status', 'duration_flag'],
  )

  const filterDefs: FilterDef[] = [
    { key: 'interviewer_id', label: 'Interviewer', type: 'select', options: uniqueVals['interviewer_id'] ?? [] },
    { key: 'region', label: 'Region', type: 'select', options: uniqueVals['region'] ?? [] },
    { key: 'approval_status', label: 'Status', type: 'select', options: uniqueVals['approval_status'] ?? [] },
    { key: 'duration_flag', label: 'Dur. Flag', type: 'select', options: uniqueVals['duration_flag'] ?? [] },
    { key: 'date_from', label: 'Date from', type: 'date' },
    { key: 'date_to', label: 'Date to', type: 'date' },
  ]

  // ── QC metrics ────────────────────────────────────────────────────────────────
  const q = filteredQ as QualityRecord[]
  const total = q.length
  const approved = q.filter(r => r.approval_status === 'Approved').length
  const pending = q.filter(r => r.approval_status === 'Pending').length
  const cancelled = q.filter(r => r.approval_status === 'Cancelled').length
  const durFlags = q.filter(r => r.duration_flag === 'Flag').length
  const slFlags = q.filter(r => r.straight_lining === 'Flag').length

  const approvalPie = [
    { name: 'Approved', value: approved },
    { name: 'Pending', value: pending },
    { name: 'Cancelled', value: cancelled },
  ].filter(d => d.value > 0)
  const pieColors = [C.accent, C.warning, C.critical]

  // Flag breakdown bar
  const flagBreakdown = [
    { name: 'Duration Flag', count: durFlags, fill: C.critical },
    { name: 'Straight-lining', count: slFlags, fill: C.warning },
  ]

  // Per-interviewer summary
  const byItv: Record<string, { interviews: number; dur: number; sl: number; approved: number }> = {}
  q.forEach(r => {
    const id = r.interviewer_id ?? 'Unknown'
    if (!byItv[id]) byItv[id] = { interviews: 0, dur: 0, sl: 0, approved: 0 }
    byItv[id].interviews++
    if (r.duration_flag === 'Flag') byItv[id].dur++
    if (r.straight_lining === 'Flag') byItv[id].sl++
    if (r.approval_status === 'Approved') byItv[id].approved++
  })
  const itvData = Object.entries(byItv)
    .map(([name, v]) => ({ name, ...v, flags: v.dur + v.sl }))
    .sort((a, b) => b.flags - a.flags)
    .slice(0, 15)

  // ── Backcheck metrics ─────────────────────────────────────────────────────────
  const bc = backcheck as BackcheckRecord[]
  const errorTotals: Record<string, number> = {}
  bc.forEach(r => {
    for (let i = 1; i <= 13; i++) {
      const k = `error_${String(i).padStart(2, '0')}` as keyof BackcheckRecord
      const v = r[k] as number
      if (v > 0) errorTotals[k] = (errorTotals[k] ?? 0) + v
    }
  })
  const topErrors = Object.entries(errorTotals)
    .map(([k, v]) => ({ name: BACKCHECK_ERRORS[k] ?? k, count: v }))
    .sort((a, b) => b.count - a.count)
    .slice(0, 5)

  // ── Listen-in metrics ─────────────────────────────────────────────────────────
  const li = listenin as ListenInRecord[]
  const liPass = li.filter(r => r.result === 'Pass').length
  const liFail = li.filter(r => r.result === 'Fail').length
  const liPartial = li.filter(r => r.result === 'Partial').length
  const liPie = [
    { name: 'Pass', value: liPass },
    { name: 'Partial', value: liPartial },
    { name: 'Fail', value: liFail },
  ].filter(d => d.value > 0)
  const liColors = [C.accent, C.warning, C.critical]

  const handleDownload = async () => {
    setDownloading(true)
    try {
      await downloadCombinedReport(projectId, token, project?.name ?? 'project')
    } finally {
      setDownloading(false)
    }
  }

  const handlePptDownload = async () => {
    setPptDownloading(true)
    try {
      const res = await fetch(`/api/dashboard/projects/${projectId}/ppt`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!res.ok) throw new Error('PPT generation failed')
      const blob = await res.blob()
      const a = document.createElement('a')
      a.href = URL.createObjectURL(blob)
      a.download = `${project?.name ?? 'project'}_QC_Report.pptx`
      a.click()
      URL.revokeObjectURL(a.href)
    } finally {
      setPptDownloading(false)
    }
  }

  return (
    <div className="space-y-6">
      {/* Header with download */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h3 className="text-sm font-display font-bold text-tx">Combined Project Report</h3>
          <p className="text-xs text-muted mt-0.5">Aggregates QC results, back-check, and listen-in into one view</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handlePptDownload}
            disabled={pptDownloading}
            className="btn-ghost flex items-center gap-2 text-sm"
          >
            {pptDownloading ? <Loader2 size={14} className="animate-spin" /> : <FileCheck size={14} />}
            PPT Report
          </button>
          <button
            onClick={handleDownload}
            disabled={downloading}
            className="btn-primary flex items-center gap-2"
          >
            {downloading ? <Loader2 size={14} className="animate-spin" /> : <Download size={14} />}
            Download Excel
          </button>
        </div>
      </div>

      {isLoading && (
        <div className="flex items-center gap-2 text-muted text-sm">
          <Loader2 size={14} className="animate-spin" /> Loading data…
        </div>
      )}

      {!isLoading && total === 0 && bc.length === 0 && li.length === 0 && (
        <div className="card p-8 text-center text-muted text-sm space-y-2">
          <FileCheck size={24} className="mx-auto text-muted/50" />
          <p>No data yet for this project.</p>
          <p className="text-xs">Save QC results from the Quality Report tab, then upload back-check and listen-in files.</p>
        </div>
      )}

      {(quality as QualityRecord[]).length > 0 && (
        <FilterBar
          filters={filters} defs={filterDefs} onChange={setFilter} onClear={clearFilters}
          activeCount={activeCount} totalRows={(quality as QualityRecord[]).length} filteredRows={filteredQ.length}
          onCsvDownload={() => {}}
        />
      )}

      {/* ── Top-level KPI summary ── */}
      {(total > 0 || bc.length > 0 || li.length > 0) && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div className="card p-4">
            <p className="label mb-1">QC Records</p>
            <p className="text-2xl font-bold font-display text-tx">{total}</p>
            <p className="text-xs text-accent mt-0.5">{approved} approved</p>
          </div>
          <div className="card p-4">
            <p className="label mb-1">QC Flags</p>
            <p className={`text-2xl font-bold font-display ${durFlags + slFlags > 0 ? 'text-critical' : 'text-muted'}`}>
              {durFlags + slFlags}
            </p>
            <p className="text-xs text-muted mt-0.5">{durFlags} dur · {slFlags} SL</p>
          </div>
          <div className="card p-4">
            <p className="label mb-1">Back-check</p>
            <p className="text-2xl font-bold font-display text-tx">{bc.length}</p>
            <p className="text-xs text-muted mt-0.5">
              {Object.values(errorTotals).reduce((a, b) => a + b, 0)} errors
            </p>
          </div>
          <div className="card p-4">
            <p className="label mb-1">Listen-in</p>
            <p className="text-2xl font-bold font-display text-tx">{li.length}</p>
            <p className="text-xs text-muted mt-0.5">{liPass} pass · {liFail} fail</p>
          </div>
        </div>
      )}

      {/* ── QC section ── */}
      {total > 0 && (
        <div className="space-y-4">
          <div className="flex items-center gap-2">
            <div className="h-px flex-1 bg-line" />
            <span className="text-xs text-muted uppercase tracking-wider px-2">Quality Report</span>
            <div className="h-px flex-1 bg-line" />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {/* Approval pie */}
            <div className="card p-4">
              <p className="label mb-3">Approval Status</p>
              <ResponsiveContainer width="100%" height={200}>
                <PieChart>
                  <Pie data={approvalPie} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={75} label>
                    {approvalPie.map((_, i) => <Cell key={i} fill={pieColors[i % pieColors.length]} />)}
                  </Pie>
                  <Tooltip {...TooltipStyle} />
                  <Legend wrapperStyle={{ color: C.muted, fontSize: 11 }} />
                </PieChart>
              </ResponsiveContainer>
            </div>

            {/* Flags */}
            <div className="card p-4">
              <p className="label mb-3">QC Flag Breakdown</p>
              <div className="space-y-3 pt-4">
                {flagBreakdown.map(f => (
                  <div key={f.name}>
                    <div className="flex justify-between text-xs mb-1">
                      <span className="text-muted">{f.name}</span>
                      <span className="text-tx">{f.count} / {total} ({total > 0 ? Math.round(f.count / total * 100) : 0}%)</span>
                    </div>
                    <div className="h-2 bg-surface2 rounded-full overflow-hidden">
                      <div
                        className="h-full rounded-full transition-all"
                        style={{ width: `${total > 0 ? (f.count / total) * 100 : 0}%`, backgroundColor: f.fill }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Interviewer table */}
          {itvData.length > 0 && (
            <div className="card p-4">
              <p className="label mb-3">QC Results by Interviewer</p>
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-line text-muted">
                      {['Interviewer', 'Interviews', 'Approved', 'Dur Flags', 'SL Flags', 'Total Flags'].map(h => (
                        <th key={h} className="text-left py-1.5 pr-4">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {itvData.map(r => (
                      <tr key={r.name} className="border-b border-line/30 hover:bg-surface2/50">
                        <td className="py-1.5 pr-4 font-mono text-accent">{r.name}</td>
                        <td className="py-1.5 pr-4 text-tx">{r.interviews}</td>
                        <td className="py-1.5 pr-4 text-accent">{r.approved}</td>
                        <td className="py-1.5 pr-4 text-critical">{r.dur}</td>
                        <td className="py-1.5 pr-4 text-warning">{r.sl}</td>
                        <td className="py-1.5 pr-4">
                          {r.flags > 0
                            ? <span className="text-critical font-bold">{r.flags}</span>
                            : <span className="text-muted">0</span>}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── Back-check section ── */}
      {bc.length > 0 && (
        <div className="space-y-4">
          <div className="flex items-center gap-2">
            <div className="h-px flex-1 bg-line" />
            <span className="text-xs text-muted uppercase tracking-wider px-2">Back-check</span>
            <div className="h-px flex-1 bg-line" />
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            <div className="card p-4">
              <p className="label mb-1">BC Records</p>
              <p className="text-2xl font-bold font-display text-tx">{bc.length}</p>
            </div>
            <div className="card p-4">
              <p className="label mb-1">Total Errors</p>
              <p className="text-2xl font-bold font-display text-critical">
                {Object.values(errorTotals).reduce((a, b) => a + b, 0)}
              </p>
            </div>
            <div className="card p-4">
              <p className="label mb-1">Error Types</p>
              <p className="text-2xl font-bold font-display text-warning">{topErrors.length}</p>
            </div>
          </div>

          {topErrors.length > 0 && (
            <div className="card p-4">
              <p className="label mb-3">Top BC Errors</p>
              <ResponsiveContainer width="100%" height={180}>
                <BarChart data={topErrors} layout="vertical" margin={{ left: 10 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke={C.line} horizontal={false} />
                  <XAxis type="number" tick={{ fill: C.muted, fontSize: 10 }} />
                  <YAxis type="category" dataKey="name" width={120} tick={{ fill: C.muted, fontSize: 10 }} />
                  <Tooltip {...TooltipStyle} />
                  <Bar dataKey="count" fill={C.critical} radius={[0, 2, 2, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      )}

      {/* ── Listen-in section ── */}
      {li.length > 0 && (
        <div className="space-y-4">
          <div className="flex items-center gap-2">
            <div className="h-px flex-1 bg-line" />
            <span className="text-xs text-muted uppercase tracking-wider px-2">Listen-in</span>
            <div className="h-px flex-1 bg-line" />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="card p-4">
              <p className="label mb-3">Session Results</p>
              <ResponsiveContainer width="100%" height={180}>
                <PieChart>
                  <Pie data={liPie} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={65} label>
                    {liPie.map((_, i) => <Cell key={i} fill={liColors[i % liColors.length]} />)}
                  </Pie>
                  <Tooltip {...TooltipStyle} />
                  <Legend wrapperStyle={{ color: C.muted, fontSize: 11 }} />
                </PieChart>
              </ResponsiveContainer>
            </div>
            <div className="card p-4 space-y-3 pt-6">
              {[
                { label: 'Total Sessions', value: li.length, color: 'text-tx' },
                { label: 'Pass', value: liPass, color: 'text-accent' },
                { label: 'Partial', value: liPartial, color: 'text-warning' },
                { label: 'Fail', value: liFail, color: 'text-critical' },
              ].map(k => (
                <div key={k.label} className="flex justify-between text-sm">
                  <span className="text-muted">{k.label}</span>
                  <span className={`font-bold ${k.color}`}>{k.value}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
