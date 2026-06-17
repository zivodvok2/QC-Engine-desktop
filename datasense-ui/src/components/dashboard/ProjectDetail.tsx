import React, { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Loader2 } from 'lucide-react'
import { useAppStore } from '../../store/appStore'
import { getDashboardSummary, type ProjectSummary } from '../../api/dashboard'
import { QualityReportTab } from './tabs/QualityReportTab'
import { BackcheckTab } from './tabs/BackcheckTab'
import { ListenInTab } from './tabs/ListenInTab'
import { PerformanceTab } from './tabs/PerformanceTab'
import { TimingTab } from './tabs/TimingTab'
import { CancelledTab } from './tabs/CancelledTab'
import { AdminTab } from './tabs/AdminTab'
import { CombinedReportTab } from './tabs/CombinedReportTab'

type SubTab = 'quality' | 'backcheck' | 'listenin' | 'performance' | 'timing' | 'cancelled' | 'combined' | 'admin'

const ADMIN_ROLES = new Set(['qc_executive', 'operations_manager'])

interface Props { id: number }

export function ProjectDetail({ id }: Props) {
  const { authUser, authToken } = useAppStore()
  const token = authToken ?? ''
  const [subTab, setSubTab] = useState<SubTab>('quality')

  const { data: summary = [], isLoading } = useQuery({
    queryKey: ['dash-summary'],
    queryFn: () => getDashboardSummary(token),
    enabled: !!token,
  })

  const project: ProjectSummary | undefined = summary.find((p: ProjectSummary) => p.id === id)

  const isAdmin = authUser && ADMIN_ROLES.has(authUser.role)

  const tabs: { key: SubTab; label: string }[] = [
    { key: 'quality',      label: 'Quality Report' },
    { key: 'backcheck',    label: 'Back-check' },
    { key: 'listenin',     label: 'Listen-in' },
    { key: 'performance',  label: 'Performance' },
    { key: 'timing',       label: 'Timing' },
    { key: 'cancelled',    label: 'Cancelled' },
    { key: 'combined',     label: 'Combined Report' },
    ...(isAdmin ? [{ key: 'admin' as SubTab, label: 'Admin' }] : []),
  ]

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 text-muted text-sm p-6">
        <Loader2 size={14} className="animate-spin" /> Loading project…
      </div>
    )
  }

  if (!project) {
    return <div className="p-6 text-muted text-sm">Project not found.</div>
  }

  const bcRateColor = project.backcheck_rate >= project.backcheck_target * 100
    ? 'text-accent'
    : project.backcheck_rate >= project.backcheck_target * 80
    ? 'text-warning'
    : 'text-critical'

  const liRateColor = project.listenin_rate >= project.listenin_target * 100
    ? 'text-accent'
    : project.listenin_rate >= project.listenin_target * 80
    ? 'text-warning'
    : 'text-critical'

  return (
    <div className="space-y-4">
      {/* Project header */}
      <div className="card p-5">
        <div className="flex items-start justify-between flex-wrap gap-3">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className={`w-2 h-2 rounded-full ${
                project.status === 'active' ? 'bg-accent' : project.status === 'closed' ? 'bg-muted' : 'bg-warning'
              }`} />
              <h2 className="text-lg font-display font-bold text-tx">{project.name}</h2>
              {project.job_number && (
                <span className="text-xs text-muted border border-line rounded px-1.5 py-0.5">{project.job_number}</span>
              )}
            </div>
            {project.client && <p className="text-sm text-muted">{project.client}</p>}
            {(project.start_date || project.end_date) && (
              <p className="text-xs text-muted mt-1">
                {project.start_date ?? '?'} → {project.end_date ?? 'ongoing'}
              </p>
            )}
          </div>

          {/* KPI pills */}
          <div className="flex flex-wrap gap-3">
            <div className="card2 p-3 text-center min-w-[80px]">
              <p className="label mb-0.5">Approved</p>
              <p className="text-lg font-bold font-display text-accent">{project.approved}</p>
              <p className="text-[10px] text-muted">of {project.sample_target}</p>
            </div>
            <div className="card2 p-3 text-center min-w-[80px]">
              <p className="label mb-0.5">Completion</p>
              <p className="text-lg font-bold font-display text-accent">{project.completion_pct}%</p>
            </div>
            <div className="card2 p-3 text-center min-w-[80px]">
              <p className="label mb-0.5">BC Rate</p>
              <p className={`text-lg font-bold font-display ${bcRateColor}`}>{project.backcheck_rate}%</p>
              <p className="text-[10px] text-muted">tgt {Math.round(project.backcheck_target * 100)}%</p>
            </div>
            <div className="card2 p-3 text-center min-w-[80px]">
              <p className="label mb-0.5">Listen-in</p>
              <p className={`text-lg font-bold font-display ${liRateColor}`}>{project.listenin_rate}%</p>
              <p className="text-[10px] text-muted">tgt {Math.round(project.listenin_target * 100)}%</p>
            </div>
            <div className="card2 p-3 text-center min-w-[80px]">
              <p className="label mb-0.5">Flagged</p>
              <p className={`text-lg font-bold font-display ${project.flagged > 0 ? 'text-critical' : 'text-muted'}`}>
                {project.flagged}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Sub-tabs */}
      <div className="flex gap-1 border-b border-line pb-0">
        {tabs.map(t => (
          <button
            key={t.key}
            onClick={() => setSubTab(t.key)}
            className={`px-4 py-2 text-sm border-b-2 transition-colors -mb-px ${
              subTab === t.key
                ? 'border-accent text-accent'
                : 'border-transparent text-muted hover:text-tx'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {subTab === 'quality'      && <QualityReportTab projectId={id} />}
      {subTab === 'backcheck'    && <BackcheckTab projectId={id} target={project.backcheck_target} />}
      {subTab === 'listenin'     && <ListenInTab projectId={id} target={project.listenin_target} />}
      {subTab === 'performance'  && <PerformanceTab projectId={id} />}
      {subTab === 'timing'       && <TimingTab projectId={id} loiMin={project.loi_min_minutes ?? undefined} />}
      {subTab === 'cancelled'    && <CancelledTab projectId={id} />}
      {subTab === 'combined'     && <CombinedReportTab projectId={id} />}
      {subTab === 'admin'        && isAdmin && <AdminTab projectId={id} />}
    </div>
  )
}
