import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient, keepPreviousData } from '@tanstack/react-query'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid,
  ResponsiveContainer, Cell, Legend,
} from 'recharts'
import {
  Users, Plus, Trash2, ChevronRight, X, Loader2,
  TrendingUp, AlertTriangle, ChevronDown, ChevronUp, Activity, Download,
} from 'lucide-react'
import { useAppStore } from '../../store/appStore'
import {
  getSupervisors, getInterviewers, getInterviewerMetrics,
  getInterviewerAnalytics, downloadInterviewerReport,
  createSupervisor, deleteSupervisor, upsertInterviewer,
  type Supervisor, type Interviewer, type InterviewerMetrics, type ItvAnalyticsRow,
} from '../../api/dashboard'

const C = {
  accent: '#00B5A3', critical: '#1B2A4A', warning: '#00B5A3',
  muted: '#6B7280', surface: '#FFFFFF', surface2: '#F1F4F8', line: '#E2E6ED',
  tx: '#1B2A4A', info: '#1B2A4A',
}

const TooltipStyle = {
  contentStyle: { backgroundColor: C.surface2, border: `1px solid ${C.line}`, borderRadius: 6, color: C.tx },
  itemStyle: { color: C.tx },
  labelStyle: { color: C.muted },
}

const ADMIN_ROLES = new Set(['qc_executive', 'operations_manager'])

function riskColor(rate: number) {
  if (rate >= 15) return C.critical
  if (rate >= 8) return C.warning
  return C.accent
}

function riskLabel(rate: number) {
  if (rate >= 15) return 'HIGH'
  if (rate >= 8) return 'MED'
  return 'LOW'
}

// ── Interviewer detail modal ───────────────────────────────────────────────────

