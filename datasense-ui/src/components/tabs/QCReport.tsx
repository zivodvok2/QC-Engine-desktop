import React, { useEffect, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { Download, ChevronDown, ChevronUp, Info, XCircle, Activity, Sparkles, FileText, Database, ChevronRight, Check, Filter, Search, Users, Loader2 } from 'lucide-react'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell, PieChart, Pie, Legend } from 'recharts'
import { useAppStore } from '../../store/appStore'
import { downloadReport } from '../../api/qc'
import { explainFlags, generateQCSummary } from '../../api/ai'
import { getProjects, createProject, saveQCResults } from '../../api/projects'
import { getUploadLog, uploadBackcheck, uploadListenIn, uploadPerformance, uploadCancelled } from '../../api/dashboard'
import { computeRisk } from '../../api/interviewers'
import type { RiskRow } from '../../api/interviewers'
import type { CheckResult } from '../../types'
import type { Project } from '../../api/projects'

const SEV_ORDER: Record<string, number> = { critical: 0, warning: 1, info: 2 }
const SEV_COLORS: Record<string, string> = { critical: '#1B2A4A', warning: '#00B5A3', info: '#00B5A3' }
const RISK_COLORS: Record<string, string> = { HIGH: '#1B2A4A', MEDIUM: '#00B5A3', LOW: '#00B5A3' }
const CHART_TOOLTIP_STYLE = {
  contentStyle: { background: '#FFFFFF', border: '1px solid #E2E6ED', borderRadius: 6 },
  labelStyle: { color: '#1B2A4A' },
  itemStyle: { color: '#00B5A3' },
}

function MetricCard({ label, value, color }: { label: string; value: number | string; color?: string }) {
  return (
    <div className="card2 px-4 py-3 space-y-1">
      <p className="label">{label}</p>
      <p className={`text-2xl font-display font-extrabold ${color ?? 'text-tx'}`}>{value}</p>
    </div>
  )
}

