import React from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from 'recharts'
import { Loader2, AlertTriangle, AlertCircle, Info } from 'lucide-react'
import { useAppStore } from '../../store/appStore'
import { getDashboardSummary, getDashboardActivity, type ProjectSummary, type ActivityEntry } from '../../api/dashboard'

const C = {
  accent: '#00B5A3', critical: '#1B2A4A', warning: '#00B5A3', info: '#1B2A4A',
  purple: '#1B2A4A', muted: '#6B7280', surface: '#FFFFFF', surface2: '#F1F4F8',
  line: '#E2E6ED', tx: '#1B2A4A',
}

const TooltipStyle = {
  contentStyle: { backgroundColor: C.surface2, border: `1px solid ${C.line}`, borderRadius: 6, color: C.tx },
  itemStyle: { color: C.tx },
  labelStyle: { color: C.muted },
}

const REPORT_TYPE_LABELS: Record<string, string> = {
  quality_report: 'Quality Report',
  backcheck: 'Back-check',
  listen_in: 'Listen-in',
  performance: 'Performance',
  timing: 'Timing',
  cancelled_interviews: 'Cancelled',
}

interface Props {
  onSelectProject: (id: number) => void
}

export function Overview({ onSelectProject }: Props) {
  const { authToken } = useAppStore()
  const token = authToken ?? ''

  const { data: summary = [], isLoading } = useQuery({
    queryKey: ['dash-summary'],
    queryFn: () => getDashboardSummary(token),
    enabled: !!token,
  })

  const { data: activity = [] } = useQuery({
    queryKey: ['dash-activity'],
    queryFn: () => getDashboardActivity(token),
    enabled: !!token,
  })

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 text-muted text-sm p-6">
        <Loader2 size={14} className="animate-spin" /> Loading dashboard…
      </div>
    )
  }

  // KPIs
  const activeProjects = summary.filter((p: ProjectSummary) => p.status === 'active').length
  const totalTarget = summary.reduce((s: number, p: ProjectSummary) => s + (p.sample_target ?? 0), 0)
  const totalApproved = summary.reduce((s: number, p: ProjectSummary) => s + (p.approved ?? 0), 0)
  const avgBcRate = summary.length > 0
    ? Math.round(summary.reduce((s: number, p: ProjectSummary) => s + (p.backcheck_rate ?? 0), 0) / summary.length * 10) / 10
    : 0
  const totalFlagged = summary.reduce((s: number, p: ProjectSummary) => s + (p.flagged ?? 0), 0)

  // Bar chart data
  const chartData = summary
    .filter((p: ProjectSummary) => p.status === 'active')
    .map((p: ProjectSummary) => ({
      name: p.name.length > 18 ? p.name.slice(0, 16) + '…' : p.name,
      Target: p.sample_target,
      Approved: p.approved,
    }))

  // Risk alerts
  const criticalProjects = summary.filter((p: ProjectSummary) =>
    p.flagged > 0 && p.total_submitted > 0 && (p.flagged / p.total_submitted * 100) >= (p.flag_critical_pct ?? 10)
  )
  const warningProjects = summary.filter((p: ProjectSummary) =>
    p.flagged > 0 && p.total_submitted > 0 && (p.flagged / p.total_submitted * 100) >= (p.flag_warning_pct ?? 5) &&
    (p.flagged / p.total_submitted * 100) < (p.flag_critical_pct ?? 10)
  )
  const lowBcProjects = summary.filter((p: ProjectSummary) =>
    p.status === 'active' && p.approved > 0 && p.backcheck_rate < (p.backcheck_target * 100 * 0.5)
  )

  return (
    <div className="space-y-6">
      {/* KPI strip */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
        {[
          { label: 'Active Projects', value: activeProjects, color: 'text-accent' },
          { label: 'Total Target', value: totalTarget.toLocaleString(), color: 'text-tx' },
          { label: 'Total Approved', value: totalApproved.toLocaleString(), color: 'text-accent' },
          { label: 'Avg BC Rate', value: `${avgBcRate}%`, color: 'text-info' },
          { label: 'Total Flagged', value: totalFlagged, color: totalFlagged > 0 ? 'text-critical' : 'text-muted' },
        ].map(k => (
          <div key={k.label} className="card p-4">
            <p className="label mb-1">{k.label}</p>
            <p className={`text-2xl font-bold font-display ${k.color}`}>{k.value}</p>
          </div>
        ))}
      </div>

      {/* Bar chart */}
      {chartData.length > 0 && (
        <div className="card p-4">
          <p className="label mb-3">Target vs Approved (Active Projects)</p>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={chartData} margin={{ left: -20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={C.line} />
              <XAxis dataKey="name" tick={{ fill: C.muted, fontSize: 10 }} />
              <YAxis tick={{ fill: C.muted, fontSize: 10 }} />
              <Tooltip {...TooltipStyle} />
              <Legend wrapperStyle={{ color: C.muted, fontSize: 11 }} />
              <Bar dataKey="Target" fill={C.surface2} stroke={C.line} radius={[2, 2, 0, 0]} />
              <Bar dataKey="Approved" fill={C.accent} radius={[2, 2, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Risk alerts */}
      {(criticalProjects.length > 0 || warningProjects.length > 0 || lowBcProjects.length > 0) && (
        <div className="space-y-2">
          <p className="label">Risk Alerts</p>
          {criticalProjects.map((p: ProjectSummary) => (
            <div key={p.id} className="flex items-start gap-2 bg-navy/10 border border-navy/20 rounded-lg px-3 py-2.5">
              <AlertCircle size={14} className="text-tx mt-0.5 shrink-0" />
              <p className="text-xs text-tx">
                <span className="font-semibold">{p.name}</span> — flag rate{' '}
                {Math.round(p.flagged / p.total_submitted * 100)}% exceeds critical threshold ({p.flag_critical_pct ?? 10}%)
              </p>
            </div>
          ))}
          {warningProjects.map((p: ProjectSummary) => (
            <div key={p.id} className="flex items-start gap-2 bg-accent/10 border border-accent/20 rounded-lg px-3 py-2.5">
              <AlertTriangle size={14} className="text-accent mt-0.5 shrink-0" />
              <p className="text-xs text-tx">
                <span className="font-semibold">{p.name}</span> — flag rate{' '}
                {Math.round(p.flagged / p.total_submitted * 100)}% exceeds warning threshold ({p.flag_warning_pct ?? 5}%)
              </p>
            </div>
          ))}
          {lowBcProjects.map((p: ProjectSummary) => (
            <div key={p.id} className="flex items-start gap-2 bg-navy/5 border border-navy/10 rounded-lg px-3 py-2.5">
              <Info size={14} className="text-muted mt-0.5 shrink-0" />
              <p className="text-xs text-tx">
                <span className="font-semibold">{p.name}</span> — back-check rate{' '}
                {p.backcheck_rate}% is below 50% of target ({Math.round(p.backcheck_target * 100)}%)
              </p>
            </div>
          ))}
        </div>
      )}

      {/* Project cards grid */}
      <div>
        <p className="label mb-3">All Projects ({summary.length})</p>
        {summary.length === 0 ? (
          <div className="card p-8 text-center text-muted text-sm">
            No projects yet. An admin can create projects in the Admin tab.
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {summary.map((p: ProjectSummary) => {
              const flagPct = p.total_submitted > 0 ? p.flagged / p.total_submitted * 100 : 0
              const isCritical = p.status === 'active' && flagPct >= (p.flag_critical_pct ?? 10)
              const isAmber = !isCritical && p.status === 'active' && (
                flagPct >= (p.flag_warning_pct ?? 5) ||
                (p.approved > 0 && p.backcheck_rate < p.backcheck_target * 100 * 0.5)
              )
              const isGreen = !isCritical && !isAmber && p.status === 'active' && p.approved > 0
              const ragColor = isCritical ? '#EF4444' : isAmber ? '#F97316' : isGreen ? '#10B981' : '#6B7280'
              const ragLabel = isCritical ? 'Critical' : isAmber ? 'Needs Review' : isGreen ? 'On Track' : p.status

              return (
                <button
                  key={p.id}
                  onClick={() => onSelectProject(p.id)}
                  className="card p-4 space-y-3 text-left hover:shadow-md transition-all"
                  style={{ borderLeft: `4px solid ${ragColor}` }}
                >
                  {/* Header row with traffic light */}
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-semibold text-tx leading-tight truncate">{p.name}</p>
                      {p.client && <p className="text-xs text-muted mt-0.5">{p.client}</p>}
                      {p.job_number && <p className="text-xs text-muted">{p.job_number}</p>}
                    </div>
                    {/* RAG Traffic Light */}
                    <div
                      className="flex items-center gap-1.5 px-2.5 py-1 rounded-full shrink-0"
                      style={{ backgroundColor: `${ragColor}18`, border: `1px solid ${ragColor}40` }}
                    >
                      <span className="w-2.5 h-2.5 rounded-full shrink-0 shadow-sm" style={{ backgroundColor: ragColor }} />
                      <span className="text-[10px] font-bold uppercase tracking-wide" style={{ color: ragColor }}>
                        {ragLabel}
                      </span>
                    </div>
                  </div>

                  {/* Progress bar */}
                  <div>
                    <div className="flex justify-between text-[10px] text-muted mb-1">
                      <span>Completion</span>
                      <span className="font-medium">{p.completion_pct}% — {p.approved} / {p.sample_target}</span>
                    </div>
                    <div className="h-2 bg-surface2 rounded-full overflow-hidden">
                      <div
                        className="h-full rounded-full transition-all"
                        style={{
                          width: `${Math.min(p.completion_pct, 100)}%`,
                          backgroundColor: ragColor,
                        }}
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-3 gap-2 text-center pt-1 border-t border-line/50">
                    <div>
                      <p className="text-[10px] text-muted mb-0.5">Back-check</p>
                      <p className="text-xs font-bold" style={{
                        color: p.backcheck_rate >= p.backcheck_target * 100 ? '#10B981' : p.approved > 0 ? '#F97316' : '#6B7280'
                      }}>{p.backcheck_rate}%</p>
                    </div>
                    <div>
                      <p className="text-[10px] text-muted mb-0.5">Listen-in</p>
                      <p className="text-xs font-bold" style={{
                        color: p.listenin_rate >= p.listenin_target * 100 ? '#10B981' : p.approved > 0 ? '#F97316' : '#6B7280'
                      }}>{p.listenin_rate}%</p>
                    </div>
                    <div>
                      <p className="text-[10px] text-muted mb-0.5">Flagged</p>
                      <p className="text-xs font-bold" style={{
                        color: p.flagged > 0 ? (isCritical ? '#EF4444' : '#F97316') : '#6B7280'
                      }}>{p.flagged || '—'}</p>
                    </div>
                  </div>
                </button>
              )
            })}
          </div>
        )}
      </div>

      {/* Activity feed */}
      {activity.length > 0 && (
        <div className="card p-4">
          <p className="label mb-3">Recent Activity</p>
          <div className="space-y-2">
            {activity.map((a: ActivityEntry, i: number) => (
              <div key={i} className="flex items-center gap-3 text-xs">
                <span className="text-muted shrink-0">{a.upload_date?.slice(0, 10)}</span>
                <span className="badge-info shrink-0">{REPORT_TYPE_LABELS[a.report_type] ?? a.report_type}</span>
                <span className="text-tx">{a.project_name}</span>
                <span className="text-muted">—</span>
                <span className="text-muted">{a.filename}</span>
                {a.wave_label && <span className="text-muted">({a.wave_label})</span>}
                {a.uploader && <span className="text-muted ml-auto shrink-0">by {a.uploader}</span>}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
