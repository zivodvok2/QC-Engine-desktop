import React from 'react'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, LayoutDashboard, Loader2, Users } from 'lucide-react'
import { useAppStore } from '../../store/appStore'

const IS_DASHBOARD_DOMAIN = typeof window !== 'undefined' && (
  window.location.hostname.includes('dashboard.') ||
  new URLSearchParams(window.location.search).get('mode') === 'dashboard'
)
import { getDashboardSummary, type ProjectSummary } from '../../api/dashboard'
import { Overview } from './Overview'
import { ProjectDetail } from './ProjectDetail'
import { InterviewerDirectory } from './InterviewerDirectory'

export function Dashboard() {
  const {
    authToken, authUser,
    dashboardProjectId, dashboardView,
    setDashboardMode, setDashboardProject, setDashboardView,
  } = useAppStore()
  const token = authToken ?? ''

  const { data: summary = [], isLoading } = useQuery({
    queryKey: ['dash-summary'],
    queryFn: () => getDashboardSummary(token),
    enabled: !!token,
  })

  return (
    <div className="flex h-full overflow-hidden">
      {/* Left sidebar */}
      <aside className="w-52 shrink-0 bg-surface border-r border-line flex flex-col overflow-hidden">
        {/* Back button — hidden on dashboard subdomain */}
        {!IS_DASHBOARD_DOMAIN && (
          <button
            onClick={() => setDashboardMode(false)}
            className="flex items-center gap-2 px-4 py-3 text-sm text-muted hover:text-tx hover:bg-surface2 transition-colors border-b border-line"
          >
            <ArrowLeft size={13} />
            QC Engine
          </button>
        )}

        {/* Overview button */}
        <button
          onClick={() => setDashboardView('overview')}
          className={`flex items-center gap-2 px-4 py-2.5 text-sm transition-colors ${
            dashboardView === 'overview'
              ? 'text-accent bg-accent/10 border-r-2 border-accent'
              : 'text-muted hover:text-tx hover:bg-surface2'
          }`}
        >
          <LayoutDashboard size={13} />
          Overview
        </button>

        {/* Interviewers button */}
        <button
          onClick={() => setDashboardView('interviewers')}
          className={`flex items-center gap-2 px-4 py-2.5 text-sm transition-colors ${
            dashboardView === 'interviewers'
              ? 'text-accent bg-accent/10 border-r-2 border-accent'
              : 'text-muted hover:text-tx hover:bg-surface2'
          }`}
        >
          <Users size={13} />
          Interviewers
        </button>

        <div className="px-3 py-2 mt-1">
          <p className="text-[10px] text-muted uppercase tracking-wider">Projects</p>
        </div>

        {/* Project list */}
        <div className="flex-1 overflow-y-auto">
          {isLoading ? (
            <div className="flex items-center gap-2 px-4 py-3 text-muted text-xs">
              <Loader2 size={12} className="animate-spin" /> Loading…
            </div>
          ) : (
            summary.map((p: ProjectSummary) => (
              <button
                key={p.id}
                onClick={() => setDashboardProject(p.id)}
                className={`w-full flex items-center gap-2 px-4 py-2 text-left transition-colors ${
                  dashboardView === 'project' && dashboardProjectId === p.id
                    ? 'text-accent bg-accent/10 border-r-2 border-accent'
                    : 'text-muted hover:text-tx hover:bg-surface2'
                }`}
              >
                <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${
                  p.status === 'active' ? 'bg-accent' : p.status === 'closed' ? 'bg-muted' : 'bg-warning'
                }`} />
                <span className="text-xs leading-snug truncate">{p.name}</span>
              </button>
            ))
          )}
        </div>

        {/* Auth info */}
        {authUser && (
          <div className="px-4 py-3 border-t border-line">
            <p className="text-[10px] text-muted truncate">{authUser.name}</p>
            <p className="text-[9px] text-muted/60 truncate">{authUser.role.replace(/_/g, ' ')}</p>
          </div>
        )}
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto">
        <div className="p-6">
          {dashboardView === 'overview' && <Overview onSelectProject={setDashboardProject} />}
          {dashboardView === 'project' && dashboardProjectId !== null && <ProjectDetail id={dashboardProjectId} />}
          {dashboardView === 'interviewers' && <InterviewerDirectory />}
        </div>
      </main>
    </div>
  )
}
