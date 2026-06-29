import React from 'react'
import {
  Settings, ShieldCheck, Braces, TrendingDown, Users,
  Target, GitCompare, LineChart, Table2, SlidersHorizontal, Clapperboard,
  LogIn, LogOut, LayoutDashboard,
} from 'lucide-react'
import { useAppStore } from '../../store/appStore'

const IS_DASHBOARD_DOMAIN = typeof window !== 'undefined' && (
  window.location.hostname.includes('dashboard.') ||
  new URLSearchParams(window.location.search).get('mode') === 'dashboard'
)

const TABS: { label: string; icon: React.ElementType }[] = [
  { label: 'QC Report',      icon: ShieldCheck },
  { label: 'Logic Checks',   icon: Braces },
  { label: 'Straightlining', icon: TrendingDown },
  { label: 'Interviewers',   icon: Users },
  { label: 'Quotas',         icon: Target },
  { label: 'Wave Compare',   icon: GitCompare },
  { label: 'EDA',            icon: LineChart },
  { label: 'Data Preview',   icon: Table2 },
  { label: 'Config',         icon: SlidersHorizontal },
  { label: 'Demos',          icon: Clapperboard },
]

interface Props { onSettings: () => void }

const PRE_FILE_TABS = new Set(['Config', 'Demos'])

export function Header({ onSettings }: Props) {
  const { activeTab, setActiveTab, jobStatus, jobProgress, fileId, authUser, openLogin, logoutUser, dashboardMode, setDashboardMode, setDashboardProject } = useAppStore()
  const visibleTabs = dashboardMode
    ? TABS.filter(t => PRE_FILE_TABS.has(t.label))
    : (fileId ? TABS : TABS.filter(t => PRE_FILE_TABS.has(t.label)))
  return (
    <header className="bg-surface border-b border-line shrink-0">
      {/* Progress bar */}
      {(jobStatus === 'queued' || jobStatus === 'running') && (
        <div className="h-0.5 bg-line">
          <div
            className="h-full bg-accent transition-all duration-500"
            style={{ width: `${jobProgress || 15}%` }}
          />
        </div>
      )}

      <div className="flex items-center justify-between px-4">
        {/* Tabs */}
        <nav className="flex overflow-x-auto">
          {visibleTabs.map(({ label, icon: Icon }) => (
            <button
              key={label}
              onClick={() => setActiveTab(label)}
              className={`
                flex items-center gap-1.5 px-4 py-3 text-sm whitespace-nowrap border-b-2 transition-colors
                ${activeTab === label
                  ? 'border-accent text-accent'
                  : 'border-transparent text-muted hover:text-tx hover:border-line'
                }
              `}
            >
              <Icon size={13} />
              {label}
            </button>
          ))}
        </nav>

        {/* Right controls */}
        <div className="flex items-center gap-2 pl-4 shrink-0">
          {jobStatus === 'complete' && (
            <span className="text-xs text-accent">✓ QC complete</span>
          )}
          {jobStatus === 'failed' && (
            <span className="text-xs text-critical">✗ Run failed</span>
          )}

          {/* Dashboard button — only when signed in and NOT locked on the dashboard subdomain */}
          {authUser && !IS_DASHBOARD_DOMAIN && (
            <button
              onClick={() => { setDashboardMode(!dashboardMode); setDashboardProject(null) }}
              className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded text-xs transition-colors ${
                dashboardMode
                  ? 'bg-accent/20 text-accent border border-accent/40'
                  : 'text-muted hover:text-tx hover:bg-surface2'
              }`}
              title={dashboardMode ? 'Exit Dashboard' : 'Open QC Dashboard'}
            >
              <LayoutDashboard size={13} />
              <span className="hidden sm:inline">{dashboardMode ? 'Exit Dashboard' : 'Dashboard'}</span>
            </button>
          )}

          {/* Auth */}
          {authUser ? (
            <div className="flex items-center gap-1.5">
              <span className="text-xs text-muted hidden sm:inline">{authUser.name}</span>
              <div
                title={`${authUser.name} (${authUser.role})`}
                className="w-6 h-6 rounded-full bg-accent/20 text-accent text-[10px] font-bold flex items-center justify-center uppercase"
              >
                {authUser.name.slice(0, 1)}
              </div>
              <button
                onClick={logoutUser}
                className="p-1.5 text-muted hover:text-tx transition-colors"
                title="Sign out"
              >
                <LogOut size={14} />
              </button>
            </div>
          ) : (
            <button
              onClick={() => openLogin()}
              className="flex items-center gap-1 text-xs text-muted hover:text-tx transition-colors px-2 py-1 rounded hover:bg-surface2"
              title="Sign in"
            >
              <LogIn size={13} />
              Sign in
            </button>
          )}

          <button
            onClick={onSettings}
            className="p-1.5 text-muted hover:text-tx transition-colors"
            title="Settings"
          >
            <Settings size={16} />
          </button>
        </div>
      </div>
    </header>
  )
}
