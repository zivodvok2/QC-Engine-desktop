import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient, keepPreviousData } from '@tanstack/react-query'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid,
  ResponsiveContainer, Cell, Legend,
} from 'recharts'
import {
  Users, Plus, Trash2, X, Loader2,
  TrendingUp, AlertTriangle, ChevronDown, ChevronUp, Activity, Download,
  ShieldOff, AlertCircle, ArrowUpCircle, ShieldCheck, ShieldAlert,
} from 'lucide-react'
import { useAppStore } from '../../store/appStore'
import {
  getSupervisors, getInterviewers, getInterviewerMetrics,
  getInterviewerAnalytics, downloadInterviewerReport,
  createSupervisor, deleteSupervisor, upsertInterviewer, dedupSupervisors,
  blockInterviewer, unblockInterviewer, warnInterviewer, escalateInterviewer,
  getInterviewerActions,
  type Supervisor, type Interviewer, type InterviewerMetrics, type ItvAnalyticsRow,
  type InterviewerAction,
} from '../../api/dashboard'

const C = {
  accent: '#00B5A3', muted: '#6B7280', surface: '#FFFFFF',
  surface2: '#F1F4F8', line: '#E2E6ED', tx: '#1B2A4A',
  // True RAG colors
  red: '#EF4444', orange: '#F97316', green: '#10B981',
}

const TooltipStyle = {
  contentStyle: { backgroundColor: C.surface2, border: `1px solid ${C.line}`, borderRadius: 6, color: C.tx },
  itemStyle: { color: C.tx },
  labelStyle: { color: C.muted },
}

const ADMIN_ROLES = new Set(['qc_executive', 'operations_manager'])

function riskColor(rate: number) {
  if (rate >= 15) return C.red
  if (rate >= 8) return C.orange
  return C.green
}

function riskLabel(rate: number) {
  if (rate >= 15) return 'HIGH RISK'
  if (rate >= 8) return 'MEDIUM'
  return 'LOW RISK'
}

function RiskBadge({ rate, interviews }: { rate: number; interviews: number }) {
  if (interviews === 0) return <span className="text-xs text-muted">—</span>
  const color = riskColor(rate)
  const label = riskLabel(rate)
  return (
    <span
      className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold tracking-wide"
      style={{ backgroundColor: `${color}20`, color, border: `1px solid ${color}50` }}
    >
      <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ backgroundColor: color }} />
      {label}
    </span>
  )
}

// ── Interviewer action modal ────────────────────────────────────────────────────

type ActionType = 'block' | 'unblock' | 'warn' | 'escalate'

