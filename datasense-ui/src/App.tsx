import React, { useEffect } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import {
  ShieldCheck, Braces, TrendingDown, Users, Target,
  GitCompare, LineChart, Table2, SlidersHorizontal,
  Clapperboard, X,
} from 'lucide-react'
import { Sidebar } from './components/layout/Sidebar'
import { Header } from './components/layout/Header'
import { FileUpload } from './components/upload/FileUpload'
import { QCReport } from './components/tabs/QCReport'
import { LogicChecks } from './components/tabs/LogicChecks'
import { Straightlining } from './components/tabs/Straightlining'
import { EDA } from './components/tabs/EDA'
import { DataPreview } from './components/tabs/DataPreview'
import { Config } from './components/tabs/Config'
import { Interviewers } from './components/tabs/Interviewers'
import { WaveCompare } from './components/tabs/WaveCompare'
import { Quotas } from './components/tabs/Quotas'
import { Demos } from './components/tabs/Demos'
import { OnboardingTooltip } from './components/onboarding/OnboardingTooltip'
import { SettingsPanel } from './components/settings/SettingsPanel'
import { LoginModal } from './components/auth/LoginModal'
import { Dashboard } from './components/dashboard/Dashboard'
import { useAppStore, IS_DASHBOARD_DOMAIN } from './store/appStore'

const qc = new QueryClient({
  defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } },
})

const ACCENT_VARS: Record<string, [string, string]> = {
  emerald: ['74 240 160', '42 184 112'],
  blue:    ['74 158 240', '42 110 200'],
  purple:  ['160 120 240', '110 80 200'],
  orange:  ['240 144 64',  '200 100 24'],
  pink:    ['240 74 144',  '200 34 104'],
}

function ThemeSync() {
  const { theme, accent } = useAppStore()
  useEffect(() => {
    const root = document.documentElement
    root.setAttribute('data-theme', theme)
    const [acc, dim] = ACCENT_VARS[accent]
    root.style.setProperty('--c-accent', acc)
    root.style.setProperty('--c-accent-dim', dim)
  }, [theme, accent])
  return null
}

const FEATURE_CARDS = [
  { icon: ShieldCheck,       tab: 'QC Report',      desc: 'Missing values, range violations, duplicates, and fabrication flags in one report.' },
  { icon: Braces,            tab: 'Logic Checks',   desc: 'Custom IF / THEN rules to catch invalid conditional patterns.' },
  { icon: TrendingDown,      tab: 'Straightlining', desc: 'Flag respondents giving identical answers across rating scale batteries.' },
  { icon: Users,             tab: 'Interviewers',   desc: 'Duration anomalies, productivity outliers, and fabrication signals per interviewer.' },
  { icon: Target,            tab: 'Quotas',         desc: 'Real-time target vs achieved tracking with RAG cell colouring.' },
  { icon: GitCompare,        tab: 'Wave Compare',   desc: 'Compare two waves to detect drift, new interviewers, and changed values.' },
  { icon: LineChart,         tab: 'EDA',            desc: 'Interactive frequency plots, distributions, correlations, and cross-tabs.' },
  { icon: Table2,            tab: 'Data Preview',   desc: 'Browse the cleaned dataset with column filtering and pagination.' },
  { icon: SlidersHorizontal, tab: 'Config',         desc: 'View active config and the full audit trail of every QC run.' },
  { icon: Clapperboard,      tab: 'Demos',          desc: 'Short video walkthroughs for every feature — no file needed.' },
]

function DemosModal() {
  const { closeDemos } = useAppStore()
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm"
      onClick={(e) => { if (e.target === e.currentTarget) closeDemos() }}
    >
      <div className="bg-surface border border-line rounded-xl w-full max-w-5xl max-h-[85vh] flex flex-col shadow-2xl">
        {/* Modal header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-line shrink-0">
          <div className="flex items-center gap-2">
            <Clapperboard size={16} className="text-accent" />
            <span className="font-display font-bold text-sm text-tx">Demo Videos</span>
          </div>
          <button
            onClick={closeDemos}
            className="p-1.5 text-muted hover:text-tx hover:bg-surface2 rounded transition-colors"
            title="Close"
          >
            <X size={16} />
          </button>
        </div>
        {/* Modal body */}
        <div className="overflow-y-auto p-6">
          <Demos />
        </div>
      </div>
    </div>
  )
}