function InterviewerDetailModal({ code, onClose }: { code: string; onClose: () => void }) {
  const { authToken } = useAppStore()
  const token = authToken ?? ''
  const { data, isLoading } = useQuery({
    queryKey: ['itv-metrics', code],
    queryFn: () => getInterviewerMetrics(code, token),
    enabled: !!token,
  })
  const m = data as InterviewerMetrics | undefined

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm"
      onClick={e => { if (e.target === e.currentTarget) onClose() }}
    >
      <div className="bg-surface border border-line rounded-xl w-full max-w-3xl max-h-[85vh] flex flex-col shadow-2xl">
        <div className="flex items-center justify-between px-5 py-4 border-b border-line shrink-0">
          <div className="flex items-center gap-2">
            <Users size={15} className="text-accent" />
            <span className="font-display font-bold text-sm text-tx">{code}</span>
            {m?.info?.name && <span className="text-muted text-xs">— {m.info.name}</span>}
          </div>
          <button onClick={onClose} className="p-1.5 text-muted hover:text-tx hover:bg-surface2 rounded transition-colors">
            <X size={15} />
          </button>
        </div>
        <div className="overflow-y-auto p-5 space-y-5">
          {isLoading && <div className="flex items-center gap-2 text-muted text-sm"><Loader2 size={14} className="animate-spin" /> Loading…</div>}
          {m && (
            <>
              <div className="card p-3 text-sm">
                <span className="text-muted">Supervisor: </span>
                <span className="text-tx">{m.info?.supervisor_name ?? <span className="text-muted italic">Unassigned</span>}</span>
                {m.info?.region && <span className="text-muted ml-3">Region: <span className="text-tx">{m.info.region}</span></span>}
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                {[
                  { label: 'Total Interviews', value: m.quality.total_interviews ?? 0, color: 'text-tx' },
                  { label: 'Approved', value: m.quality.approved ?? 0, color: 'text-accent' },
                  { label: 'Duration Flags', value: m.quality.duration_flags ?? 0, color: 'text-critical' },
                  { label: 'SL Flags', value: m.quality.sl_flags ?? 0, color: 'text-warning' },
                  { label: 'BC Sessions', value: m.backcheck.bc_count ?? 0, color: 'text-info' },
                  { label: 'BC Errors', value: m.backcheck.total_errors ?? 0, color: 'text-critical' },
                  { label: 'Listen-ins', value: m.listen_in.li_count ?? 0, color: 'text-tx' },
                  { label: 'LI Pass', value: m.listen_in.li_pass ?? 0, color: 'text-accent' },
                ].map(k => (
                  <div key={k.label} className="card p-3">
                    <p className="label mb-0.5">{k.label}</p>
                    <p className={`text-xl font-bold font-display ${k.color}`}>{k.value}</p>
                  </div>
                ))}
              </div>
              {m.by_project.length > 0 && (
                <div className="card p-4">
                  <p className="label mb-3">Performance by Project</p>
                  <ResponsiveContainer width="100%" height={200}>
                    <BarChart data={m.by_project} margin={{ left: -20 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke={C.line} />
                      <XAxis dataKey="project_name" tick={{ fill: C.muted, fontSize: 10 }} />
                      <YAxis tick={{ fill: C.muted, fontSize: 10 }} />
                      <Tooltip {...TooltipStyle} />
                      <Bar dataKey="interviews" name="Interviews" fill={C.accent} radius={[2, 2, 0, 0]} />
                      <Bar dataKey="dur_flags" name="Dur Flags" fill={C.critical} radius={[2, 2, 0, 0]} />
                      <Bar dataKey="sl_flags" name="SL Flags" fill={C.warning} radius={[2, 2, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}

// ── Add forms ──────────────────────────────────────────────────────────────────

function AddInterviewerForm({ supervisors, onClose }: { supervisors: Supervisor[]; onClose: () => void }) {
  const { authToken } = useAppStore()
  const token = authToken ?? ''
  const qc = useQueryClient()
  const [form, setForm] = useState({ interviewer_code: '', name: '', supervisor_id: '', region: '' })
  const mut = useMutation({
    mutationFn: () => upsertInterviewer({
      interviewer_code: form.interviewer_code.trim().toUpperCase(),
      name: form.name.trim() || undefined,
      supervisor_id: form.supervisor_id ? Number(form.supervisor_id) : null,
      region: form.region.trim() || undefined,
    }, token),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['itv-analytics'] }); qc.invalidateQueries({ queryKey: ['dash-interviewers'] }); onClose() },
  })
  return (
    <div className="card p-4 space-y-3">
      <p className="label">Add / Update Interviewer</p>
      <div className="grid grid-cols-2 gap-3">
        {[
          { key: 'interviewer_code', label: 'Code *', placeholder: 'e.g. NB0664' },
          { key: 'name', label: 'Full Name', placeholder: 'Optional' },
          { key: 'region', label: 'Region', placeholder: 'Optional' },
        ].map(f => (
          <div key={f.key}>
            <label className="label mb-1 block">{f.label}</label>
            <input value={(form as any)[f.key]} onChange={e => setForm(p => ({ ...p, [f.key]: e.target.value }))}
              placeholder={f.placeholder} className="w-full bg-surface2 border border-line rounded-lg px-3 py-2 text-sm text-tx placeholder:text-muted" />
          </div>
        ))}
        <div>
          <label className="label mb-1 block">Supervisor</label>
          <select value={form.supervisor_id} onChange={e => setForm(p => ({ ...p, supervisor_id: e.target.value }))}
            className="w-full bg-surface2 border border-line rounded-lg px-3 py-2 text-sm text-tx">
            <option value="">— None —</option>
            {supervisors.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select>
        </div>
      </div>
      <div className="flex items-center gap-3">
        <button onClick={() => mut.mutate()} disabled={!form.interviewer_code.trim() || mut.isPending}
          className="btn-primary flex items-center gap-2">
          {mut.isPending ? <Loader2 size={13} className="animate-spin" /> : <Plus size={13} />} Save
        </button>
        <button onClick={onClose} className="btn-ghost text-sm">Cancel</button>
      </div>
    </div>
  )
}

function AddSupervisorForm({ onClose }: { onClose: () => void }) {
  const { authToken } = useAppStore()
  const token = authToken ?? ''
  const qc = useQueryClient()
  const [form, setForm] = useState({ name: '', email: '', phone: '', region: '' })
  const mut = useMutation({
    mutationFn: () => createSupervisor({ name: form.name.trim(), email: form.email.trim() || null, phone: form.phone.trim() || null, region: form.region.trim() || null }, token),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['dash-supervisors'] }); qc.invalidateQueries({ queryKey: ['itv-analytics'] }); onClose() },
  })
  return (
    <div className="card p-4 space-y-3">
      <p className="label">Add Supervisor</p>
      <div className="grid grid-cols-2 gap-3">
        {[
          { key: 'name', label: 'Full Name *', placeholder: 'Jane Supervisor' },
          { key: 'email', label: 'Email', placeholder: 'jane@example.com' },
          { key: 'phone', label: 'Phone', placeholder: '+254 7xx xxx xxx' },
          { key: 'region', label: 'Region', placeholder: 'Nairobi' },
        ].map(f => (
          <div key={f.key}>
            <label className="label mb-1 block">{f.label}</label>
            <input value={(form as any)[f.key]} onChange={e => setForm(p => ({ ...p, [f.key]: e.target.value }))}
              placeholder={f.placeholder} className="w-full bg-surface2 border border-line rounded-lg px-3 py-2 text-sm text-tx placeholder:text-muted" />
          </div>
        ))}
      </div>
      <div className="flex items-center gap-3">
        <button onClick={() => mut.mutate()} disabled={!form.name.trim() || mut.isPending}
          className="btn-primary flex items-center gap-2">
          {mut.isPending ? <Loader2 size={13} className="animate-spin" /> : <Plus size={13} />} Add Supervisor
        </button>
        <button onClick={onClose} className="btn-ghost text-sm">Cancel</button>
      </div>
    </div>
  )
}

// ── Shared chart card wrapper ──────────────────────────────────────────────────

function ChartCard({ title, icon: Icon, children }: { title: string; icon: React.ElementType; children: React.ReactNode }) {
  return (
    <div className="card p-4 flex flex-col gap-3">
      <div className="flex items-center gap-2">
        <Icon size={13} className="text-accent" />
        <p className="label">{title}</p>
      </div>
      {children}
    </div>
  )
}

// ── Main component ─────────────────────────────────────────────────────────────

export function InterviewerDirectory() {
  const { authUser, authToken } = useAppStore()
  const token = authToken ?? ''
  const qc = useQueryClient()
  const isAdmin = authUser && ADMIN_ROLES.has(authUser.role)

  const [filterProject, setFilterProject] = useState<number | undefined>()
  const [filterSupervisor, setFilterSupervisor] = useState<number | undefined>()
  const [filterRegion, setFilterRegion] = useState<string>('')
  const [filterInterviewer, setFilterInterviewer] = useState<string>('')
  const [registryOpen, setRegistryOpen] = useState(false)
  const [selectedCode, setSelectedCode] = useState<string | null>(null)
  const [showAddItv, setShowAddItv] = useState(false)
  const [showAddSup, setShowAddSup] = useState(false)
  const [downloading, setDownloading] = useState(false)

  const { data: analytics, isLoading, isFetching } = useQuery({
    queryKey: ['itv-analytics', filterProject, filterSupervisor, filterRegion],
    queryFn: () => getInterviewerAnalytics(token, {
      project_id: filterProject,
      supervisor_id: filterSupervisor,
      region: filterRegion || undefined,
    }),
    enabled: !!token,
    placeholderData: keepPreviousData,
  })

  const handleDownload = async () => {
    setDownloading(true)
    try {
      await downloadInterviewerReport(token, {
        project_id: filterProject,
        supervisor_id: filterSupervisor,
        region: filterRegion || undefined,
      })
    } finally {
      setDownloading(false)
    }
  }

  const { data: supervisors = [] } = useQuery({
    queryKey: ['dash-supervisors'],
    queryFn: () => getSupervisors(token),
    enabled: !!token,
  })

  const { data: interviewers = [] } = useQuery({
    queryKey: ['dash-interviewers'],
    queryFn: () => getInterviewers(token),
    enabled: !!token && registryOpen,
  })

  const delSupMut = useMutation({
    mutationFn: (id: number) => deleteSupervisor(id, token),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['dash-supervisors'] }); qc.invalidateQueries({ queryKey: ['itv-analytics'] }) },
  })

  const rows = analytics?.interviewers ?? []
  const bySup = analytics?.by_supervisor ?? []
  const projects = analytics?.projects ?? []
  const regions = [...new Set(rows.map(r => r.region).filter(Boolean))] as string[]

  // KPIs
  const totalActive = rows.filter(r => r.is_active).length
  const withData = rows.filter(r => r.total_interviews > 0)
  const avgFlagRate = withData.length ? Math.round(withData.reduce((s, r) => s + r.flag_rate, 0) / withData.length * 10) / 10 : 0
  const highRisk = rows.filter(r => r.flag_rate >= 15).length
  const totalBcErrors = rows.reduce((s, r) => s + r.bc_errors, 0)

  // Chart data — top 10 by flag rate (only those with interviews)
  const top10 = rows.filter(r => r.total_interviews > 0).slice(0, 10)
  const topFlagged = [...top10].sort((a, b) => b.flag_rate - a.flag_rate).map(r => ({
    label: r.name ? r.name.split(' ')[0] : r.code,
    code: r.code,
    flag_rate: r.flag_rate,
  }))
  const flagBreakdown = top10.map(r => ({
    label: r.name ? r.name.split(' ')[0] : r.code,
    dur: r.duration_flags,
    sl: r.sl_flags,
  }))
  const issueSummary = [...top10]
    .sort((a, b) => (b.bc_errors + b.li_fail + b.cancelled) - (a.bc_errors + a.li_fail + a.cancelled))
    .slice(0, 8)
    .map(r => ({
      label: r.name ? r.name.split(' ')[0] : r.code,
      bc_errors: r.bc_errors,
      li_fail: r.li_fail,
      cancelled: r.cancelled,
    }))

  const hasFilters = filterProject || filterSupervisor || filterRegion || filterInterviewer
  // Client-side interviewer filter applied to table only (charts always show full picture)
  const tableRows = filterInterviewer
    ? rows.filter(r => r.code === filterInterviewer)
    : rows

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-lg font-display font-bold text-tx">Interviewer Performance</h2>
          <p className="text-xs text-muted mt-0.5">
            {rows.length} interviewers · {bySup.length} supervisors
            {isFetching && !isLoading && <span className="ml-2 text-accent animate-pulse">· updating…</span>}
          </p>
        </div>
        <div className="flex gap-2 shrink-0">
          <button
            onClick={handleDownload}
            disabled={downloading || rows.length === 0}
            className="btn-ghost flex items-center gap-1.5 text-xs disabled:opacity-40"
          >
            {downloading ? <Loader2 size={12} className="animate-spin" /> : <Download size={12} />}
            Export Excel
          </button>
          {isAdmin && (
            <>
              <button onClick={() => { setShowAddSup(s => !s); setShowAddItv(false) }} className="btn-ghost flex items-center gap-1.5 text-xs">
                <Plus size={12} /> Supervisor
              </button>
              <button onClick={() => { setShowAddItv(s => !s); setShowAddSup(false) }} className="btn-primary flex items-center gap-1.5 text-xs">
                <Plus size={12} /> Interviewer
              </button>
            </>
          )}
        </div>
      </div>

      {showAddSup && isAdmin && <AddSupervisorForm onClose={() => setShowAddSup(false)} />}
      {showAddItv && isAdmin && <AddInterviewerForm supervisors={supervisors as Supervisor[]} onClose={() => setShowAddItv(false)} />}

      {/* Filters */}
      <div className="flex flex-wrap gap-2 items-center">
        <select value={filterProject ?? ''} onChange={e => setFilterProject(e.target.value ? Number(e.target.value) : undefined)}
          className="bg-surface2 border border-line rounded-lg px-3 py-1.5 text-sm text-tx">
          <option value="">All projects</option>
          {projects.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
        </select>
        <select value={filterSupervisor ?? ''} onChange={e => setFilterSupervisor(e.target.value ? Number(e.target.value) : undefined)}
          className="bg-surface2 border border-line rounded-lg px-3 py-1.5 text-sm text-tx">
          <option value="">All supervisors</option>
          {(supervisors as Supervisor[]).map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
        </select>
        <select value={filterRegion} onChange={e => setFilterRegion(e.target.value)}
          className="bg-surface2 border border-line rounded-lg px-3 py-1.5 text-sm text-tx">
          <option value="">All regions</option>
          {regions.map(r => <option key={r} value={r}>{r}</option>)}
        </select>
        <select value={filterInterviewer} onChange={e => setFilterInterviewer(e.target.value)}
          className="bg-surface2 border border-line rounded-lg px-3 py-1.5 text-sm text-tx">
          <option value="">All interviewers</option>
          {rows.map(r => (
            <option key={r.code} value={r.code}>
              {r.name ? `${r.code} — ${r.name}` : r.code}
            </option>
          ))}
        </select>
        {hasFilters && (
          <button onClick={() => { setFilterProject(undefined); setFilterSupervisor(undefined); setFilterRegion(''); setFilterInterviewer('') }}
            className="text-xs text-muted hover:text-tx transition-colors">
            Clear all
          </button>
        )}
      </div>

      {isLoading ? (
        <div className="flex items-center gap-2 text-muted text-sm py-8">
          <Loader2 size={14} className="animate-spin" /> Loading analytics…
        </div>
      ) : (
        <>
          {/* KPI strip */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {[
              { label: 'Active Interviewers', value: totalActive, icon: Users, color: 'text-tx' },
              { label: 'Avg Flag Rate', value: `${avgFlagRate}%`, icon: TrendingUp, color: avgFlagRate >= 15 ? 'text-critical' : avgFlagRate >= 8 ? 'text-warning' : 'text-accent' },
              { label: 'High Risk', value: highRisk, icon: AlertTriangle, color: highRisk > 0 ? 'text-critical' : 'text-accent' },
              { label: 'Total BC Errors', value: totalBcErrors, icon: Activity, color: totalBcErrors > 20 ? 'text-warning' : 'text-tx' },
            ].map(k => (
              <div key={k.label} className="card p-4 flex items-center gap-3">
                <k.icon size={18} className={k.color} />
                <div>
                  <p className="label mb-0.5">{k.label}</p>
                  <p className={`text-2xl font-bold font-display ${k.color}`}>{k.value}</p>
                </div>
              </div>
            ))}
          </div>

          {rows.filter(r => r.total_interviews > 0).length === 0 ? (
            <div className="card p-6 text-center text-muted text-sm border border-line/50">
              No interviewers with QC records match these filters — try a different project or supervisor combination.
            </div>
          ) : (
            <>
              {/* Chart row 1 */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <ChartCard title="Top Flagged Interviewers" icon={AlertTriangle}>
                  <p className="text-xs text-muted -mt-1">Flag rate = (duration flags + SL flags) / total interviews</p>
                  <ResponsiveContainer width="100%" height={240}>
                    <BarChart layout="vertical" data={topFlagged} margin={{ left: 0, right: 24 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke={C.line} horizontal={false} />
                      <XAxis type="number" tick={{ fill: C.muted, fontSize: 10 }} tickFormatter={v => `${v}%`} domain={[0, 'dataMax + 5']} />
                      <YAxis type="category" dataKey="label" tick={{ fill: C.tx, fontSize: 10 }} width={72} />
                      <Tooltip {...TooltipStyle} formatter={(v: number) => [`${v}%`, 'Flag Rate']} />
                      <Bar dataKey="flag_rate" radius={[0, 3, 3, 0]} maxBarSize={18}>
                        {topFlagged.map((r, i) => <Cell key={i} fill={riskColor(r.flag_rate)} />)}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                  <div className="flex gap-4 text-xs text-muted">
                    {[['HIGH ≥15%', C.critical], ['MED 8–14%', C.warning], ['LOW <8%', C.accent]].map(([l, c]) => (
                      <span key={l as string} className="flex items-center gap-1.5">
                        <span className="w-2.5 h-2.5 rounded-sm shrink-0" style={{ backgroundColor: c as string }} />
                        {l}
                      </span>
                    ))}
                  </div>
                </ChartCard>

                <ChartCard title="Supervisor Flag Rates" icon={Users}>
                  <p className="text-xs text-muted -mt-1">Average flag rate across all interviewers per supervisor</p>
                  <ResponsiveContainer width="100%" height={240}>
                    <BarChart data={bySup} margin={{ left: -12, right: 8 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke={C.line} />
                      <XAxis dataKey="supervisor_name" tick={{ fill: C.muted, fontSize: 9 }}
                        tickFormatter={v => v.split(' ')[0]} />
                      <YAxis tick={{ fill: C.muted, fontSize: 10 }} tickFormatter={v => `${v}%`} />
                      <Tooltip {...TooltipStyle}
                        formatter={(v: number, name: string) => name === 'flag_rate' ? [`${v}%`, 'Flag Rate'] : [v, name]}
                        labelFormatter={l => `Supervisor: ${l}`} />
                      <Bar dataKey="flag_rate" name="Flag Rate" radius={[3, 3, 0, 0]} maxBarSize={40}>
                        {bySup.map((s, i) => <Cell key={i} fill={riskColor(s.flag_rate)} />)}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                  <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted">
                    {bySup.map(s => (
                      <span key={s.supervisor_name} className="flex items-center gap-1">
                        <span className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: riskColor(s.flag_rate) }} />
                        {s.supervisor_name.split(' ')[0]}: {s.flag_rate}% ({s.interviewer_count} itv)
                      </span>
                    ))}
                  </div>
                </ChartCard>
              </div>

              {/* Chart row 2 */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <ChartCard title="Flag Type Breakdown" icon={TrendingUp}>
                  <p className="text-xs text-muted -mt-1">Duration vs straightlining flags per interviewer (top 10)</p>
                  <ResponsiveContainer width="100%" height={220}>
                    <BarChart data={flagBreakdown} margin={{ left: -12, right: 8 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke={C.line} />
                      <XAxis dataKey="label" tick={{ fill: C.muted, fontSize: 9 }} />
                      <YAxis tick={{ fill: C.muted, fontSize: 10 }} />
                      <Tooltip {...TooltipStyle} />
                      <Legend wrapperStyle={{ fontSize: 10, color: C.muted }} />
                      <Bar dataKey="dur" name="Duration Flags" stackId="a" fill={C.critical} />
                      <Bar dataKey="sl" name="SL Flags" stackId="a" fill={C.warning} radius={[3, 3, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </ChartCard>

                <ChartCard title="QC Issue Summary" icon={Activity}>
                  <p className="text-xs text-muted -mt-1">Backcheck errors · listen-in fails · cancelled interviews</p>
                  <ResponsiveContainer width="100%" height={220}>
                    <BarChart data={issueSummary} margin={{ left: -12, right: 8 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke={C.line} />
                      <XAxis dataKey="label" tick={{ fill: C.muted, fontSize: 9 }} />
                      <YAxis tick={{ fill: C.muted, fontSize: 10 }} />
                      <Tooltip {...TooltipStyle} />
                      <Legend wrapperStyle={{ fontSize: 10, color: C.muted }} />
                      <Bar dataKey="bc_errors" name="BC Errors" fill={C.info} radius={[2, 2, 0, 0]} />
                      <Bar dataKey="li_fail" name="LI Fail" fill={C.warning} radius={[2, 2, 0, 0]} />
                      <Bar dataKey="cancelled" name="Cancelled" fill={C.muted} radius={[2, 2, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </ChartCard>
              </div>

              {/* Ranked table — always visible, no toggle needed */}
              <div className="card overflow-hidden">
                <div className="px-4 py-3 border-b border-line flex items-center justify-between">
                  <p className="label">Interviewer Rankings</p>
                  <p className="text-xs text-muted">Sorted by flag rate</p>
                </div>
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-line text-muted bg-surface">
                      {['Interviewer', 'Supervisor', 'Region', 'Interviews', 'Dur Flags', 'SL Flags', 'Flag Rate', 'BC Errors', 'LI Fail', 'Cancelled', 'Risk'].map(h => (
                        <th key={h} className="text-left px-3 py-2.5 whitespace-nowrap font-normal">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {tableRows.map((r: ItvAnalyticsRow) => (
                      <tr key={r.code} onClick={() => setSelectedCode(r.code)}
                        className="border-b border-line/30 hover:bg-surface2/60 cursor-pointer">
                        <td className="px-3 py-2.5">
                          <p className="font-mono text-accent text-xs">{r.code}</p>
                          {r.name && <p className="text-muted text-xs">{r.name}</p>}
                        </td>
                        <td className="px-3 py-2.5 text-muted">{r.supervisor_name ?? '—'}</td>
                        <td className="px-3 py-2.5 text-muted">{r.region ?? '—'}</td>
                        <td className="px-3 py-2.5 text-tx font-medium">{r.total_interviews}</td>
                        <td className="px-3 py-2.5 text-critical">{r.duration_flags || '—'}</td>
                        <td className="px-3 py-2.5 text-warning">{r.sl_flags || '—'}</td>
                        <td className="px-3 py-2.5 font-medium" style={{ color: riskColor(r.flag_rate) }}>
                          {r.total_interviews > 0 ? `${r.flag_rate}%` : '—'}
                        </td>
                        <td className="px-3 py-2.5" style={{ color: r.bc_errors > 0 ? C.info : C.muted }}>{r.bc_errors || '—'}</td>
                        <td className="px-3 py-2.5" style={{ color: r.li_fail > 0 ? C.warning : C.muted }}>{r.li_fail || '—'}</td>
                        <td className="px-3 py-2.5 text-muted">{r.cancelled || '—'}</td>
                        <td className="px-3 py-2.5">
                          {r.total_interviews > 0 ? (
                            <span className="text-xs font-bold" style={{ color: riskColor(r.flag_rate) }}>
                              {riskLabel(r.flag_rate)}
                            </span>
                          ) : <span className="text-muted">—</span>}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}

          {/* Collapsible registry (add/edit + full list) */}
          <div className="card overflow-hidden">
            <button
              onClick={() => setRegistryOpen(o => !o)}
              className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-surface2/40 transition-colors"
            >
              <div className="flex items-center gap-2">
                <Users size={13} className="text-muted" />
                <span className="label">Interviewer Registry</span>
                <span className="text-xs text-muted">({(interviewers as Interviewer[]).length || rows.length} total)</span>
              </div>
              {registryOpen ? <ChevronUp size={14} className="text-muted" /> : <ChevronDown size={14} className="text-muted" />}
            </button>

            {registryOpen && (
              <div className="border-t border-line">
                {/* Supervisors grid */}
                {(supervisors as Supervisor[]).length > 0 && (
                  <div className="p-4 border-b border-line">
                    <p className="label mb-2">Supervisors</p>
                    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2">
                      {(supervisors as Supervisor[]).map(s => {
                        const count = rows.filter(i => i.supervisor_id === s.id).length
                        return (
                          <div key={s.id} className="bg-surface2 border border-line rounded-lg p-2.5 flex items-start justify-between gap-1">
                            <div>
                              <p className="text-xs text-tx font-medium">{s.name}</p>
                              <p className="text-xs text-accent mt-0.5">{count} itv</p>
                            </div>
                            {isAdmin && (
                              <button onClick={() => delSupMut.mutate(s.id)} className="p-0.5 text-muted hover:text-critical transition-colors shrink-0">
                                <Trash2 size={11} />
                              </button>
                            )}
                          </div>
                        )
                      })}
                    </div>
                  </div>
                )}

                {/* Full interviewer list */}
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-line text-muted bg-surface">
                      {['Code', 'Name', 'Supervisor', 'Region', 'Status', ''].map(h => (
                        <th key={h} className="text-left px-4 py-2 font-normal">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {(interviewers as Interviewer[]).map(itv => (
                      <tr key={itv.id} onClick={() => setSelectedCode(itv.interviewer_code)}
                        className="border-b border-line/30 hover:bg-surface2/60 cursor-pointer">
                        <td className="px-4 py-2 font-mono text-accent">{itv.interviewer_code}</td>
                        <td className="px-4 py-2 text-tx">{itv.name ?? <span className="text-muted italic">—</span>}</td>
                        <td className="px-4 py-2 text-muted">{itv.supervisor_name ?? <span className="italic">Unassigned</span>}</td>
                        <td className="px-4 py-2 text-muted">{itv.region ?? '—'}</td>
                        <td className="px-4 py-2">
                          <span className={`text-xs ${itv.is_active ? 'text-accent' : 'text-muted line-through'}`}>
                            {itv.is_active ? 'Active' : 'Inactive'}
                          </span>
                        </td>
                        <td className="px-4 py-2"><ChevronRight size={12} className="text-muted" /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}

      {selectedCode && <InterviewerDetailModal code={selectedCode} onClose={() => setSelectedCode(null)} />}
    </div>
  )
}
