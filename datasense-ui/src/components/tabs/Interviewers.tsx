import React, { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell,
  PieChart, Pie, Legend, LineChart, Line,
} from 'recharts'
import {
  Users, AlertTriangle, Download, Sparkles, ChevronDown, ChevronUp,
  CheckCircle2, LayoutDashboard, TrendingUp, Loader2, Activity, Filter,
} from 'lucide-react'
import { useAppStore } from '../../store/appStore'
import { computeRisk, type RiskRow } from '../../api/interviewers'
import { generateFeedbackLetter } from '../../api/ai'
import { addSupplemental } from '../../api/qc'
import { InterviewerProfile } from './InterviewerProfile'
import { getInterviewerMetrics, upsertInterviewer, type InterviewerMetrics } from '../../api/dashboard'

const TOOLTIP_STYLE = {
  contentStyle: { background: '#111318', border: '1px solid #1f2330', borderRadius: 6 },
  labelStyle: { color: '#e8eaf2' },
  itemStyle: { color: '#4af0a0' },
}

function riskColor(score: number, red: number, amber: number) {
  if (score >= red) return '#f04a6a'
  if (score >= amber) return '#f0c04a'
  return '#4af0a0'
}

function riskScoreClass(score: number, red: number, amber: number) {
  if (score >= red) return 'text-critical'
  if (score >= amber) return 'text-warning'
  return 'text-accent'
}

function riskBadge(level: string) {
  if (level === 'HIGH') return 'bg-critical/10 text-critical border border-critical/30'
  if (level === 'MEDIUM') return 'bg-warning/10 text-warning border border-warning/30'
  return 'bg-accent/10 text-accent border border-accent/30'
}

function MetricCard({ label, value, color }: { label: string; value: number | string; color?: string }) {
  return (
    <div className="card2 px-4 py-3 space-y-1">
      <p className="label">{label}</p>
      <p className={`text-2xl font-display font-extrabold ${color ?? 'text-tx'}`}>{value}</p>
    </div>
  )
}

// ── Dashboard ─────────────────────────────────────────────────────────────────

const PIE_COLORS: Record<string, string> = {
  HIGH: '#f04a6a', MEDIUM: '#f0c04a', LOW: '#4af0a0',
}

