import React from 'react'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, LayoutDashboard, Loader2, LogIn, Settings, Users } from 'lucide-react'
import { useAppStore } from '../../store/appStore'

const IS_DASHBOARD_DOMAIN = typeof window !== 'undefined' && (
  window.location.hostname.includes('dashboard.') ||
  new URLSearchParams(window.location.search).get('mode') === 'dashboard'
)
import { getDashboardSummary, type ProjectSummary } from '../../api/dashboard'
import { Overview } from './Overview'
import { ProjectDetail, ADMIN_ROLES } from './ProjectDetail'
import { InterviewerDirectory } from './InterviewerDirectory'
import { AdminTab } from './tabs/AdminTab'

const NAVY = '#1B2A4A'

export function Dashboard() {
  const {
    authToken, authUser,
    dashboardProjectId, dashboardView,
    setDashboardMode, setDashboardProject, setDashboardView, openLogin,
  } = useAppStore()
  const isAdmin = authUser && ADMIN_ROLES.has(authUser.role)
  const token = authToken ?? ''

  const { data: summary = [], isLoading } = useQuery({
    queryKey: ['dash-summary'],
    queryFn: () => getDashboardSummary(token),
    enabled: !!token,
  })

  return (
    <div className="flex h-full overflow-hidden">
      {/* ── Ipsos navy sidebar ─────────────────────────────────────────────── */}
      <aside
        className="w-56 shrink-0 flex flex-col overflow-hidden"
        style={{ backgroundColor: NAVY }}
      >
        {/* Branding strip */}
        <div className="px-5 py-4 border-b border-white/10">
          <p className="text-white font-semibold text-sm tracking-wide">Servallab</p>
          <p className="text-white/50 text-xs mt-0.5">QC Dashboard</p>
        </div>

        {/* User badge */}
        {authUser && (
          <div className="px-5 py-3 border-b border-white/10">
            <div className="flex items-center gap-2">
              <div className="w-7 h-7 rounded-full bg-accent flex items-center justify-center text-white text-xs font-bold shrink-0">
                {authUser.name?.[0]?.toUpperCase() ?? 'U'}
              </div>
              <div className="min-w-0">
                <p className="text-white text-xs font-medium truncate">{authUser.name}</p>
                <p className="text-white/50 text-[10px] truncate capitalize">{authUser.role.replace(/_/g, ' ')}</p>
              </div>
            </div>
          </div>
        )}

        {/* Navigation */}
        <nav className="px-2 py-3 space-y-0.5">
          <p className="px-2 text-[10px] text-white/40 uppercase tracking-widest mb-2 font-medium">Navigation</p>

          {!IS_DASHBOARD_DOMAIN && (
            <button
              onClick={() => setDashboardMode(false)}
              className="nav-item w-full text-left"
            >
              <ArrowLeft size={14} /> QC Engine
            </button>
          )}

          <button
            onClick={() => setDashboardView('overview')}
            className={dashboardView === 'overview' ? 'nav-item-active w-full text-left' : 'nav-item w-full text-left'}
          >
            <LayoutDashboard size={14} /> Overview
          </button>

          <button
            onClick={() => setDashboardView('interviewers')}
            className={dashboardView === 'interviewers' ? 'nav-item-active w-full text-left' : 'nav-item w-full text-left'}
          >
            <Users size={14} /> Interviewers
          </button>

          {isAdmin && (
            <button
              onClick={() => setDashboardView('admin')}
              className={dashboardView === 'admin' ? 'nav-item-active w-full text-left' : 'nav-item w-full text-left'}
            >
              <Settings size={14} /> Admin
            </button>
          )}
        </nav>

        {/* Project list */}
        <div className="px-2 flex-1 overflow-y-auto">
          <p className="px-2 text-[10px] text-white/40 uppercase tracking-widest mb-2 font-medium">Projects</p>

          {!token ? (
            <button
              onClick={() => openLogin()}
              className="nav-item w-full text-left text-xs"
            >
              <LogIn size={13} /> Sign in
            </button>
          ) : isLoading ? (
            <div className="flex items-center gap-2 px-2 py-2 text-white/40 text-xs">
              <Loader2 size={11} className="animate-spin" /> Loading…
            </div>
          ) : (
            summary.map((p: ProjectSummary) => (
              <button
                key={p.id}
                onClick={() => setDashboardProject(p.id)}
                className={`w-full flex items-center gap-2 px-2 py-2 text-left rounded-lg text-xs transition-colors mb-0.5 ${
                  dashboardView === 'project' && dashboardProjectId === p.id
                    ? 'bg-accent/20 text-white border-r-2 border-accent font-medium'
                    : 'text-white/60 hover:text-white hover:bg-white/10'
                }`}
              >
                <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${
                  p.status === 'active' ? 'bg-accent' : p.status === 'closed' ? 'bg-white/30' : 'bg-white/50'
                }`} />
                <span className="leading-snug truncate">{p.name}</span>
              </button>
            ))
          )}
        </div>
      </aside>

      {/* ── Main content ──────────────────────────────────────────────────── */}
      <main className="flex-1 overflow-auto bg-bg">
        <div className="p-6 max-w-7xl">
          {dashboardView === 'overview'      && <Overview onSelectProject={setDashboardProject} />}
          {dashboardView === 'project'       && dashboardProjectId !== null && <ProjectDetail id={dashboardProjectId} />}
          {dashboardView === 'interviewers'  && <InterviewerDirectory />}
          {dashboardView === 'admin'         && isAdmin && <AdminTab />}
        </div>
      </main>
    </div>
  )
}
