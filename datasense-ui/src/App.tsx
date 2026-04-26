import React, { useState } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import {
  ShieldCheck, BarChart2, Braces, Copy, TrendingDown,
  Users, MessageSquare, LineChart, Upload,
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
import { OnboardingTooltip } from './components/onboarding/OnboardingTooltip'
import { SettingsPanel } from './components/settings/SettingsPanel'
import { useAppStore } from './store/appStore'

const qc = new QueryClient({
  defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } },
})

const FEATURE_CARDS = [
  { Icon: ShieldCheck,   title: 'Missing Value Checks',     desc: 'Flag respondents and columns exceeding configurable missing thresholds.' },
  { Icon: BarChart2,     title: 'Range Validation',         desc: 'Detect numeric values outside expected bounds per variable.' },
  { Icon: Braces,        title: 'Logic Checks',             desc: 'Custom IF / THEN rules to catch invalid conditional patterns.' },
  { Icon: Copy,          title: 'Duplicate Detection',      desc: 'Identify exact and near-duplicate records across key identifiers.' },
  { Icon: TrendingDown,  title: 'Straightlining',           desc: 'Flag respondents giving identical answers across rating scales.' },
  { Icon: Users,         title: 'Interviewer QC',           desc: 'Duration anomalies, productivity outliers, and fabrication signals.' },
  { Icon: MessageSquare, title: 'Verbatim Quality',         desc: 'AI-scored open-ended responses for relevance and depth.' },
  { Icon: LineChart,     title: 'EDA & Visualisation',      desc: 'Interactive charts and summary statistics across your dataset.' },
]

function LandingPage() {
  return (
    <div className="flex flex-col items-center justify-center min-h-full px-6 py-16 space-y-12">
      {/* Hero */}
      <div className="text-center space-y-3">
        <div className="inline-flex items-center gap-3 mb-2">
          <div className="w-9 h-9 bg-accent rounded-lg flex items-center justify-center">
            <span className="font-display font-extrabold text-bg text-sm">SL</span>
          </div>
          <h1 className="font-display font-extrabold text-4xl text-tx tracking-tight">Servallab</h1>
        </div>
        <p className="text-muted text-lg">Survey Quality Control Engine</p>
      </div>

      {/* Upload */}
      <div className="w-full max-w-md">
        <FileUpload />
      </div>

      {/* Feature grid */}
      <div className="w-full max-w-4xl grid grid-cols-2 sm:grid-cols-4 gap-4">
        {FEATURE_CARDS.map(({ Icon, title, desc }) => (
          <div key={title} className="card p-4 space-y-2 hover:border-muted transition-colors">
            <div className="w-8 h-8 bg-surface2 rounded flex items-center justify-center">
              <Icon size={16} className="text-accent" />
            </div>
            <p className="text-sm font-medium text-tx leading-snug">{title}</p>
            <p className="text-xs text-muted leading-relaxed">{desc}</p>
          </div>
        ))}
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
    </div>
  )
}

function AppShell() {
  const { fileId } = useAppStore()
  const [showSettings, setShowSettings] = useState(false)

  return (
    <div className="flex h-full">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        {fileId ? (
          <>
            <Header onSettings={() => setShowSettings(true)} />
            <TabContent />
          </>
        ) : (
          <main className="flex-1 overflow-auto">
            <LandingPage />
          </main>
        )}
      </div>
      {showSettings && <SettingsPanel onClose={() => setShowSettings(false)} />}
    </div>
  )
}

export default function App() {
  return (
    <QueryClientProvider client={qc}>
      <OnboardingTooltip />
      <AppShell />
    </QueryClientProvider>
  )
}