function RiskDashboard({
  rows,
  intColName,
  redThr,
  amberThr,
  dateTrends,
}: {
  rows: RiskRow[]
  intColName: string
  redThr: number
  amberThr: number
  dateTrends: { date: string; flag_count: number }[]
}) {
  const pieData = [
    { name: 'High Risk',   value: rows.filter((r) => r.risk_level === 'HIGH').length,   fill: PIE_COLORS.HIGH   },
    { name: 'Medium Risk', value: rows.filter((r) => r.risk_level === 'MEDIUM').length, fill: PIE_COLORS.MEDIUM },
    { name: 'Low Risk',    value: rows.filter((r) => r.risk_level === 'LOW').length,    fill: PIE_COLORS.LOW    },
  ].filter((d) => d.value > 0)

  const top5 = rows.slice(0, 5)

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 mb-1">
        <LayoutDashboard size={15} className="text-accent" />
        <h3 className="text-sm font-semibold text-tx">Risk Overview Dashboard</h3>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {/* Pie — risk distribution */}
        <div className="card p-4">
          <p className="text-xs font-medium text-tx mb-3">Risk Distribution</p>
          {pieData.length > 0 ? (
            <ResponsiveContainer width="100%" height={180}>
              <PieChart>
                <Pie
                  data={pieData}
                  cx="50%"
                  cy="45%"
                  outerRadius={62}
                  dataKey="value"
                  label={({ name, percent }) =>
                    `${(percent * 100).toFixed(0)}%`
                  }
                  labelLine={false}
                >
                  {pieData.map((entry, i) => (
                    <Cell key={i} fill={entry.fill} />
                  ))}
                </Pie>
                <Legend
                  iconType="circle"
                  iconSize={8}
                  wrapperStyle={{ fontSize: 10, color: '#8b90a8' }}
                />
                <Tooltip
                  contentStyle={{ background: '#111318', border: '1px solid #1f2330', borderRadius: 6 }}
                  formatter={(v: number, name: string) => [v, name]}
                />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-xs text-muted text-center mt-8">No data</p>
          )}
        </div>

        {/* Bar — top 5 */}
        <div className="card p-4">
          <p className="text-xs font-medium text-tx mb-3">Top 5 Highest Risk</p>
          {top5.length > 0 ? (
            <ResponsiveContainer width="100%" height={180}>
              <BarChart data={top5} margin={{ top: 4, right: 4, left: -28, bottom: 32 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1f2330" />
                <XAxis
                  dataKey={intColName}
                  tick={{ fill: '#8b90a8', fontSize: 9 }}
                  angle={-35}
                  textAnchor="end"
                  interval={0}
                />
                <YAxis domain={[0, 110]} tick={{ fill: '#8b90a8', fontSize: 9 }} />
                <Tooltip {...TOOLTIP_STYLE} formatter={(v: number) => [v, 'Risk Score']} />
                <Bar dataKey="risk_score" radius={[3, 3, 0, 0]}>
                  {top5.map((r, i) => (
                    <Cell key={i} fill={riskColor(r.risk_score, redThr, amberThr)} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-xs text-muted text-center mt-8">No data</p>
          )}
        </div>

        {/* Line — flag trends */}
        <div className="card p-4">
          <p className="text-xs font-medium text-tx mb-1">Flag Trends Over Time</p>
          {dateTrends.length > 1 ? (
            <ResponsiveContainer width="100%" height={180}>
              <LineChart data={dateTrends} margin={{ top: 4, right: 4, left: -28, bottom: 32 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1f2330" />
                <XAxis
                  dataKey="date"
                  tick={{ fill: '#8b90a8', fontSize: 9 }}
                  angle={-35}
                  textAnchor="end"
                  interval="preserveStartEnd"
                />
                <YAxis tick={{ fill: '#8b90a8', fontSize: 9 }} allowDecimals={false} />
                <Tooltip
                  contentStyle={{ background: '#111318', border: '1px solid #1f2330', borderRadius: 6 }}
                  formatter={(v: number) => [v, 'Flags']}
                />
                <Line
                  type="monotone"
                  dataKey="flag_count"
                  stroke="#4af0a0"
                  strokeWidth={2}
                  dot={false}
                  activeDot={{ r: 4, fill: '#4af0a0' }}
                />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex flex-col items-center justify-center h-36 gap-2">
              <TrendingUp size={22} className="text-muted" />
              <p className="text-xs text-muted text-center">
                {dateTrends.length === 0
                  ? 'Set a date column above and re-run to see flag trends.'
                  : 'Not enough date points to plot a trend.'}
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

export function Interviewers() {
  const { fileId, jobId, jobStatus, config, groqApiKey, itvTabState, setItvTabState, authToken } = useAppStore()
  const { intCol, redThr, amberThr, flagThr, rows, intColName, selectedInt,
          supervisorCol, dateCol, durationCol, dateTrends, productivityMatrix } = itvTabState

  const [riskFilter, setRiskFilter] = useState<'ALL' | 'HIGH' | 'MEDIUM' | 'LOW'>('ALL')
  const [issuesOnly, setIssuesOnly] = useState(false)
  const [showPerf, setShowPerf] = useState(false)

  const defaultIntCol =
    config.interviewer_duration_check.interviewer_column ||
    config.interviewer_productivity_check.interviewer_column ||
    config.fabrication_check.interviewer_column || ''

  React.useEffect(() => {
    if (!intCol && defaultIntCol) setItvTabState({ intCol: defaultIntCol })
  }, [defaultIntCol]) // eslint-disable-line react-hooks/exhaustive-deps

  const [letter, setLetter]           = useState('')
  const [showMethods, setShowMethods] = useState(false)
  const [reportPushed, setReportPushed] = useState(false)
  const [profileRow, setProfileRow]   = useState<RiskRow | null>(null)
  const [dbMetrics, setDbMetrics]     = useState<Record<string, InterviewerMetrics>>({})
  const [dbLoading, setDbLoading]     = useState(false)

  const riskMutation = useMutation({
    mutationFn: () => computeRisk(fileId!, jobId!, intCol, redThr, amberThr,
                                  supervisorCol || undefined, dateCol || undefined,
                                  durationCol || undefined),
    onSuccess: async (data) => {
      setDbMetrics({})
      setItvTabState({
        rows: data.rows as unknown as Record<string, unknown>[],
        intColName: data.interviewer_column,
        selectedInt: data.rows.length > 0 ? String(data.rows[0][data.interviewer_column] ?? '') : '',
        dateTrends: data.date_trends ?? [],
        productivityMatrix: data.productivity_matrix ?? [],
      })
      setReportPushed(false)
      if (jobId && data.rows.length > 0) {
        addSupplemental(jobId, {
          check_name: 'interviewer_risk_scores',
          issue_type: 'Interviewer Risk',
          severity: 'warning',
          flag_count: data.rows.filter((r: RiskRow) => r.risk_level === 'HIGH').length,
          flagged_rows: data.rows.filter((r: RiskRow) => r.risk_level !== 'LOW') as unknown as Record<string, unknown>[],
        }).then(() => setReportPushed(true)).catch(() => { /* non-blocking */ })
      }
      if (authToken && data.rows.length > 0) {
        setDbLoading(true)
        const codes = [...new Set(
          (data.rows as RiskRow[]).map(r => String(r[data.interviewer_column] ?? '')).filter(Boolean)
        )]
        const results = await Promise.allSettled(
          codes.map(code =>
            getInterviewerMetrics(code, authToken).then(m => [code, m] as [string, InterviewerMetrics])
          )
        )
        const metrics: Record<string, InterviewerMetrics> = {}
        const unregistered: string[] = []
        results.forEach((r, i) => {
          if (r.status === 'fulfilled') {
            const [c, m] = r.value
            metrics[c] = m
            if (!m.info) unregistered.push(c)  // has activity but not formally registered
          } else {
            unregistered.push(codes[i])  // 404 — completely unknown
          }
        })
        setDbMetrics(metrics)
        setDbLoading(false)
        // Auto-register new interviewers found in this file (fire-and-forget)
        if (unregistered.length > 0) {
          Promise.allSettled(
            unregistered.map(code => upsertInterviewer({ interviewer_code: code }, authToken))
          ).catch(() => { /* non-blocking */ })
        }
      }
    },
  })

  const typedRows = rows as unknown as RiskRow[]

  type EnrichedRow = RiskRow & {
    composite_score?: number
    db_supervisor?: string | null
    cross_project_interviews?: number
    by_project?: InterviewerMetrics['by_project']
  }

  const hasDbMetrics = Object.keys(dbMetrics).length > 0

  const enrichedRows: EnrichedRow[] = typedRows.map(row => {
    const code = String(row[intColName] ?? '')
    const m = dbMetrics[code]
    if (!m) return row as EnrichedRow
    const total = m.quality.total_interviews
    const flagged = m.quality.duration_flags + m.quality.sl_flags
    const crossFlagRate = total > 0 ? (flagged / total) * 100 : 0
    const bcErrRate = m.backcheck.bc_count > 0 ? (m.backcheck.total_errors / m.backcheck.bc_count) * 100 : 0
    const liFailRate = m.listen_in.li_count > 0 ? (m.listen_in.li_fail / m.listen_in.li_count) * 100 : 0
    return {
      ...row,
      db_supervisor: m.info?.supervisor_name ?? null,
      cross_project_interviews: total,
      composite_score: Math.min(Math.round(row.risk_score * 0.4 + crossFlagRate * 0.3 + bcErrRate * 0.2 + liFailRate * 0.1), 100),
      by_project: m.by_project,
    } as EnrichedRow
  })

  const letterMutation = useMutation({
    mutationFn: () => {
      const row = typedRows.find((r) => String(r[intColName]) === selectedInt)
      if (!row) throw new Error('Interviewer not found')
      return generateFeedbackLetter(selectedInt, row as Record<string, unknown>, groqApiKey)
    },
    onSuccess: (data) => setLetter(data.letter),
  })

  const canRun = !!fileId && !!jobId && jobStatus === 'complete' && !!intCol

  const high   = typedRows.filter((r) => r.risk_score >= redThr).length
  const medium = typedRows.filter((r) => r.risk_score >= amberThr && r.risk_score < redThr).length
  const low    = typedRows.filter((r) => r.risk_score < amberThr).length
  const aboveFlagThr = typedRows.filter((r) => r.flag_rate_pct > flagThr).length
  const hasDurationData = typedRows.some(r => r.avg_duration != null)
  const hasDateData = typedRows.some(r => r.first_interview != null)

  const filteredRows = enrichedRows.filter(r => {
    if (issuesOnly && r.risk_level === 'LOW') return false
    if (riskFilter !== 'ALL' && r.risk_level !== riskFilter) return false
    return true
  })

  const top20  = filteredRows.slice(0, 20)
  const hasSupervisors = typedRows.some((r) => r.supervisor && r.supervisor !== 'None' && r.supervisor !== 'null')
  const hasDbSupervisors = hasDbMetrics && enrichedRows.some(r => r.db_supervisor)
  const showSupervisorCol = hasSupervisors || hasDbSupervisors

  // Supervisors who have 2+ HIGH risk interviewers
  const supervisorHighCounts = typedRows
    .filter((r) => r.risk_level === 'HIGH' && r.supervisor && r.supervisor !== 'None')
    .reduce<Record<string, number>>((acc, r) => {
      const s = String(r.supervisor!)
      acc[s] = (acc[s] || 0) + 1
      return acc
    }, {})
  const flaggedSupervisors = new Set(
    Object.entries(supervisorHighCounts).filter(([, n]) => n >= 2).map(([s]) => s)
  )

  const downloadCSV = () => {
    const cols = Object.keys(typedRows[0] ?? {})
    const csv = [
      cols.join(','),
      ...typedRows.map((r) =>
        cols.map((c) => JSON.stringify(r[c as keyof RiskRow] ?? '')).join(',')
      ),
    ].join('\n')
    const a = document.createElement('a')
    a.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv' }))
    a.download = 'interviewer_risk_scores.csv'
    a.click()
  }

  const downloadLetter = () => {
    if (!letter) return
    const a = document.createElement('a')
    a.href = URL.createObjectURL(new Blob([letter], { type: 'text/plain' }))
    a.download = `feedback_letter_${selectedInt}.txt`
    a.click()
  }

  if (jobStatus !== 'complete') {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-3 text-muted">
        <Users size={32} />
        <p className="text-sm">Run QC first to compute interviewer risk scores.</p>
      </div>
    )
  }

  return (
    <div className="space-y-6 animate-fade-in">
      {profileRow && (
        <InterviewerProfile
          row={profileRow}
          intColName={intColName}
          redThr={redThr}
          amberThr={amberThr}
          onClose={() => setProfileRow(null)}
        />
      )}

      <div>
        <h2 className="font-display font-extrabold text-base text-tx">Interviewer Risk</h2>
        <p className="text-xs text-muted mt-0.5">
          Combines all QC flags into a weighted risk score per interviewer (0–100). Higher = investigate first.
        </p>
      </div>

      {/* Config row */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-7 gap-3">
        <div className="space-y-1 col-span-2 sm:col-span-1 lg:col-span-1">
          <p className="text-xs text-muted">Interviewer column</p>
          <input
            type="text" className="w-full" value={intCol}
            onChange={(e) => setItvTabState({ intCol: e.target.value })}
            placeholder="interviewer_id"
          />
        </div>
        <div className="space-y-1">
          <p className="text-xs text-muted">Supervisor column <span className="text-muted/60">(opt)</span></p>
          <input
            type="text" className="w-full" value={supervisorCol}
            onChange={(e) => setItvTabState({ supervisorCol: e.target.value })}
            placeholder="supervisor"
          />
        </div>
        <div className="space-y-1">
          <p className="text-xs text-muted">Date column <span className="text-muted/60">(opt)</span></p>
          <input
            type="text" className="w-full" value={dateCol}
            onChange={(e) => setItvTabState({ dateCol: e.target.value })}
            placeholder="interview_date"
          />
        </div>
        <div className="space-y-1">
          <p className="text-xs text-muted">Duration column <span className="text-muted/60">(opt)</span></p>
          <input
            type="text" className="w-full" value={durationCol}
            onChange={(e) => setItvTabState({ durationCol: e.target.value })}
            placeholder="duration_minutes"
          />
        </div>
        <div className="space-y-1">
          <p className="text-xs text-muted">Flag % alert threshold</p>
          <input type="number" className="w-full" min={1} max={100}
            value={flagThr} onChange={(e) => setItvTabState({ flagThr: +e.target.value })} />
        </div>
        <div className="space-y-1">
          <p className="text-xs text-muted">Red score ≥</p>
          <input type="number" className="w-full" min={2} max={100}
            value={redThr} onChange={(e) => setItvTabState({ redThr: +e.target.value })} />
        </div>
        <div className="space-y-1">
          <p className="text-xs text-muted">Amber score ≥</p>
          <input type="number" className="w-full" min={1} max={99}
            value={amberThr} onChange={(e) => setItvTabState({ amberThr: +e.target.value })} />
        </div>
      </div>

      <div className="flex items-center gap-3">
        <button
          onClick={() => riskMutation.mutate()}
          disabled={!canRun || riskMutation.isPending}
          className="btn-primary flex items-center gap-2"
        >
          <Users size={14} />
          {riskMutation.isPending ? 'Computing…' : 'Compute Risk Scores'}
        </button>
        {reportPushed && !riskMutation.isPending && !dbLoading && (
          <span className="flex items-center gap-1.5 text-xs text-accent">
            <CheckCircle2 size={13} /> Added to report
          </span>
        )}
        {dbLoading && (
          <span className="flex items-center gap-1.5 text-xs text-muted">
            <Loader2 size={12} className="animate-spin" /> Fetching cross-project data…
          </span>
        )}
        {hasDbMetrics && !dbLoading && (
          <span className="flex items-center gap-1.5 text-xs text-accent/70">
            <CheckCircle2 size={12} /> Cross-project enriched ({Object.keys(dbMetrics).length} IDs)
          </span>
        )}
      </div>

      {riskMutation.isError && (
        <p className="text-xs text-critical">{(riskMutation.error as Error).message}</p>
      )}

      {typedRows.length > 0 && (
        <>
          {/* Summary metrics */}
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
            <MetricCard label="Interviewers" value={typedRows.length} />
            <MetricCard label="High risk"   value={high}   color="text-critical" />
            <MetricCard label="Medium risk" value={medium} color="text-warning" />
            <MetricCard label="Low risk"    value={low}    color="text-accent" />
            <MetricCard label={`Above ${flagThr}% flag rate`} value={aboveFlagThr} />
          </div>

          {/* ── Filter bar ──────────────────────────────────────────────── */}
          <div className="flex flex-wrap items-center gap-3 py-2 border-b border-line">
            <div className="flex items-center gap-1.5 text-xs text-muted">
              <Filter size={12} />
              <span>Filter:</span>
            </div>
            <div className="flex gap-1">
              {(['ALL', 'HIGH', 'MEDIUM', 'LOW'] as const).map(level => (
                <button
                  key={level}
                  onClick={() => setRiskFilter(level)}
                  className={`text-[10px] px-2.5 py-1 rounded-full font-medium border transition-colors ${
                    riskFilter === level
                      ? level === 'HIGH' ? 'bg-critical/20 text-critical border-critical/40'
                        : level === 'MEDIUM' ? 'bg-warning/20 text-warning border-warning/40'
                        : level === 'LOW' ? 'bg-accent/20 text-accent border-accent/40'
                        : 'bg-surface2 text-tx border-line'
                      : 'text-muted border-line/50 hover:text-tx'
                  }`}
                >
                  {level}
                </button>
              ))}
            </div>
            <label className="flex items-center gap-1.5 text-xs text-muted cursor-pointer select-none">
              <input
                type="checkbox"
                checked={issuesOnly}
                onChange={e => setIssuesOnly(e.target.checked)}
                className="accent-accent"
              />
              Issues only (hide LOW risk)
            </label>
            {(riskFilter !== 'ALL' || issuesOnly) && (
              <span className="text-xs text-accent">
                Showing {filteredRows.length} of {enrichedRows.length} interviewers
              </span>
            )}
          </div>

          {/* ── Dashboard ───────────────────────────────────────────────── */}
          <RiskDashboard
            rows={typedRows}
            intColName={intColName}
            redThr={redThr}
            amberThr={amberThr}
            dateTrends={dateTrends}
          />

          {/* ── Risk table ──────────────────────────────────────────────── */}
          <div className="card border-line">
            <div className="flex items-center justify-between px-4 py-3 border-b border-line">
              <h3 className="text-sm font-medium text-tx">Interviewer Risk Rankings</h3>
              <button onClick={downloadCSV} className="btn-ghost flex items-center gap-1.5 text-xs">
                <Download size={12} /> Export CSV
              </button>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-line">
                    <th className="text-left py-2 px-3 text-muted font-normal">#</th>
                    {[
                      intColName,
                      ...(showSupervisorCol ? ['Supervisor'] : []),
                      'risk score',
                      ...(hasDbMetrics ? ['QC Score ★'] : []),
                      'risk level', 'total interviews', 'total flags',
                      'flag rate %', 'fabrication', 'duration',
                      'straightlining', 'productivity', 'verbatim',
                      ...(hasDurationData ? ['avg duration (min)', 'min dur', 'max dur'] : []),
                      ...(hasDateData ? ['first interview', 'last interview'] : []),
                    ].map((c) => (
                      <th key={c} className="text-left py-2 px-3 text-muted font-normal whitespace-nowrap">
                        {c}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {filteredRows.map((row, i) => {
                    const localSup = row.supervisor && row.supervisor !== 'None' && row.supervisor !== 'null'
                      ? String(row.supervisor) : null
                    const displaySup = localSup ?? row.db_supervisor ?? null
                    const isFlaggedSup = displaySup && flaggedSupervisors.has(displaySup)
                    const displayScore = row.composite_score ?? row.risk_score

                    return (
                      <tr key={i} className="border-b border-line/50 hover:bg-surface2 transition-colors">
                        <td className="py-2 px-3 text-muted">{i + 1}</td>
                        <td className="py-2 px-3">
                          <button
                            className="font-medium text-accent hover:underline"
                            onClick={() => setProfileRow(row)}
                          >
                            {String(row[intColName] ?? '')}
                          </button>
                        </td>
                        {showSupervisorCol && (
                          <td className="py-2 px-3">
                            {displaySup ? (
                              <span
                                className={`px-2 py-0.5 rounded text-[10px] font-medium ${
                                  isFlaggedSup
                                    ? 'bg-critical/15 text-critical border border-critical/30'
                                    : 'text-tx'
                                }`}
                                title={isFlaggedSup ? 'This supervisor has 2+ high-risk interviewers' : !localSup && row.db_supervisor ? 'From global database' : ''}
                              >
                                {displaySup}{isFlaggedSup && ' ⚠'}
                                {!localSup && row.db_supervisor && <span className="text-accent/50 ml-1 text-[9px]">·db</span>}
                              </span>
                            ) : (
                              <span className="text-muted">—</span>
                            )}
                          </td>
                        )}
                        <td className="py-2 px-3">
                          <div className="flex items-center gap-1.5">
                            <div className="h-1.5 rounded-full" style={{ width: `${Math.min(row.risk_score, 100)}%`, maxWidth: 60, background: riskColor(row.risk_score, redThr, amberThr) }} />
                            <span className="text-tx">{row.risk_score}</span>
                          </div>
                        </td>
                        {hasDbMetrics && (
                          <td className="py-2 px-3">
                            <div className="flex items-center gap-1.5">
                              <div className="h-1.5 rounded-full" style={{ width: `${Math.min(displayScore, 100)}%`, maxWidth: 60, background: riskColor(displayScore, redThr, amberThr) }} />
                              <span className={`font-semibold ${riskScoreClass(displayScore, redThr, amberThr)}`}>{displayScore}</span>
                            </div>
                          </td>
                        )}
                        <td className="py-2 px-3">
                          <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${riskBadge(row.risk_level)}`}>
                            {row.risk_level}
                          </span>
                        </td>
                        <td className="py-2 px-3 text-tx">{row.total_interviews}</td>
                        <td className="py-2 px-3 text-tx">{row.total_flags}</td>
                        <td className="py-2 px-3 text-tx">{row.flag_rate_pct}%</td>
                        <td className="py-2 px-3 text-tx">{row.fabrication_flags}</td>
                        <td className="py-2 px-3 text-tx">{row.duration_flags}</td>
                        <td className="py-2 px-3 text-tx">{row.straightlining_flags}</td>
                        <td className="py-2 px-3 text-tx">{row.productivity_flags}</td>
                        <td className="py-2 px-3 text-tx">{row.verbatim_flags}</td>
                        {hasDurationData && (
                          <>
                            <td className="py-2 px-3 text-tx">{row.avg_duration != null ? `${row.avg_duration} min` : '—'}</td>
                            <td className="py-2 px-3 text-muted">{row.min_duration != null ? String(row.min_duration) : '—'}</td>
                            <td className="py-2 px-3 text-muted">{row.max_duration != null ? String(row.max_duration) : '—'}</td>
                          </>
                        )}
                        {hasDateData && (
                          <>
                            <td className="py-2 px-3 text-muted text-[10px]">{row.first_interview ? String(row.first_interview).slice(0, 10) : '—'}</td>
                            <td className="py-2 px-3 text-muted text-[10px]">{row.last_interview ? String(row.last_interview).slice(0, 10) : '—'}</td>
                          </>
                        )}
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {/* ── Performance Metrics ──────────────────────────────────────── */}
          {(hasDurationData || hasDateData || productivityMatrix.length > 0) && (
            <div className="card border-line">
              <button
                onClick={() => setShowPerf(o => !o)}
                className="w-full flex items-center justify-between px-4 py-3 text-sm text-tx hover:bg-surface2 transition-colors"
              >
                <span className="flex items-center gap-2">
                  <Activity size={14} className="text-accent" />
                  Performance Metrics
                  {hasDurationData && <span className="text-xs text-muted">· duration stats</span>}
                  {productivityMatrix.length > 0 && <span className="text-xs text-muted">· daily output</span>}
                </span>
                {showPerf ? <ChevronUp size={14} className="text-muted" /> : <ChevronDown size={14} className="text-muted" />}
              </button>
              {showPerf && (
                <div className="border-t border-line px-4 pb-4 pt-3 space-y-4">
                  {hasDurationData && (
                    <div>
                      <h4 className="text-xs font-semibold text-muted uppercase tracking-wide mb-2">Duration Performance</h4>
                      <div className="overflow-x-auto">
                        <table className="w-full text-xs">
                          <thead>
                            <tr className="border-b border-line">
                              {[intColName, 'Total Interviews', 'Avg Duration (min)', 'Min (min)', 'Max (min)',
                                ...(hasDateData ? ['First Interview', 'Last Interview'] : [])
                              ].map(h => (
                                <th key={h} className="text-left py-2 px-3 text-muted font-normal whitespace-nowrap">{h}</th>
                              ))}
                            </tr>
                          </thead>
                          <tbody>
                            {filteredRows.map((row, i) => (
                              <tr key={i} className={`border-b border-line/50 ${row.avg_duration != null && Number(row.avg_duration) < 5 ? 'bg-critical/5' : i % 2 === 0 ? 'bg-surface2/30' : ''}`}>
                                <td className="py-2 px-3 font-medium text-accent">{String(row[intColName] ?? '')}</td>
                                <td className="py-2 px-3 text-tx">{row.total_interviews}</td>
                                <td className="py-2 px-3">
                                  <span className={`font-medium ${row.avg_duration != null && Number(row.avg_duration) < 5 ? 'text-critical' : 'text-tx'}`}>
                                    {row.avg_duration != null ? `${row.avg_duration} min` : '—'}
                                  </span>
                                </td>
                                <td className="py-2 px-3 text-muted">{row.min_duration != null ? `${row.min_duration}` : '—'}</td>
                                <td className="py-2 px-3 text-muted">{row.max_duration != null ? `${row.max_duration}` : '—'}</td>
                                {hasDateData && (
                                  <>
                                    <td className="py-2 px-3 text-muted text-[10px]">{row.first_interview ? String(row.first_interview).slice(0, 10) : '—'}</td>
                                    <td className="py-2 px-3 text-muted text-[10px]">{row.last_interview ? String(row.last_interview).slice(0, 10) : '—'}</td>
                                  </>
                                )}
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}

                  {productivityMatrix.length > 0 && (
                    <div>
                      <h4 className="text-xs font-semibold text-muted uppercase tracking-wide mb-2">Daily Output (Interviews per Day)</h4>
                      <div className="overflow-x-auto">
                        <table className="w-full text-xs">
                          <thead>
                            <tr className="border-b border-line">
                              {Object.keys(productivityMatrix[0] ?? {}).map(h => (
                                <th key={h} className="text-left py-1.5 px-2 text-muted font-normal whitespace-nowrap">{h}</th>
                              ))}
                            </tr>
                          </thead>
                          <tbody>
                            {productivityMatrix.map((row, i) => {
                              const dateKey = Object.keys(row)[0]
                              return (
                                <tr key={i} className="border-b border-line/50 hover:bg-surface2 transition-colors">
                                  {Object.entries(row).map(([k, v]) => (
                                    <td key={k} className={`py-1.5 px-2 ${k === dateKey ? 'text-muted font-medium' : Number(v) >= 10 ? 'text-critical font-medium' : Number(v) >= 5 ? 'text-warning font-medium' : Number(v) > 0 ? 'text-accent' : 'text-muted/40'}`}>
                                      {k === dateKey ? String(v).slice(0, 10) : (Number(v) > 0 ? String(v) : '·')}
                                    </td>
                                  ))}
                                </tr>
                              )
                            })}
                          </tbody>
                        </table>
                        <p className="text-[10px] text-muted mt-2">
                          <span className="text-critical font-medium">≥10</span> = high output &nbsp;
                          <span className="text-warning font-medium">5–9</span> = above average &nbsp;
                          <span className="text-accent">1–4</span> = normal
                        </p>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Bar chart — top 20 */}
          {top20.length > 1 && (
            <div className="card p-4">
              <h3 className="text-sm font-medium text-tx mb-3">Risk Score Chart (top 20)</h3>
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={top20} margin={{ top: 5, right: 20, left: 0, bottom: 60 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1f2330" />
                  <XAxis
                    dataKey={intColName} tick={{ fill: '#8b90a8', fontSize: 10 }}
                    angle={-40} textAnchor="end" interval={0}
                  />
                  <YAxis domain={[0, 110]} tick={{ fill: '#8b90a8', fontSize: 10 }} />
                  <Tooltip {...TOOLTIP_STYLE} />
                  <Bar dataKey="risk_score" radius={[3, 3, 0, 0]}>
                    {top20.map((row, i) => (
                      <Cell key={i} fill={riskColor(row.risk_score, redThr, amberThr)} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Flag rate alerts */}
          <div className="space-y-2">
            <h3 className="text-sm font-medium text-tx">Flag Rate Alerts — threshold: {flagThr}%</h3>
            {typedRows.filter((r) => r.flag_rate_pct > flagThr).length === 0 ? (
              <p className="text-xs text-accent">No interviewers exceed the {flagThr}% flag rate threshold.</p>
            ) : (
              typedRows.filter((r) => r.flag_rate_pct > flagThr).map((row, i) => (
                <div key={i} className="flex items-start gap-2 p-3 rounded-lg bg-warning/5 border border-warning/20 text-xs">
                  <AlertTriangle size={12} className="text-warning shrink-0 mt-0.5" />
                  <span className="text-tx">
                    <button
                      className="font-medium text-accent hover:underline"
                      onClick={() => setProfileRow(row)}
                    >
                      {String(row[intColName])}
                    </button>
                    : {row.flag_rate_pct}% of interviews flagged ({row.total_flags} / {row.total_interviews}) — above {flagThr}% threshold · Risk: <span className="font-medium">{row.risk_score}</span> · {row.risk_level}
                  </span>
                </div>
              ))
            )}
          </div>

          {/* Feedback letter */}
          <div className="card p-4 space-y-3">
            <h3 className="text-sm font-medium text-tx flex items-center gap-1.5">
              <Sparkles size={14} className="text-accent" />
              Interviewer Feedback Letter
            </h3>
            <p className="text-xs text-muted">
              Select an interviewer and generate a structured feedback letter via Groq AI.
              {!groqApiKey && <span className="text-warning ml-1">Set Groq API key in Settings first.</span>}
            </p>
            <div className="flex gap-2 items-end">
              <div className="flex-1 space-y-1">
                <p className="text-xs text-muted">Interviewer</p>
                <select className="w-full" value={selectedInt} onChange={(e) => setItvTabState({ selectedInt: e.target.value })}>
                  {typedRows.map((r) => (
                    <option key={String(r[intColName])} value={String(r[intColName])}>
                      {String(r[intColName])} · Risk: {r.risk_score} ({r.risk_level})
                    </option>
                  ))}
                </select>
              </div>
              <button
                onClick={() => letterMutation.mutate()}
                disabled={!groqApiKey || !selectedInt || letterMutation.isPending}
                className="btn-primary flex items-center gap-1.5 shrink-0"
              >
                <Sparkles size={12} />
                {letterMutation.isPending ? 'Writing…' : 'Generate letter'}
              </button>
            </div>
            {letterMutation.isError && (
              <p className="text-xs text-critical">{(letterMutation.error as Error).message}</p>
            )}
            {letter && (
              <div className="space-y-2">
                <textarea
                  className="w-full h-64 text-xs font-mono bg-surface2 border border-line rounded p-3 resize-y text-tx"
                  value={letter} readOnly
                />
                <button onClick={downloadLetter} className="btn-ghost flex items-center gap-1.5 text-xs">
                  <Download size={12} /> Download letter ({selectedInt})
                </button>
              </div>
            )}
          </div>

          {/* Score methodology */}
          <div className="card border-line">
            <button
              onClick={() => setShowMethods((o) => !o)}
              className="w-full flex items-center justify-between px-4 py-3 text-xs text-muted hover:text-tx"
            >
              <span>Score methodology</span>
              {showMethods ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
            </button>
            {showMethods && (
              <div className="px-4 pb-4 overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-line">
                      {['Component', 'Weight', 'Populated by'].map((h) => (
                        <th key={h} className="text-left py-1.5 px-2 text-muted font-normal">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {[
                      ['Fabrication',       '40%', 'fabrication_check'],
                      ['Duration anomaly',  '25%', 'interviewer_duration_check'],
                      ['Straightlining',    '25%', 'straightlining_check'],
                      ['Productivity',      '10%', 'interviewer_productivity_check'],
                    ].map(([comp, weight, check]) => (
                      <tr key={comp} className="border-b border-line/50">
                        <td className="py-1.5 px-2 text-tx">{comp}</td>
                        <td className="py-1.5 px-2 text-accent font-medium">{weight}</td>
                        <td className="py-1.5 px-2 text-muted font-mono">{check}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <p className="text-xs text-muted mt-2">
                  Each component contributes points proportional to that interviewer's flag rate (flags ÷ total interviews × weight). Scores are summed and capped at 100.
                </p>
                {hasDbMetrics && (
                  <div className="mt-3 pt-3 border-t border-line">
                    <p className="text-xs font-medium text-tx mb-2">QC Score ★ (composite — requires login)</p>
                    <table className="w-full text-xs">
                      <tbody>
                        {[
                          ['Local risk score',        '40%', 'this file'],
                          ['Cross-project flag rate', '30%', 'global database'],
                          ['Back-check error rate',   '20%', 'global database'],
                          ['Listen-in fail rate',     '10%', 'global database'],
                        ].map(([comp, w, src]) => (
                          <tr key={comp} className="border-b border-line/50">
                            <td className="py-1.5 px-2 text-tx">{comp}</td>
                            <td className="py-1.5 px-2 text-accent font-medium">{w}</td>
                            <td className="py-1.5 px-2 text-muted">{src}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  )
}