function ActionModal({
  code,
  isBlocked,
  onClose,
}: {
  code: string
  isBlocked: boolean
  onClose: () => void
}) {
  const { authToken } = useAppStore()
  const token = authToken ?? ''
  const qc = useQueryClient()
  const [action, setAction] = useState<ActionType | null>(null)
  const [message, setMessage] = useState('')
  const [notifyEmail, setNotifyEmail] = useState(false)

  const { data: history = [] } = useQuery({
    queryKey: ['itv-actions', code],
    queryFn: () => getInterviewerActions(code, token),
    enabled: !!token,
  })

  const mut = useMutation({
    mutationFn: async () => {
      if (!action) return
      if (action === 'block') await blockInterviewer(code, message || undefined, token)
      else if (action === 'unblock') await unblockInterviewer(code, token)
      else if (action === 'warn') await warnInterviewer(code, message || undefined, notifyEmail, token)
      else if (action === 'escalate') await escalateInterviewer(code, message || undefined, token)
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['itv-analytics'] })
      qc.invalidateQueries({ queryKey: ['itv-actions', code] })
      setAction(null)
      setMessage('')
    },
  })

  const actionConfig: Record<ActionType, { label: string; color: string; icon: React.ElementType; desc: string }> = {
    block: { label: 'Block Interviewer', color: C.red, icon: ShieldOff, desc: 'Prevents this interviewer from being assigned to future projects.' },
    unblock: { label: 'Remove Block', color: C.green, icon: ShieldCheck, desc: 'Re-activates this interviewer and allows project assignment.' },
    warn: { label: 'Send Warning', color: C.orange, icon: AlertCircle, desc: 'Records a formal warning. Optionally emails their supervisor.' },
    escalate: { label: 'Escalate to Senior Manager', color: C.orange, icon: ArrowUpCircle, desc: 'Escalates this interviewer\'s issues to a senior manager for review.' },
  }

  const ACTION_LABELS: Record<string, string> = {
    block: 'Blocked', unblock: 'Unblocked', warning: 'Warning Issued', escalation: 'Escalated',
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm"
      onClick={e => { if (e.target === e.currentTarget) onClose() }}
    >
      <div className="bg-surface border border-line rounded-xl w-full max-w-lg shadow-2xl flex flex-col max-h-[85vh]">
        <div className="flex items-center justify-between px-5 py-4 border-b border-line shrink-0">
          <div className="flex items-center gap-2">
            <ShieldOff size={14} className="text-muted" />
            <span className="font-bold text-sm text-tx">Manage Interviewer: {code}</span>
          </div>
          <button onClick={onClose} className="p-1.5 text-muted hover:text-tx rounded transition-colors">
            <X size={14} />
          </button>
        </div>

        <div className="overflow-y-auto p-5 space-y-4">
          {/* Action buttons */}
          {!action ? (
            <div className="grid grid-cols-2 gap-3">
              {(isBlocked ? ['unblock', 'warn', 'escalate'] : ['block', 'warn', 'escalate']).map((a) => {
                const cfg = actionConfig[a as ActionType]
                const Icon = cfg.icon
                return (
                  <button
                    key={a}
                    onClick={() => setAction(a as ActionType)}
                    className="flex flex-col items-start gap-1.5 p-3 rounded-lg border transition-all hover:shadow-sm text-left"
                    style={{ borderColor: `${cfg.color}40`, backgroundColor: `${cfg.color}08` }}
                  >
                    <div className="flex items-center gap-2">
                      <Icon size={14} style={{ color: cfg.color }} />
                      <span className="text-xs font-bold" style={{ color: cfg.color }}>{cfg.label}</span>
                    </div>
                    <p className="text-[10px] text-muted leading-tight">{cfg.desc}</p>
                  </button>
                )
              })}
            </div>
          ) : (
            <div className="space-y-3">
              <div className="flex items-center gap-2 p-3 rounded-lg" style={{ backgroundColor: `${actionConfig[action].color}10` }}>
                {React.createElement(actionConfig[action].icon, { size: 14, style: { color: actionConfig[action].color } })}
                <span className="text-sm font-bold" style={{ color: actionConfig[action].color }}>
                  {actionConfig[action].label}
                </span>
              </div>

              {action !== 'unblock' && (
                <div>
                  <label className="text-xs text-muted block mb-1">
                    {action === 'block' ? 'Reason for blocking (optional)' :
                     action === 'warn' ? 'Warning details' : 'Escalation notes'}
                  </label>
                  <textarea
                    value={message}
                    onChange={e => setMessage(e.target.value)}
                    rows={3}
                    placeholder="Add details here…"
                    className="w-full bg-surface2 border border-line rounded-lg px-3 py-2 text-sm text-tx placeholder:text-muted resize-none"
                  />
                </div>
              )}

              {action === 'warn' && (
                <label className="flex items-center gap-2 text-xs text-tx cursor-pointer">
                  <input type="checkbox" checked={notifyEmail} onChange={e => setNotifyEmail(e.target.checked)} className="rounded" />
                  Send email notification to supervisor
                </label>
              )}

              <div className="flex gap-2">
                <button
                  onClick={() => mut.mutate()}
                  disabled={mut.isPending}
                  className="btn-primary flex items-center gap-2 text-sm"
                  style={{ backgroundColor: actionConfig[action].color, borderColor: actionConfig[action].color }}
                >
                  {mut.isPending ? <Loader2 size={13} className="animate-spin" /> : null}
                  Confirm
                </button>
                <button onClick={() => { setAction(null); setMessage('') }} className="btn-ghost text-sm">Back</button>
              </div>
            </div>
          )}

          {/* Action history */}
          {(history as InterviewerAction[]).length > 0 && (
            <div className="border-t border-line pt-4">
              <p className="text-xs text-muted font-medium mb-2">Action History</p>
              <div className="space-y-2">
                {(history as InterviewerAction[]).map(h => (
                  <div key={h.id} className="flex items-start gap-2 text-xs">
                    <span
                      className="px-1.5 py-0.5 rounded text-[10px] font-bold shrink-0 mt-0.5"
                      style={{
                        backgroundColor: h.action_type === 'block' ? `${C.red}20` :
                          h.action_type === 'warning' ? `${C.orange}20` :
                          h.action_type === 'escalation' ? `${C.orange}15` : `${C.green}20`,
                        color: h.action_type === 'block' ? C.red :
                          h.action_type === 'warning' ? C.orange :
                          h.action_type === 'escalation' ? C.orange : C.green,
                      }}
                    >
                      {ACTION_LABELS[h.action_type] ?? h.action_type}
                    </span>
                    <div>
                      <span className="text-muted">{new Date(h.created_at).toLocaleDateString()}</span>
                      {h.performed_by_name && <span className="text-muted ml-1">by {h.performed_by_name}</span>}
                      {h.message && <p className="text-tx mt-0.5 leading-tight">{h.message}</p>}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
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
                      <Bar dataKey="dur_flags" name="Dur Flags" fill={C.red} radius={[2, 2, 0, 0]} />
                      <Bar dataKey="sl_flags" name="SL Flags" fill={C.orange} radius={[2, 2, 0, 0]} />
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
  const [preset, setPreset] = useState<'all' | 'high' | 'medium' | 'issues' | 'blocked'>('all')
  const [sortCol, setSortCol] = useState<string>('flag_rate')
  const [sortDir, setSortDir] = useState<'desc' | 'asc'>('desc')
  const [registryOpen, setRegistryOpen] = useState(false)
  const [selectedCode, setSelectedCode] = useState<string | null>(null)
  const [managingCode, setManagingCode] = useState<string | null>(null)
  const [showAddItv, setShowAddItv] = useState(false)
  const [showAddSup, setShowAddSup] = useState(false)
  const [downloading, setDownloading] = useState(false)
  const [dedupMsg, setDedupMsg] = useState<string | null>(null)

  // Filtered analytics (used for main display)
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

  // Unfiltered analytics — powers dropdowns so options never disappear when filtering
  const { data: allAnalytics } = useQuery({
    queryKey: ['itv-analytics-all'],
    queryFn: () => getInterviewerAnalytics(token, {}),
    enabled: !!token,
    staleTime: 60_000,
  })

  // Always-loaded interviewers list for accurate supervisor counts
  const { data: interviewers = [] } = useQuery({
    queryKey: ['dash-interviewers'],
    queryFn: () => getInterviewers(token),
    enabled: !!token,
  })

  // Single-interviewer detail (only when one is selected from filter)
  const { data: singleMetrics, isLoading: singleLoading } = useQuery({
    queryKey: ['itv-metrics', filterInterviewer],
    queryFn: () => getInterviewerMetrics(filterInterviewer, token),
    enabled: !!token && !!filterInterviewer,
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

  const delSupMut = useMutation({
    mutationFn: (id: number) => deleteSupervisor(id, token),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['dash-supervisors'] }); qc.invalidateQueries({ queryKey: ['itv-analytics'] }); qc.invalidateQueries({ queryKey: ['itv-analytics-all'] }) },
  })

  const dedupMut = useMutation({
    mutationFn: () => dedupSupervisors(token),
    onSuccess: (result) => {
      setDedupMsg(`Cleaned up ${result.supervisors_removed} duplicate supervisor(s) across ${result.groups_merged} name(s).`)
      qc.invalidateQueries({ queryKey: ['dash-supervisors'] })
      qc.invalidateQueries({ queryKey: ['itv-analytics'] })
      qc.invalidateQueries({ queryKey: ['itv-analytics-all'] })
      qc.invalidateQueries({ queryKey: ['dash-interviewers'] })
    },
  })

  const rows = analytics?.interviewers ?? []
  const bySup = analytics?.by_supervisor ?? []
  const projects = analytics?.projects ?? []

  // Dropdown options always from unfiltered data so they never disappear
  const allRows = allAnalytics?.interviewers ?? []
  const regions = [...new Set(allRows.map(r => r.region).filter(Boolean))].sort() as string[]
  const allInterviewerOptions = [...allRows].sort((a, b) =>
    (a.name ?? a.code).localeCompare(b.name ?? b.code)
  )

  // KPIs
  const totalActive = rows.filter(r => r.is_active).length
  const withData = rows.filter(r => r.total_interviews > 0)
  const avgFlagRate = withData.length ? Math.round(withData.reduce((s, r) => s + r.flag_rate, 0) / withData.length * 10) / 10 : 0
  const highRisk = rows.filter(r => r.flag_rate >= 15).length
  const totalBcErrors = rows.reduce((s, r) => s + r.bc_errors, 0)
  const blocked = rows.filter(r => r.is_blocked).length

  // "Needs Attention" — high risk with no action in last 30 days (simple heuristic: high risk & active)
  const needsAttention = rows.filter(r => r.flag_rate >= 15 && r.is_active && !r.is_blocked && r.total_interviews > 0)

  // Chart data — top 10 by flag rate
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

  const hasFilters = !!(filterProject || filterSupervisor || filterRegion || filterInterviewer || preset !== 'all')

  // Preset filter
  const presetFilter = (r: ItvAnalyticsRow) => {
    if (preset === 'high') return r.flag_rate >= 15
    if (preset === 'medium') return r.flag_rate >= 8 && r.flag_rate < 15
    if (preset === 'issues') return r.duration_flags > 0 || r.sl_flags > 0 || r.bc_errors > 0 || r.li_fail > 0
    if (preset === 'blocked') return !!r.is_blocked
    return true
  }

  // Sort helper
  const sortFn = (a: ItvAnalyticsRow, b: ItvAnalyticsRow) => {
    const numCols = ['total_interviews','flag_rate','duration_flags','sl_flags','bc_errors','li_fail','cancelled','avg_duration']
    const av = numCols.includes(sortCol) ? (Number((a as any)[sortCol]) || 0) : String((a as any)[sortCol] ?? '')
    const bv = numCols.includes(sortCol) ? (Number((b as any)[sortCol]) || 0) : String((b as any)[sortCol] ?? '')
    const cmp = typeof av === 'number' ? av - (bv as number) : (av as string).localeCompare(bv as string)
    return sortDir === 'desc' ? -cmp : cmp
  }

  const tableRows = [...rows]
    .filter(r => !filterInterviewer || r.code === filterInterviewer)
    .filter(presetFilter)
    .sort(sortFn)

  const toggleSort = (col: string) => {
    if (sortCol === col) setSortDir(d => d === 'desc' ? 'asc' : 'desc')
    else { setSortCol(col); setSortDir('desc') }
  }

  const SortArrow = ({ col }: { col: string }) => (
    <span className="ml-0.5 text-[9px]">
      {sortCol === col ? (sortDir === 'desc' ? '↓' : '↑') : <span className="opacity-30">↕</span>}
    </span>
  )

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
              <button
                onClick={() => dedupMut.mutate()}
                disabled={dedupMut.isPending}
                className="btn-ghost flex items-center gap-1.5 text-xs text-muted"
                title="Remove duplicate supervisors"
              >
                {dedupMut.isPending ? <Loader2 size={12} className="animate-spin" /> : <ShieldAlert size={12} />}
                Dedup
              </button>
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
          {allInterviewerOptions.map(r => (
            <option key={r.code} value={r.code}>
              {r.name ? `${r.code} — ${r.name}` : r.code}
            </option>
          ))}
        </select>
        {hasFilters && (
          <button onClick={() => { setFilterProject(undefined); setFilterSupervisor(undefined); setFilterRegion(''); setFilterInterviewer(''); setPreset('all') }}
            className="text-xs text-muted hover:text-tx transition-colors">
            Clear all
          </button>
        )}
      </div>

      {/* Preset quick-filter buttons */}
      <div className="flex flex-wrap gap-2 items-center">
        {([
          { key: 'all', label: 'All' },
          { key: 'high', label: 'High Risk', color: C.red },
          { key: 'medium', label: 'Medium Risk', color: C.orange },
          { key: 'issues', label: 'Has Issues', color: C.orange },
          { key: 'blocked', label: 'Blocked', color: C.muted },
        ] as { key: typeof preset; label: string; color?: string }[]).map(p => (
          <button
            key={p.key}
            onClick={() => setPreset(p.key)}
            className="px-3 py-1 rounded-full text-xs font-medium border transition-all"
            style={preset === p.key
              ? { backgroundColor: p.color ?? C.accent, color: '#fff', borderColor: p.color ?? C.accent }
              : { backgroundColor: 'transparent', color: p.color ?? C.muted, borderColor: `${p.color ?? C.muted}40` }
            }
          >
            {p.label}
            {p.key === 'high' && highRisk > 0 && (
              <span className="ml-1.5 bg-white/30 rounded-full px-1.5 py-0.5 text-[9px] font-bold">{highRisk}</span>
            )}
            {p.key === 'blocked' && blocked > 0 && (
              <span className="ml-1.5 bg-white/30 rounded-full px-1.5 py-0.5 text-[9px] font-bold">{blocked}</span>
            )}
          </button>
        ))}
      </div>

      {/* Needs Attention alert strip */}
      {needsAttention.length > 0 && preset === 'all' && !filterInterviewer && (
        <div className="rounded-lg border p-3 flex flex-col gap-2" style={{ borderColor: `${C.red}40`, backgroundColor: `${C.red}08` }}>
          <div className="flex items-center gap-2">
            <AlertTriangle size={13} style={{ color: C.red }} />
            <span className="text-xs font-bold" style={{ color: C.red }}>
              {needsAttention.length} interviewer{needsAttention.length > 1 ? 's' : ''} need attention
            </span>
            <span className="text-xs text-muted">— high risk, active, not yet actioned</span>
          </div>
          <div className="flex flex-wrap gap-2">
            {needsAttention.slice(0, 8).map(r => (
              <button
                key={r.code}
                onClick={() => setManagingCode(r.code)}
                className="flex items-center gap-1.5 px-2 py-1 rounded border text-xs"
                style={{ borderColor: `${C.red}40`, backgroundColor: `${C.red}10`, color: C.red }}
              >
                <span className="font-mono font-semibold">{r.code}</span>
                <span className="text-[10px]">{r.flag_rate}%</span>
              </button>
            ))}
            {needsAttention.length > 8 && (
              <span className="text-xs text-muted self-center">+{needsAttention.length - 8} more</span>
            )}
          </div>
        </div>
      )}

      {/* Dedup result message */}
      {dedupMsg && (
        <div className="text-xs text-accent bg-accent/10 border border-accent/30 rounded-lg px-3 py-2 flex items-center justify-between">
          <span>{dedupMsg}</span>
          <button onClick={() => setDedupMsg(null)} className="ml-4 text-muted hover:text-tx"><X size={12} /></button>
        </div>
      )}

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

          {/* Single-interviewer expanded profile (Issue 1) */}
          {filterInterviewer ? (
            <div className="space-y-4">
              {singleLoading ? (
                <div className="card p-8 flex items-center justify-center gap-2 text-muted text-sm">
                  <Loader2 size={14} className="animate-spin" /> Loading profile…
                </div>
              ) : singleMetrics ? (
                <>
                  <div className="card p-4">
                    <div className="flex items-start justify-between">
                      <div>
                        <div className="flex items-center gap-3">
                          <span className="font-mono text-accent font-bold text-base">{filterInterviewer}</span>
                          {(singleMetrics as any).info?.name && (
                            <span className="text-sm text-tx font-medium">{(singleMetrics as any).info.name}</span>
                          )}
                          <RiskBadge
                            rate={(singleMetrics as any).quality?.total_interviews > 0
                              ? Math.round(((((singleMetrics as any).quality?.duration_flags ?? 0) + ((singleMetrics as any).quality?.sl_flags ?? 0)) / (singleMetrics as any).quality.total_interviews) * 100)
                              : 0}
                            interviews={(singleMetrics as any).quality?.total_interviews ?? 0}
                          />
                        </div>
                        <div className="flex gap-4 mt-1 text-xs text-muted">
                          {(singleMetrics as any).info?.supervisor_name && (
                            <span>Supervisor: <span className="text-tx">{(singleMetrics as any).info.supervisor_name}</span></span>
                          )}
                          {(singleMetrics as any).info?.region && (
                            <span>Region: <span className="text-tx">{(singleMetrics as any).info.region}</span></span>
                          )}
                        </div>
                      </div>
                      {isAdmin && (
                        <button
                          onClick={() => setManagingCode(filterInterviewer)}
                          className="btn-ghost text-xs flex items-center gap-1.5"
                          style={{ color: C.red }}
                        >
                          <ShieldAlert size={12} /> Manage
                        </button>
                      )}
                    </div>
                  </div>

                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                    {[
                      { label: 'Total Interviews', value: (singleMetrics as any).quality?.total_interviews ?? 0, color: C.tx },
                      { label: 'Duration Flags', value: (singleMetrics as any).quality?.duration_flags ?? 0, color: C.red },
                      { label: 'SL Flags', value: (singleMetrics as any).quality?.sl_flags ?? 0, color: C.orange },
                      { label: 'Approved', value: (singleMetrics as any).quality?.approved ?? 0, color: C.green },
                      { label: 'BC Sessions', value: (singleMetrics as any).backcheck?.bc_count ?? 0, color: C.tx },
                      { label: 'BC Errors', value: (singleMetrics as any).backcheck?.total_errors ?? 0, color: C.red },
                      { label: 'Listen-ins', value: (singleMetrics as any).listen_in?.li_count ?? 0, color: C.tx },
                      { label: 'LI Pass', value: (singleMetrics as any).listen_in?.li_pass ?? 0, color: C.green },
                    ].map(k => (
                      <div key={k.label} className="card p-3">
                        <p className="label mb-0.5">{k.label}</p>
                        <p className="text-xl font-bold font-display" style={{ color: k.color }}>{k.value}</p>
                      </div>
                    ))}
                  </div>

                  {(singleMetrics as any).by_project?.length > 0 && (
                    <div className="card p-4">
                      <p className="label mb-3">Performance by Project</p>
                      <ResponsiveContainer width="100%" height={220}>
                        <BarChart data={(singleMetrics as any).by_project} margin={{ left: -20 }}>
                          <CartesianGrid strokeDasharray="3 3" stroke={C.line} />
                          <XAxis dataKey="project_name" tick={{ fill: C.muted, fontSize: 10 }} />
                          <YAxis tick={{ fill: C.muted, fontSize: 10 }} />
                          <Tooltip {...TooltipStyle} />
                          <Legend wrapperStyle={{ fontSize: 10, color: C.muted }} verticalAlign="top" />
                          <Bar dataKey="interviews" name="Interviews" fill={C.accent} radius={[2, 2, 0, 0]} />
                          <Bar dataKey="dur_flags" name="Dur Flags" fill={C.red} radius={[2, 2, 0, 0]} />
                          <Bar dataKey="sl_flags" name="SL Flags" fill={C.orange} radius={[2, 2, 0, 0]} />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  )}
                </>
              ) : (
                <div className="card p-6 text-center text-muted text-sm">
                  No QC data found for interviewer {filterInterviewer}.
                </div>
              )}
            </div>
          ) : rows.filter(r => r.total_interviews > 0).length === 0 ? (
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
                    {[['HIGH ≥15%', C.red], ['MEDIUM 8–14%', C.orange], ['LOW <8%', C.green]].map(([l, c]) => (
                      <span key={l as string} className="flex items-center gap-1.5">
                        <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ backgroundColor: c as string }} />
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
                      <Bar dataKey="dur" name="Duration Flags" stackId="a" fill={C.red} />
                      <Bar dataKey="sl" name="SL Flags" stackId="a" fill={C.orange} radius={[3, 3, 0, 0]} />
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
                      <Bar dataKey="bc_errors" name="BC Errors" fill={C.orange} radius={[2, 2, 0, 0]} />
                      <Bar dataKey="li_fail" name="LI Fail" fill={C.red} radius={[2, 2, 0, 0]} />
                      <Bar dataKey="cancelled" name="Cancelled" fill={C.muted} radius={[2, 2, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </ChartCard>
              </div>

              {/* Ranked table — always visible, no toggle needed */}
              <div className="card overflow-hidden">
                <div className="px-4 py-3 border-b border-line flex items-center justify-between">
                  <p className="label">Interviewer Rankings</p>
                  <p className="text-xs text-muted">{tableRows.length} shown · click column to sort · click row for details</p>
                </div>
                <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-line text-muted bg-surface2">
                      <th className="text-left px-3 py-2.5 whitespace-nowrap font-medium text-[10px] uppercase tracking-wide">Risk</th>
                      <th className="text-left px-3 py-2.5 whitespace-nowrap font-medium text-[10px] uppercase tracking-wide cursor-pointer hover:text-tx select-none" onClick={() => toggleSort('name')}>
                        Interviewer <SortArrow col="name" />
                      </th>
                      <th className="text-left px-3 py-2.5 whitespace-nowrap font-medium text-[10px] uppercase tracking-wide cursor-pointer hover:text-tx select-none" onClick={() => toggleSort('supervisor_name')}>
                        Supervisor <SortArrow col="supervisor_name" />
                      </th>
                      <th className="text-left px-3 py-2.5 whitespace-nowrap font-medium text-[10px] uppercase tracking-wide">Region</th>
                      <th className="text-left px-3 py-2.5 whitespace-nowrap font-medium text-[10px] uppercase tracking-wide cursor-pointer hover:text-tx select-none" onClick={() => toggleSort('total_interviews')}>
                        Interviews <SortArrow col="total_interviews" />
                      </th>
                      <th className="text-left px-3 py-2.5 whitespace-nowrap font-medium text-[10px] uppercase tracking-wide cursor-pointer hover:text-tx select-none" onClick={() => toggleSort('duration_flags')}>
                        Dur Flags <SortArrow col="duration_flags" />
                      </th>
                      <th className="text-left px-3 py-2.5 whitespace-nowrap font-medium text-[10px] uppercase tracking-wide cursor-pointer hover:text-tx select-none" onClick={() => toggleSort('sl_flags')}>
                        SL Flags <SortArrow col="sl_flags" />
                      </th>
                      <th className="text-left px-3 py-2.5 whitespace-nowrap font-medium text-[10px] uppercase tracking-wide cursor-pointer hover:text-tx select-none" onClick={() => toggleSort('flag_rate')}>
                        Flag Rate <SortArrow col="flag_rate" />
                      </th>
                      <th className="text-left px-3 py-2.5 whitespace-nowrap font-medium text-[10px] uppercase tracking-wide cursor-pointer hover:text-tx select-none" onClick={() => toggleSort('bc_errors')}>
                        BC Errors <SortArrow col="bc_errors" />
                      </th>
                      <th className="text-left px-3 py-2.5 whitespace-nowrap font-medium text-[10px] uppercase tracking-wide cursor-pointer hover:text-tx select-none" onClick={() => toggleSort('li_fail')}>
                        LI Fail <SortArrow col="li_fail" />
                      </th>
                      <th className="text-left px-3 py-2.5 whitespace-nowrap font-medium text-[10px] uppercase tracking-wide cursor-pointer hover:text-tx select-none" onClick={() => toggleSort('cancelled')}>
                        Cancelled <SortArrow col="cancelled" />
                      </th>
                      {isAdmin && <th className="text-left px-3 py-2.5 whitespace-nowrap font-medium text-[10px] uppercase tracking-wide">Actions</th>}
                    </tr>
                  </thead>
                  <tbody>
                    {tableRows.map((r: ItvAnalyticsRow) => (
                      <tr key={r.code}
                        className={`border-b border-line/30 hover:bg-surface2/60 ${r.is_blocked ? 'opacity-60 bg-red-50/30' : ''}`}>
                        <td className="px-3 py-2.5" onClick={() => setSelectedCode(r.code)}>
                          <RiskBadge rate={r.flag_rate} interviews={r.total_interviews} />
                          {r.is_blocked ? (
                            <span className="mt-1 flex items-center gap-1 text-[9px] font-bold uppercase" style={{ color: C.red }}>
                              <ShieldOff size={9} /> Blocked
                            </span>
                          ) : null}
                        </td>
                        <td className="px-3 py-2.5 cursor-pointer" onClick={() => setSelectedCode(r.code)}>
                          <p className="font-mono text-accent text-xs font-semibold">{r.code}</p>
                          {r.name && <p className="text-muted text-[10px]">{r.name}</p>}
                        </td>
                        <td className="px-3 py-2.5 text-muted cursor-pointer" onClick={() => setSelectedCode(r.code)}>{r.supervisor_name ?? '—'}</td>
                        <td className="px-3 py-2.5 text-muted cursor-pointer" onClick={() => setSelectedCode(r.code)}>{r.region ?? '—'}</td>
                        <td className="px-3 py-2.5 text-tx font-medium cursor-pointer" onClick={() => setSelectedCode(r.code)}>{r.total_interviews}</td>
                        <td className="px-3 py-2.5 cursor-pointer" onClick={() => setSelectedCode(r.code)}
                          style={{ color: r.duration_flags > 0 ? C.red : C.muted }}>
                          {r.duration_flags || '—'}
                        </td>
                        <td className="px-3 py-2.5 cursor-pointer" onClick={() => setSelectedCode(r.code)}
                          style={{ color: r.sl_flags > 0 ? C.orange : C.muted }}>
                          {r.sl_flags || '—'}
                        </td>
                        <td className="px-3 py-2.5 font-bold cursor-pointer" onClick={() => setSelectedCode(r.code)}
                          style={{ color: r.total_interviews > 0 ? riskColor(r.flag_rate) : C.muted }}>
                          {r.total_interviews > 0 ? `${r.flag_rate}%` : '—'}
                        </td>
                        <td className="px-3 py-2.5 cursor-pointer" onClick={() => setSelectedCode(r.code)}
                          style={{ color: r.bc_errors > 0 ? C.orange : C.muted }}>
                          {r.bc_errors || '—'}
                        </td>
                        <td className="px-3 py-2.5 cursor-pointer" onClick={() => setSelectedCode(r.code)}
                          style={{ color: r.li_fail > 0 ? C.orange : C.muted }}>
                          {r.li_fail || '—'}
                        </td>
                        <td className="px-3 py-2.5 text-muted cursor-pointer" onClick={() => setSelectedCode(r.code)}>{r.cancelled || '—'}</td>
                        {isAdmin && (
                          <td className="px-3 py-2.5">
                            <button
                              onClick={() => setManagingCode(r.code)}
                              className="text-[10px] font-bold px-2 py-1 rounded border transition-all hover:shadow-sm"
                              style={{
                                color: r.is_blocked ? C.green : C.red,
                                borderColor: r.is_blocked ? `${C.green}40` : `${C.red}40`,
                                backgroundColor: r.is_blocked ? `${C.green}08` : `${C.red}08`,
                              }}
                            >
                              {r.is_blocked ? 'Unblock' : 'Manage'}
                            </button>
                          </td>
                        )}
                      </tr>
                    ))}
                  </tbody>
                </table>
                </div>
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
                        const count = (interviewers as Interviewer[]).filter(i => i.supervisor_id === s.id).length
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
                        <td className="px-4 py-2"><span className="text-muted text-xs">→</span></td>
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
      {managingCode && (
        <ActionModal
          code={managingCode}
          isBlocked={!!(rows.find(r => r.code === managingCode)?.is_blocked)}
          onClose={() => setManagingCode(null)}
        />
      )}
    </div>
  )
}
