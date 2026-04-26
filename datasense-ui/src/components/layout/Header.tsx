import React from 'react'
import { Settings } from 'lucide-react'
import { useAppStore } from '../../store/appStore'

const TABS = ['QC Report', 'Logic Checks', 'Straightlining', 'Interviewers', 'Quotas', 'Wave Compare', 'EDA', 'Data Preview', 'Config']

interface Props { onSettings: () => void }

export function Header({ onSettings }: Props) {
  const { activeTab, setActiveTab, jobStatus, jobProgress } = useAppStore()

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
          {TABS.map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`
                px-4 py-3 text-sm whitespace-nowrap border-b-2 transition-colors
                ${activeTab === tab
                  ? 'border-accent text-accent'
                  : 'border-transparent text-muted hover:text-tx hover:border-line'
                }
              `}
            >
              {tab}
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