function LandingPage() {
  const { openDemos } = useAppStore()

  return (
    <div className="flex flex-col items-center justify-center min-h-full px-6 py-16 space-y-12">
      {/* Hero */}
      <div className="text-center space-y-3">
        <div className="inline-flex items-center gap-3 mb-2">
          <div className="w-9 h-9 bg-accent rounded-lg flex items-center justify-center">
            <span className="font-display font-extrabold text-bg text-sm">SL</span>
          </div>
          <h1 className="font-display font-extrabold text-4xl text-tx tracking-tight">Servalab</h1>
        </div>
        <p className="text-muted text-lg">Survey Quality Control Engine</p>
      </div>

      {/* Upload */}
      <div className="w-full max-w-md">
        <FileUpload />
      </div>

      {/* Feature grid */}
      <div className="w-full max-w-5xl space-y-3">
        <p className="text-xs text-muted uppercase tracking-wider text-center">What's inside</p>
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
          {FEATURE_CARDS.map(({ icon: Icon, tab, desc }) => (
            <button
              key={tab}
              onClick={tab === 'Demos' ? openDemos : undefined}
              className="card p-4 space-y-2 hover:border-muted transition-colors text-left group"
            >
              <div className="w-8 h-8 bg-surface2 rounded flex items-center justify-center group-hover:bg-accent/10 transition-colors">
                <Icon size={15} className="text-accent" />
              </div>
              <p className="text-sm font-medium text-tx leading-snug">{tab}</p>
              <p className="text-xs text-muted leading-relaxed">{desc}</p>
            </button>
          ))}
        </div>
        <p className="text-[10px] text-muted text-center pt-1">
          Upload a file above to unlock all tabs, or{' '}
          <button onClick={openDemos} className="text-accent underline underline-offset-2">
            watch demos
          </button>{' '}
          first.
        </p>
      </div>
    </div>
  )
}

function TabContent() {
  const { activeTab } = useAppStore()
  return (
    <div className="flex-1 overflow-auto p-6">
      {activeTab === 'QC Report'      && <QCReport />}
      {activeTab === 'Logic Checks'   && <LogicChecks />}
      {activeTab === 'Straightlining' && <Straightlining />}
      {activeTab === 'Interviewers'   && <Interviewers />}
      {activeTab === 'Quotas'         && <Quotas />}
      {activeTab === 'Wave Compare'   && <WaveCompare />}
      {activeTab === 'EDA'            && <EDA />}
      {activeTab === 'Data Preview'   && <DataPreview />}
      {activeTab === 'Config'         && <Config />}
      {activeTab === 'Demos'          && <Demos />}
    </div>
  )
}

function AppShell() {
  const { fileId, activeTab, demosOpen, settingsOpen, loginOpen, openSettings, closeSettings, dashboardMode, setDashboardMode } = useAppStore()

  useEffect(() => {
    if (IS_DASHBOARD_DOMAIN) setDashboardMode(true)
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="flex h-full">
      {dashboardMode ? (
        <div className="flex-1 flex flex-col overflow-hidden">
          <Header onSettings={openSettings} />
          <Dashboard />
        </div>
      ) : (
        <>
          <Sidebar />
          <div className="flex-1 flex flex-col overflow-hidden">
            <Header onSettings={openSettings} />
            {fileId || activeTab === 'Config' ? (
              <TabContent />
            ) : (
              <main className="flex-1 overflow-auto">
                <LandingPage />
              </main>
            )}
          </div>
          {demosOpen && !fileId && <DemosModal />}
        </>
      )}
      {settingsOpen && <SettingsPanel onClose={closeSettings} />}
      {loginOpen && <LoginModal />}
    </div>
  )
}

export default function App() {
  return (
    <QueryClientProvider client={qc}>
      <ThemeSync />
      <OnboardingTooltip />
      <AppShell />
    </QueryClientProvider>
  )
}