function CheckAccordion({
  check,
  totalFlags,
  totalRows,
  groqApiKey,
  model,
}: {
  check: CheckResult
  totalFlags: number
  totalRows: number
  groqApiKey: string
  model: string
}) {
  const [open, setOpen] = useState(false)
  const [page, setPage] = useState(0)
  const [explanation, setExplanation] = useState('')
  const PAGE_SIZE = 25
  const pct = totalFlags > 0 ? ((check.flag_count / totalFlags) * 100).toFixed(1) : '0'
  const rows = check.flagged_rows.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE)
  const totalPages = Math.ceil(check.flagged_rows.length / PAGE_SIZE)
  const cols = check.flagged_rows[0] ? Object.keys(check.flagged_rows[0]).filter((k) => !k.startsWith('_')) : []

  const sev = check.severity
  const badgeClass = sev === 'critical' ? 'badge-critical' : sev === 'warning' ? 'badge-warning' : 'badge-info'
  const rowHighlight = sev === 'critical' ? 'bg-critical/5 border-l-2 border-critical/30' : sev === 'warning' ? 'bg-warning/5 border-l-2 border-warning/20' : ''

  const explainMutation = useMutation({
    mutationFn: () =>
      explainFlags(
        check.check_name,
        check.severity,
        check.flag_count,
        totalRows,
        check.flagged_rows.slice(0, 5),
        {},
        groqApiKey,
        model,
      ),
    onSuccess: (data) => setExplanation(data.explanation),
  })

  return (
    <div className={`card border-line ${rowHighlight}`}>
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center gap-3 px-4 py-3 text-left"
      >
        <span className={badgeClass}>{sev}</span>
        <span className="text-sm font-medium text-tx flex-1">{check.check_name.replace(/_/g, ' ')}</span>
        <div className="flex items-center gap-2 mr-2">
          <div className="w-20 h-1.5 bg-surface2 rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full ${sev === 'critical' ? 'bg-critical' : sev === 'warning' ? 'bg-warning' : 'bg-info'}`}
              style={{ width: `${Math.min(parseFloat(pct), 100)}%` }}
            />
          </div>
          <span className="text-xs text-muted whitespace-nowrap">{check.flag_count} flags · {pct}%</span>
        </div>
        {open ? <ChevronUp size={14} className="text-muted" /> : <ChevronDown size={14} className="text-muted" />}
      </button>

      {open && check.flag_count > 0 && (
        <div className="border-t border-line px-4 pb-4 pt-3 space-y-3">
          {/* AI Explain button */}
          {groqApiKey && (
            <div className="space-y-2">
              <button
                onClick={() => explainMutation.mutate()}
                disabled={explainMutation.isPending}
                className="btn-ghost flex items-center gap-1.5 text-xs"
              >
                <Sparkles size={11} className="text-accent" />
                {explainMutation.isPending ? 'Explaining…' : 'Explain with AI'}
              </button>
              {explainMutation.isError && (
                <p className="text-xs text-critical">{(explainMutation.error as Error).message}</p>
              )}
              {explanation && (
                <div className="p-3 rounded-lg bg-accent/5 border border-accent/20 text-xs text-tx leading-relaxed whitespace-pre-wrap">
                  {explanation}
                </div>
              )}
            </div>
          )}

          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-line">
                  {cols.map((c) => (
                    <th key={c} className="text-left py-1.5 px-2 text-muted font-normal whitespace-nowrap">{c}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((row, i) => (
                  <tr key={i} className={`border-b border-line/50 hover:opacity-90 transition-colors ${
                    sev === 'critical' ? 'bg-critical/5' : sev === 'warning' ? 'bg-warning/5' : 'bg-info/5'
                  }`}>
                    {cols.map((c) => (
                      <td key={c} className="py-1.5 px-2 text-tx whitespace-nowrap">
                        {String(row[c] ?? '')}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {totalPages > 1 && (
            <div className="flex items-center gap-2 text-xs text-muted">
              <button disabled={page === 0} onClick={() => setPage((p) => p - 1)} className="btn-ghost px-2 py-0.5 disabled:opacity-30">‹</button>
              <span>Page {page + 1} / {totalPages}</span>
              <button disabled={page >= totalPages - 1} onClick={() => setPage((p) => p + 1)} className="btn-ghost px-2 py-0.5 disabled:opacity-30">›</button>
            </div>
          )}
        </div>
      )}

      {open && check.flag_count === 0 && (
        <p className="border-t border-line px-4 py-3 text-xs text-muted">No rows flagged by this check.</p>
      )}
    </div>
  )
}

function useInterviewerRiskRows() {
  const { results, jobId, fileId, jobStatus, config, itvTabState } = useAppStore()

  const interviewerCol = (
    [
      itvTabState.intCol,
      config.interviewer_duration_check.enabled ? config.interviewer_duration_check.interviewer_column : '',
      config.fabrication_check.enabled ? (config.fabrication_check.interviewer_column ?? '') : '',
      config.interviewer_productivity_check.enabled ? config.interviewer_productivity_check.interviewer_column : '',
      config.straightlining.enabled ? (config.straightlining.interviewer_column ?? '') : '',
    ].find((c) => !!c) ?? ''
  )

  const durCol =
    (config.interviewer_duration_check.enabled && config.interviewer_duration_check.duration_column) ||
    (config.interview_duration.enabled && config.interview_duration.column) ||
    undefined

  const dateCol =
    (config.interviewer_productivity_check.enabled && config.interviewer_productivity_check.date_column) ||
    undefined

  const hasItvRows = itvTabState.rows.length > 0

  const riskQuery = useQuery({
    queryKey: ['qr-risk', jobId, interviewerCol],
    queryFn: () =>
      computeRisk(
        fileId!,
        jobId!,
        interviewerCol,
        itvTabState.redThr || 60,
        itvTabState.amberThr || 30,
        itvTabState.supervisorCol || undefined,
        dateCol || undefined,
        durCol || undefined,
      ),
    enabled: !!jobId && !!fileId && !!interviewerCol && jobStatus === 'complete' && !hasItvRows,
    retry: false,
    staleTime: Infinity,
  })

  const rows: RiskRow[] = hasItvRows
    ? (itvTabState.rows as RiskRow[])
    : (riskQuery.data?.rows ?? [])
  const colName = hasItvRows
    ? (itvTabState.intColName || itvTabState.intCol)
    : (riskQuery.data?.interviewer_column ?? interviewerCol)

  return {
    results,
    interviewerCol,
    hasItvRows,
    rows,
    colName,
    isLoading: riskQuery.isPending && !hasItvRows,
    isError: riskQuery.isError && !hasItvRows,
  }
}

function InterviewerRiskPanel() {
  const { setItvTabState } = useAppStore()
  const [open, setOpen] = useState(true)
  const [promptCol, setPromptCol] = useState('')

  const { results, interviewerCol, hasItvRows, rows, colName, isLoading, isError } = useInterviewerRiskRows()

  if (!results) return null

  if (!interviewerCol && !hasItvRows) {
    return (
      <div className="card border-line px-4 py-3 flex flex-wrap items-center gap-3">
        <Users size={14} className="text-muted shrink-0" />
        <span className="text-xs text-muted flex-1 min-w-0">
          Enter the interviewer column name to auto-compute risk scores inline
        </span>
        <input
          type="text"
          value={promptCol}
          onChange={e => setPromptCol(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter' && promptCol.trim()) setItvTabState({ intCol: promptCol.trim() }) }}
          placeholder="e.g. interviewer_id"
          className="w-36 text-xs"
        />
        <button
          onClick={() => { if (promptCol.trim()) setItvTabState({ intCol: promptCol.trim() }) }}
          disabled={!promptCol.trim()}
          className="btn-ghost text-xs shrink-0"
        >
          Analyze →
        </button>
      </div>
    )
  }

  if (isError) return null

  const high = rows.filter((r) => r.risk_level === 'HIGH').length
  const medium = rows.filter((r) => r.risk_level === 'MEDIUM').length
  const low = rows.filter((r) => r.risk_level === 'LOW').length
  const top = rows.slice(0, 10)
  const showDur = top.some((r) => r.avg_duration != null)
  const showSup = top.some((r) => r.supervisor && r.supervisor !== 'None' && r.supervisor !== 'null')

  return (
    <div className="card border-line">
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-surface2 transition-colors"
      >
        <Users size={14} className="text-accent" />
        <span className="text-sm font-medium text-tx flex-1">Interviewer Risk Summary</span>
        {isLoading && <Loader2 size={12} className="text-muted animate-spin" />}
        {!isLoading && rows.length > 0 && (
          <div className="flex items-center gap-2 mr-2">
            {high > 0 && (
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-critical/10 text-critical border border-critical/30">
                {high} HIGH
              </span>
            )}
            {medium > 0 && (
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-warning/10 text-warning border border-warning/30">
                {medium} MED
              </span>
            )}
            {low > 0 && (
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-accent/10 text-accent border border-accent/30">
                {low} LOW
              </span>
            )}
          </div>
        )}
        {open ? <ChevronUp size={14} className="text-muted" /> : <ChevronDown size={14} className="text-muted" />}
      </button>

      {open && (
        <div className="border-t border-line px-4 pb-4 pt-3">
          {isLoading && (
            <div className="flex items-center justify-center gap-2 py-6 text-xs text-muted">
              <Loader2 size={12} className="animate-spin" />
              Computing interviewer risk…
            </div>
          )}
          {!isLoading && rows.length === 0 && (
            <p className="text-xs text-muted py-2">
              {interviewerCol
                ? `No data found in column "${interviewerCol}". Run interviewer checks to populate this panel.`
                : 'Enable an interviewer check (duration, fabrication, or productivity) and set the interviewer column to auto-populate this panel.'}
            </p>
          )}
          {!isLoading && top.length > 0 && (
            <>
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-line">
                      <th className="text-left py-1.5 px-2 text-muted font-normal whitespace-nowrap">
                        {colName || 'Interviewer'}
                      </th>
                      {showSup && (
                        <th className="text-left py-1.5 px-2 text-muted font-normal whitespace-nowrap">Supervisor</th>
                      )}
                      <th className="text-center py-1.5 px-2 text-muted font-normal">Risk</th>
                      <th className="text-center py-1.5 px-2 text-muted font-normal">Score</th>
                      <th className="text-center py-1.5 px-2 text-muted font-normal">Interviews</th>
                      <th className="text-center py-1.5 px-2 text-muted font-normal">Flags</th>
                      <th className="text-center py-1.5 px-2 text-muted font-normal">Flag %</th>
                      <th className="text-center py-1.5 px-2 text-muted font-normal whitespace-nowrap">Fabrication</th>
                      <th className="text-center py-1.5 px-2 text-muted font-normal whitespace-nowrap">Duration</th>
                      <th className="text-center py-1.5 px-2 text-muted font-normal whitespace-nowrap">S-lining</th>
                      {showDur && (
                        <th className="text-center py-1.5 px-2 text-muted font-normal whitespace-nowrap">
                          Avg Dur (min)
                        </th>
                      )}
                    </tr>
                  </thead>
                  <tbody>
                    {top.map((r, i) => {
                      const id = String(r[colName] ?? r[interviewerCol] ?? i)
                      const lvl = r.risk_level
                      const badgeCls =
                        lvl === 'HIGH'
                          ? 'bg-critical/10 text-critical border-critical/30'
                          : lvl === 'MEDIUM'
                          ? 'bg-warning/10 text-warning border-warning/30'
                          : 'bg-accent/10 text-accent border-accent/30'
                      const rowCls =
                        lvl === 'HIGH' ? 'bg-critical/5' : lvl === 'MEDIUM' ? 'bg-warning/5' : ''
                      const rateColor =
                        lvl === 'HIGH' ? 'text-critical' : lvl === 'MEDIUM' ? 'text-warning' : 'text-accent'
                      return (
                        <tr
                          key={id}
                          className={`border-b border-line/50 hover:opacity-90 transition-opacity ${rowCls}`}
                        >
                          <td className="py-1.5 px-2 text-tx font-medium whitespace-nowrap">{id}</td>
                          {showSup && (
                            <td className="py-1.5 px-2 text-muted whitespace-nowrap">
                              {r.supervisor && r.supervisor !== 'None' ? r.supervisor : '—'}
                            </td>
                          )}
                          <td className="py-1.5 px-2 text-center">
                            <span className={`text-[10px] px-1.5 py-0.5 rounded-full border ${badgeCls}`}>
                              {lvl}
                            </span>
                          </td>
                          <td className={`py-1.5 px-2 text-center font-bold ${rateColor}`}>{r.risk_score}</td>
                          <td className="py-1.5 px-2 text-center text-muted">{r.total_interviews}</td>
                          <td className="py-1.5 px-2 text-center text-tx">{r.total_flags}</td>
                          <td className={`py-1.5 px-2 text-center font-medium ${rateColor}`}>
                            {r.flag_rate_pct}%
                          </td>
                          <td className="py-1.5 px-2 text-center text-muted">{r.fabrication_flags || 0}</td>
                          <td className="py-1.5 px-2 text-center text-muted">{r.duration_flags || 0}</td>
                          <td className="py-1.5 px-2 text-center text-muted">{r.straightlining_flags || 0}</td>
                          {showDur && (
                            <td className="py-1.5 px-2 text-center text-muted">
                              {r.avg_duration != null ? r.avg_duration : '—'}
                            </td>
                          )}
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
              {rows.length > 10 && (
                <p className="text-[10px] text-muted mt-2 px-1">
                  Showing top 10 of {rows.length} interviewers by risk score. Full breakdown in the{' '}
                  <span className="text-accent">Interviewers</span> tab.
                </p>
              )}
            </>
          )}
        </div>
      )}
    </div>
  )
}

function SeverityBreakdownChart({ flaggedBySeverity }: { flaggedBySeverity: Record<string, number> }) {
  const data = [
    { name: 'Critical', value: flaggedBySeverity.critical ?? 0, fill: SEV_COLORS.critical },
    { name: 'Warning',  value: flaggedBySeverity.warning ?? 0,  fill: SEV_COLORS.warning },
    { name: 'Info',     value: flaggedBySeverity.info ?? 0,     fill: SEV_COLORS.info },
  ].filter((d) => d.value > 0)

  return (
    <div className="card p-4">
      <p className="text-xs font-medium text-tx mb-3">Flags by Severity</p>
      {data.length > 0 ? (
        <ResponsiveContainer width="100%" height={180}>
          <PieChart>
            <Pie
              data={data}
              cx="50%"
              cy="45%"
              outerRadius={62}
              dataKey="value"
              label={({ name, percent }) => `${(percent * 100).toFixed(0)}%`}
              labelLine={false}
            >
              {data.map((entry, i) => (
                <Cell key={i} fill={entry.fill} />
              ))}
            </Pie>
            <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 10, color: '#6B7280' }} />
            <Tooltip {...CHART_TOOLTIP_STYLE} formatter={(v: number, name: string) => [v, name]} />
          </PieChart>
        </ResponsiveContainer>
      ) : (
        <p className="text-xs text-muted text-center mt-8">No flags to chart.</p>
      )}
    </div>
  )
}

function InterviewerFlagChart({ nameFilter }: { nameFilter: string }) {
  const { results, interviewerCol, rows, colName, isLoading } = useInterviewerRiskRows()

  if (!results) return null

  const filtered = nameFilter.trim()
    ? rows.filter((r) => String(r[colName] ?? r[interviewerCol] ?? '').toLowerCase().includes(nameFilter.trim().toLowerCase()))
    : rows
  const top = filtered.slice(0, 10)

  return (
    <div className="card p-4">
      <p className="text-xs font-medium text-tx mb-3">Top 10 Interviewers by Flag Count</p>
      {isLoading && (
        <div className="flex items-center justify-center gap-2 h-[180px] text-xs text-muted">
          <Loader2 size={12} className="animate-spin" />
          Computing…
        </div>
      )}
      {!isLoading && top.length > 0 && (
        <ResponsiveContainer width="100%" height={180}>
          <BarChart data={top} margin={{ top: 4, right: 4, left: -28, bottom: 32 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#E2E6ED" />
            <XAxis
              dataKey={colName}
              tick={{ fill: '#6B7280', fontSize: 9 }}
              angle={-35}
              textAnchor="end"
              interval={0}
            />
            <YAxis allowDecimals={false} tick={{ fill: '#6B7280', fontSize: 9 }} />
            <Tooltip {...CHART_TOOLTIP_STYLE} formatter={(v: number) => [v, 'Flags']} />
            <Bar dataKey="total_flags" radius={[3, 3, 0, 0]}>
              {top.map((r, i) => (
                <Cell key={i} fill={RISK_COLORS[r.risk_level] ?? SEV_COLORS.info} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      )}
      {!isLoading && top.length === 0 && (
        <p className="text-xs text-muted text-center mt-8">
          {nameFilter.trim() ? 'No interviewers match that filter.' : 'No interviewer data available.'}
        </p>
      )}
    </div>
  )
}

type UploadStatus = 'idle' | 'uploading' | 'done' | 'error'

const SUPPORT_FILES = [
  { key: 'backcheck',    label: 'Backcheck',    accept: '.xlsx,.csv', hint: 'Interviewer error records' },
  { key: 'listen_in',   label: 'Listen-in',    accept: '.xlsx,.csv', hint: 'Audio monitoring log' },
  { key: 'performance', label: 'Performance',  accept: '.xlsx,.csv', hint: 'Productivity per interviewer' },
  { key: 'cancelled',   label: 'Cancelled',    accept: '.xlsx,.csv', hint: 'Rejected/cancelled interviews' },
] as const
type SupportKey = typeof SUPPORT_FILES[number]['key']

function SupportingFilesSection({ projectId, waveLabel, token }: { projectId: number; waveLabel: string; token: string }) {
  const [files, setFiles] = useState<Partial<Record<SupportKey, File>>>({})
  const [statuses, setStatuses] = useState<Partial<Record<SupportKey, UploadStatus>>>({})
  const [errors, setErrors] = useState<Partial<Record<SupportKey, string>>>({})

  const setStatus = (key: SupportKey, s: UploadStatus) => setStatuses(p => ({ ...p, [key]: s }))
  const setErr = (key: SupportKey, e: string) => setErrors(p => ({ ...p, [key]: e }))

  const upload = async (key: SupportKey) => {
    const file = files[key]
    if (!file) return
    setStatus(key, 'uploading')
    setErr(key, '')
    try {
      const wl = waveLabel.trim() || undefined
      if (key === 'backcheck')    await uploadBackcheck(projectId, file, token, wl)
      if (key === 'listen_in')    await uploadListenIn(projectId, file, token, wl)
      if (key === 'performance')  await uploadPerformance(projectId, file, token, wl)
      if (key === 'cancelled')    await uploadCancelled(projectId, file, token, wl)
      setStatus(key, 'done')
    } catch (e) {
      setStatus(key, 'error')
      setErr(key, (e as Error).message)
    }
  }

  return (
    <div className="mt-3 pt-3 border-t border-line space-y-2">
      <p className="text-xs text-muted font-medium uppercase tracking-wider">Upload supporting files (optional)</p>
      {SUPPORT_FILES.map(({ key, label, accept, hint }) => {
        const status = statuses[key] ?? 'idle'
        const file = files[key]
        return (
          <div key={key} className="flex items-center gap-2 py-1">
            <div className="w-24 shrink-0">
              <p className="text-xs text-tx font-medium">{label}</p>
              <p className="text-[10px] text-muted">{hint}</p>
            </div>
            <label className="flex-1 cursor-pointer">
              <span className={`text-xs px-2 py-1 rounded border transition-colors block truncate ${
                file ? 'border-accent/40 text-accent bg-accent/5' : 'border-line text-muted hover:border-muted'
              }`}>
                {file ? file.name : 'Choose file…'}
              </span>
              <input
                type="file"
                accept={accept}
                className="hidden"
                onChange={e => {
                  const f = e.target.files?.[0]
                  if (f) { setFiles(p => ({ ...p, [key]: f })); setStatus(key, 'idle') }
                }}
              />
            </label>
            <button
              onClick={() => upload(key)}
              disabled={!file || status === 'uploading' || status === 'done'}
              className={`text-xs px-3 py-1 rounded border shrink-0 transition-colors ${
                status === 'done' ? 'border-accent/40 text-accent bg-accent/10 cursor-default' :
                status === 'error' ? 'border-critical/40 text-critical hover:bg-critical/10' :
                !file ? 'border-line text-muted cursor-not-allowed opacity-50' :
                'border-accent text-accent hover:bg-accent/10'
              }`}
            >
              {status === 'uploading' ? '…' : status === 'done' ? '✓ Saved' : 'Upload'}
            </button>
            {errors[key] && <p className="text-[10px] text-critical ml-1">{errors[key]}</p>}
          </div>
        )
      })}
    </div>
  )
}

const STANDARD_FIELDS: { key: string; label: string; aliases: string[] }[] = [
  { key: 'interviewer_id',   label: 'Interviewer ID',     aliases: ['INTERVIEWER_ID', 'INTERVIEWER ID'] },
  { key: 'instance_id',      label: 'Instance/Record ID', aliases: ['INSTANCE_ID', 'INSTANCE ID'] },
  { key: 'interview_date',   label: 'Interview date',     aliases: ['INTERVIEW_DATE', 'INTERVIEW DATE'] },
  { key: 'duration_minutes', label: 'Duration (minutes)', aliases: ['DURATION_MINUTES', 'DURATION MINUTES'] },
  { key: 'region',           label: 'Region',             aliases: ['REGION'] },
]

function SaveToProject() {
  const { authUser, authToken, fileId, jobId, filename, columnNames, openLogin, setDashboardMode, setDashboardProject } = useAppStore()
  const [expanded, setExpanded] = useState(false)
  const [mode, setMode] = useState<'pick' | 'new'>('pick')
  const [selectedId, setSelectedId] = useState<number | ''>('')
  const [newName, setNewName] = useState('')
  const [waveLabel, setWaveLabel] = useState('')
  const [saved, setSaved] = useState(false)
  const [savedProjectId, setSavedProjectId] = useState<number | null>(null)
  const [saveError, setSaveError] = useState('')
  const [suggestedWave, setSuggestedWave] = useState('')
  const [pendingDuplicateName, setPendingDuplicateName] = useState('')
  const [columnConfig, setColumnConfig] = useState<Record<string, string>>({})

  const projectsQuery = useQuery<Project[]>({
    queryKey: ['projects', authToken],
    queryFn: () => getProjects(authToken!),
    enabled: !!authToken && expanded,
  })

  const upperCols = columnNames.map((c) => c.trim().toUpperCase())
  const unmappedFields = STANDARD_FIELDS.filter((f) => !f.aliases.some((a) => upperCols.includes(a)))

  const saveMutation = useMutation({
    mutationFn: async () => {
      if (!authToken || !fileId || !filename) throw new Error('Missing auth or file')
      let projectId: number

      if (mode === 'new') {
        const name = newName.trim()
        if (!name) throw new Error('Project name required')
        const proj = await createProject(name, authToken)
        projectId = proj.id
      } else {
        if (!selectedId) throw new Error('Select a project')
        projectId = Number(selectedId)
      }

      const finalColumnConfig = Object.fromEntries(Object.entries(columnConfig).filter(([, v]) => v))
      const result = await saveQCResults(
        projectId, fileId, filename, authToken,
        waveLabel.trim() || undefined, jobId ?? undefined,
        Object.keys(finalColumnConfig).length ? finalColumnConfig : undefined,
      )
      setSavedProjectId(projectId)
      return result
    },
    onSuccess: () => {
      setSaved(true)
      setSaveError('')
      setPendingDuplicateName('')
    },
    onError: (err) => {
      const status = (err as { status?: number }).status
      if (mode === 'new' && status === 409) {
        setPendingDuplicateName(newName.trim())
      } else {
        setPendingDuplicateName('')
      }
      setSaveError((err as Error).message)
    },
  })

  // Once "Use existing project instead" switches back to pick mode, pre-select the matching project
  useEffect(() => {
    if (!pendingDuplicateName || !projectsQuery.data) return
    const found = projectsQuery.data.find((p) => p.name.toLowerCase() === pendingDuplicateName.toLowerCase())
    if (found) {
      setSelectedId(found.id)
      setPendingDuplicateName('')
    }
  }, [pendingDuplicateName, projectsQuery.data])

  // Suggest next wave label when a project is selected
  const { data: uploadLog } = useQuery({
    queryKey: ['upload-log-wave', selectedId, authToken],
    queryFn: () => getUploadLog(Number(selectedId), authToken!),
    enabled: !!authToken && !!selectedId && mode === 'pick',
  })

  useEffect(() => {
    if (!uploadLog) return
    const waveLabels = uploadLog
      .map((u: { wave_label?: string | null }) => u.wave_label)
      .filter((l): l is string => !!l)
    const nums = waveLabels
      .map((l: string) => { const m = l.match(/\d+/); return m ? parseInt(m[0]) : 0 })
      .filter((n: number) => n > 0)
    if (nums.length > 0) {
      setSuggestedWave(`Wave ${Math.max(...nums) + 1}`)
    } else if (waveLabels.length > 0) {
      setSuggestedWave('')
    }
  }, [uploadLog])

  if (!authUser) {
    return (
      <div className="card p-4 flex items-center justify-between">
        <div className="flex items-center gap-2 text-sm text-muted">
          <Database size={14} />
          Save results to a dashboard project
        </div>
        <button onClick={() => openLogin('inline')} className="btn-ghost text-xs flex items-center gap-1">
          Sign in <ChevronRight size={12} />
        </button>
      </div>
    )
  }

  if (saved) {
    return (
      <div className="card p-4 space-y-0">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2 text-accent text-sm">
            <Check size={14} />
            Results saved to project — upload is now locked.
          </div>
          {savedProjectId !== null && (
            <button
              onClick={() => { setDashboardMode(true); setDashboardProject(savedProjectId) }}
              className="btn-ghost text-xs flex items-center gap-1.5"
            >
              <Database size={12} /> View in Dashboard
            </button>
          )}
        </div>
        {savedProjectId !== null && authToken && (
          <SupportingFilesSection
            projectId={savedProjectId}
            waveLabel={waveLabel}
            token={authToken}
          />
        )}
      </div>
    )
  }

  return (
    <div className="card overflow-hidden">
      <button
        onClick={() => setExpanded((x) => !x)}
        className="w-full flex items-center justify-between px-4 py-3 text-sm text-tx hover:bg-surface2 transition-colors"
      >
        <span className="flex items-center gap-2">
          <Database size={14} className="text-accent" />
          Save to dashboard project
        </span>
        {expanded ? <ChevronDown size={14} className="text-muted" /> : <ChevronRight size={14} className="text-muted" />}
      </button>

      {expanded && (
        <div className="border-t border-line px-4 pb-4 pt-3 space-y-4">
          {/* Project mode toggle */}
          <div className="flex gap-2">
            <button
              onClick={() => setMode('pick')}
              className={`text-xs px-3 py-1 rounded-md border transition-colors ${mode === 'pick' ? 'border-accent text-accent bg-accent/10' : 'border-line text-muted hover:text-tx'}`}
            >
              Existing project
            </button>
            <button
              onClick={() => setMode('new')}
              className={`text-xs px-3 py-1 rounded-md border transition-colors ${mode === 'new' ? 'border-accent text-accent bg-accent/10' : 'border-line text-muted hover:text-tx'}`}
            >
              New project
            </button>
          </div>

          {mode === 'pick' && (
            <div>
              {projectsQuery.isLoading && <p className="text-xs text-muted">Loading projects…</p>}
              {projectsQuery.isError && <p className="text-xs text-critical">Could not load projects</p>}
              {projectsQuery.data && (
                <select
                  value={selectedId}
                  onChange={(e) => setSelectedId(e.target.value ? Number(e.target.value) : '')}
                  className="w-full bg-surface2 border border-line rounded-lg px-3 py-2 text-sm text-tx focus:outline-none focus:border-accent"
                >
                  <option value="">— select a project —</option>
                  {projectsQuery.data.map((p) => (
                    <option key={p.id} value={p.id}>{p.name}{p.status === 'closed' ? ' (closed)' : ''}</option>
                  ))}
                </select>
              )}
            </div>
          )}

          {mode === 'new' && (
            <input
              type="text"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="Project name"
              className="w-full bg-surface2 border border-line rounded-lg px-3 py-2 text-sm text-tx placeholder:text-muted focus:outline-none focus:border-accent"
            />
          )}

          <div className="relative">
            <input
              type="text"
              value={waveLabel}
              onChange={(e) => setWaveLabel(e.target.value)}
              placeholder={suggestedWave ? `Suggested: ${suggestedWave}` : 'Wave label (optional, e.g. Wave 1)'}
              className="w-full bg-surface2 border border-line rounded-lg px-3 py-2 text-sm text-tx placeholder:text-muted focus:outline-none focus:border-accent"
            />
            {suggestedWave && !waveLabel && (
              <button
                type="button"
                onClick={() => setWaveLabel(suggestedWave)}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-[10px] text-accent border border-accent/40 rounded px-1.5 py-0.5 hover:bg-accent/10"
              >
                Use {suggestedWave}
              </button>
            )}
          </div>

          {unmappedFields.length > 0 && (
            <div className="space-y-1.5 pt-1 border-t border-line/60">
              <p className="text-[10px] text-muted uppercase tracking-wider">Map columns (not auto-detected)</p>
              {unmappedFields.map((f) => (
                <div key={f.key} className="flex items-center gap-2">
                  <span className="text-xs text-muted w-32 shrink-0">{f.label}</span>
                  <select
                    value={columnConfig[f.key] ?? ''}
                    onChange={(e) => setColumnConfig((c) => ({ ...c, [f.key]: e.target.value }))}
                    className="flex-1 bg-surface2 border border-line rounded px-2 py-1 text-xs text-tx"
                  >
                    <option value="">— skip —</option>
                    {columnNames.map((c) => <option key={c} value={c}>{c}</option>)}
                  </select>
                </div>
              ))}
            </div>
          )}

          {saveError && (
            <div className="text-xs text-critical bg-critical/10 border border-critical/30 rounded px-3 py-2 space-y-1.5">
              <p>{saveError}</p>
              {pendingDuplicateName && (
                <button
                  type="button"
                  onClick={() => setMode('pick')}
                  className="text-[11px] text-accent underline underline-offset-2"
                >
                  Use existing project instead
                </button>
              )}
            </div>
          )}

          <button
            onClick={() => saveMutation.mutate()}
            disabled={saveMutation.isPending}
            className="btn-primary text-sm"
          >
            {saveMutation.isPending ? 'Saving…' : 'Save to project'}
          </button>
        </div>
      )}
    </div>
  )
}

export function QCReport() {
  const { results, jobId, jobStatus, jobError, rowCount, groqApiKey, config, supplementalChecks } = useAppStore()
  const [downloading, setDownloading] = useState(false)
  const [summary, setSummary] = useState('')
  const [sevFilter, setSevFilter] = useState<'all' | 'critical' | 'warning' | 'info'>('all')
  const [minFlags, setMinFlags] = useState(0)
  const [checkSearch, setCheckSearch] = useState('')
  const [itvFilter, setItvFilter] = useState('')

  const summaryMutation = useMutation({
    mutationFn: () =>
      generateQCSummary(
        results!.total_flags,
        rowCount ?? 0,
        results!.checks.map((c) => ({
          check_name: c.check_name,
          severity: c.severity,
          flag_count: c.flag_count,
        })),
        groqApiKey,
        config.verbatim_check.model,
      ),
    onSuccess: (data) => setSummary(data.summary),
  })

  const handleDownload = async () => {
    if (!jobId) return
    setDownloading(true)
    try {
      const blob = await downloadReport(jobId)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `qc_report_${jobId.slice(0, 8)}.xlsx`
      a.click()
      URL.revokeObjectURL(url)
    } finally {
      setDownloading(false)
    }
  }

  if (jobStatus === 'idle' || jobStatus === 'queued' || jobStatus === 'running') {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-3 text-muted">
        <Activity size={32} className={jobStatus !== 'idle' ? 'animate-pulse text-accent' : ''} />
        <p className="text-sm">{jobStatus === 'idle' ? 'Configure settings and click Run QC.' : `QC in progress…`}</p>
      </div>
    )
  }

  if (jobStatus === 'failed') {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-3 text-critical">
        <XCircle size={32} />
        <p className="text-sm">{jobError ?? 'QC run failed. Try again.'}</p>
      </div>
    )
  }

  if (!results) return null

  const sorted = [...results.checks].sort((a, b) => (SEV_ORDER[a.severity] ?? 9) - (SEV_ORDER[b.severity] ?? 9))
  const totalChecks = results.checks.length + supplementalChecks.length
  const totalFlags = results.total_flags + supplementalChecks.reduce((s, c) => s + c.flag_count, 0)

  const applyFilters = (checks: typeof sorted) =>
    checks.filter(c => {
      if (sevFilter !== 'all' && c.severity !== sevFilter) return false
      if (c.flag_count < minFlags) return false
      if (checkSearch && !c.check_name.toLowerCase().includes(checkSearch.toLowerCase())) return false
      return true
    })

  const filteredMain = applyFilters(sorted)
  const filteredSupp = applyFilters(supplementalChecks)

  const groupBySeverity = (checks: typeof sorted) => ({
    critical: checks.filter(c => c.severity === 'critical' && c.flag_count > 0),
    warning:  checks.filter(c => c.severity === 'warning'  && c.flag_count > 0),
    info:     checks.filter(c => c.severity === 'info'     && c.flag_count > 0),
    clean:    checks.filter(c => c.flag_count === 0),
  })

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Metric cards */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
        <MetricCard label="Checks run" value={totalChecks} />
        <MetricCard label="Total flags" value={totalFlags} />
        <MetricCard label="Critical" value={results.flagged_by_severity.critical ?? 0} color="text-critical" />
        <MetricCard label="Warnings" value={results.flagged_by_severity.warning ?? 0} color="text-warning" />
        <MetricCard label="Info" value={results.flagged_by_severity.info ?? 0} color="text-info" />
      </div>

      {/* Interviewer risk — auto-computed when interviewer column is configured */}
      <InterviewerRiskPanel />

      {/* AI Summary */}
      {groqApiKey && (
        <div className="card p-4 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-medium text-tx flex items-center gap-1.5">
              <FileText size={14} className="text-accent" />
              AI Executive Summary
            </h3>
            <button
              onClick={() => summaryMutation.mutate()}
              disabled={summaryMutation.isPending}
              className="btn-ghost flex items-center gap-1.5 text-xs"
            >
              <Sparkles size={11} className="text-accent" />
              {summaryMutation.isPending ? 'Generating…' : summary ? 'Regenerate' : 'Generate summary'}
            </button>
          </div>
          {summaryMutation.isError && (
            <p className="text-xs text-critical">{(summaryMutation.error as Error).message}</p>
          )}
          {summary && (
            <p className="text-xs text-tx leading-relaxed whitespace-pre-wrap">{summary}</p>
          )}
          {!summary && !summaryMutation.isPending && (
            <p className="text-xs text-muted">
              Click "Generate summary" to get an AI-written executive narrative of these QC results.
            </p>
          )}
        </div>
      )}

      {/* Download */}
      <div className="flex justify-end">
        <button onClick={handleDownload} disabled={downloading} className="btn-ghost flex items-center gap-2">
          <Download size={14} />
          {downloading ? 'Downloading…' : 'Download Excel report'}
        </button>
      </div>

      {/* ── Filter bar ───────────────────────────────────────────────────── */}
      <div className="card p-3 space-y-3">
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-1.5 text-xs text-muted shrink-0">
            <Filter size={12} />
            <span>Filter checks:</span>
          </div>
          <div className="flex gap-1">
            {(['all', 'critical', 'warning', 'info'] as const).map(sev => (
              <button
                key={sev}
                onClick={() => setSevFilter(sev)}
                className={`text-[10px] px-2.5 py-1 rounded-full font-medium border transition-colors capitalize ${
                  sevFilter === sev
                    ? sev === 'critical' ? 'bg-critical/20 text-critical border-critical/40'
                      : sev === 'warning' ? 'bg-warning/20 text-warning border-warning/40'
                      : sev === 'info' ? 'bg-info/20 text-info border-info/40'
                      : 'bg-surface2 text-tx border-line'
                    : 'text-muted border-line/50 hover:text-tx'
                }`}
              >
                {sev}
              </button>
            ))}
          </div>
          <div className="flex items-center gap-1.5 text-xs text-muted">
            <span>Min flags:</span>
            <input
              type="number"
              min={0}
              value={minFlags}
              onChange={e => setMinFlags(Math.max(0, +e.target.value))}
              className="w-16 py-0.5 px-2 text-xs"
            />
          </div>
          <div className="relative flex-1 min-w-32">
            <Search size={11} className="absolute left-2 top-1/2 -translate-y-1/2 text-muted" />
            <input
              type="text"
              placeholder="Search check name…"
              value={checkSearch}
              onChange={e => setCheckSearch(e.target.value)}
              className="w-full pl-6 py-0.5 text-xs"
            />
          </div>
          <div className="relative flex-1 min-w-32">
            <Users size={11} className="absolute left-2 top-1/2 -translate-y-1/2 text-muted" />
            <input
              type="text"
              placeholder="Filter interviewer chart…"
              value={itvFilter}
              onChange={e => setItvFilter(e.target.value)}
              className="w-full pl-6 py-0.5 text-xs"
            />
          </div>
          {(sevFilter !== 'all' || minFlags > 0 || checkSearch) && (
            <button
              onClick={() => { setSevFilter('all'); setMinFlags(0); setCheckSearch('') }}
              className="text-[10px] text-muted hover:text-tx"
            >
              Clear filters
            </button>
          )}
        </div>
        {(sevFilter !== 'all' || minFlags > 0 || checkSearch) && (
          <p className="text-[10px] text-muted">
            Showing {filteredMain.length + filteredSupp.length} of {totalChecks} checks
          </p>
        )}
      </div>

      {/* Visuals — severity breakdown + top interviewer flags */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <SeverityBreakdownChart flaggedBySeverity={results.flagged_by_severity} />
        <InterviewerFlagChart nameFilter={itvFilter} />
      </div>

      {/* Main pipeline checks — grouped by severity */}
      <div className="space-y-4">
        {results.total_flags === 0 && supplementalChecks.length === 0 ? (
          <div className="flex items-center gap-2 text-accent text-sm justify-center py-8">
            <Info size={16} />
            No issues found — your data looks clean!
          </div>
        ) : (
          <>
            {/* Critical */}
            {groupBySeverity(filteredMain).critical.length > 0 && (
              <div className="space-y-2">
                <div className="flex items-center gap-2">
                  <div className="h-3 w-1 rounded bg-critical" />
                  <h3 className="text-xs font-semibold text-critical uppercase tracking-wide">
                    Critical Issues — {groupBySeverity(filteredMain).critical.length} check{groupBySeverity(filteredMain).critical.length !== 1 ? 's' : ''}
                  </h3>
                </div>
                {groupBySeverity(filteredMain).critical.map((check) => (
                  <CheckAccordion key={check.check_name} check={check} totalFlags={totalFlags}
                    totalRows={rowCount ?? 0} groqApiKey={groqApiKey} model={config.verbatim_check.model} />
                ))}
              </div>
            )}
            {/* Warning */}
            {groupBySeverity(filteredMain).warning.length > 0 && (
              <div className="space-y-2">
                <div className="flex items-center gap-2">
                  <div className="h-3 w-1 rounded bg-warning" />
                  <h3 className="text-xs font-semibold text-warning uppercase tracking-wide">
                    Warnings — {groupBySeverity(filteredMain).warning.length} check{groupBySeverity(filteredMain).warning.length !== 1 ? 's' : ''}
                  </h3>
                </div>
                {groupBySeverity(filteredMain).warning.map((check) => (
                  <CheckAccordion key={check.check_name} check={check} totalFlags={totalFlags}
                    totalRows={rowCount ?? 0} groqApiKey={groqApiKey} model={config.verbatim_check.model} />
                ))}
              </div>
            )}
            {/* Info */}
            {groupBySeverity(filteredMain).info.length > 0 && (
              <div className="space-y-2">
                <div className="flex items-center gap-2">
                  <div className="h-3 w-1 rounded bg-info" />
                  <h3 className="text-xs font-semibold text-info uppercase tracking-wide">
                    Info — {groupBySeverity(filteredMain).info.length} check{groupBySeverity(filteredMain).info.length !== 1 ? 's' : ''}
                  </h3>
                </div>
                {groupBySeverity(filteredMain).info.map((check) => (
                  <CheckAccordion key={check.check_name} check={check} totalFlags={totalFlags}
                    totalRows={rowCount ?? 0} groqApiKey={groqApiKey} model={config.verbatim_check.model} />
                ))}
              </div>
            )}
            {/* Clean checks (no flags) — collapsed by default */}
            {groupBySeverity(filteredMain).clean.length > 0 && (sevFilter === 'all' && !checkSearch) && (
              <details className="group">
                <summary className="text-xs text-muted cursor-pointer hover:text-tx flex items-center gap-1.5 list-none py-1">
                  <ChevronRight size={12} className="group-open:rotate-90 transition-transform" />
                  {groupBySeverity(filteredMain).clean.length} checks passed (no flags)
                </summary>
                <div className="space-y-2 mt-2">
                  {groupBySeverity(filteredMain).clean.map((check) => (
                    <CheckAccordion key={check.check_name} check={check} totalFlags={totalFlags}
                      totalRows={rowCount ?? 0} groqApiKey={groqApiKey} model={config.verbatim_check.model} />
                  ))}
                </div>
              </details>
            )}
          </>
        )}
      </div>

      {/* Supplemental checks from tabs */}
      {filteredSupp.length > 0 && (
        <div className="space-y-2">
          <h3 className="text-xs font-semibold text-muted uppercase tracking-wide">Ad-hoc Checks (from tabs)</h3>
          {filteredSupp.map((check) => (
            <CheckAccordion
              key={check.check_name}
              check={check}
              totalFlags={totalFlags}
              totalRows={rowCount ?? 0}
              groqApiKey={groqApiKey}
              model={config.verbatim_check.model}
            />
          ))}
        </div>
      )}

      {/* Save to dashboard project */}
      <SaveToProject />
    </div>
  )
}
