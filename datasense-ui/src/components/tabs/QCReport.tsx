import React, { useState } from 'react'
import { Download, ChevronDown, ChevronUp, AlertTriangle, Info, XCircle, Activity } from 'lucide-react'
import { useAppStore } from '../../store/appStore'
import { downloadReport } from '../../api/qc'
import type { CheckResult } from '../../types'

const SEV_ORDER: Record<string, number> = { critical: 0, warning: 1, info: 2 }

function MetricCard({ label, value, color }: { label: string; value: number | string; color?: string }) {
  return (
    <div className="card2 px-4 py-3 space-y-1">
      <p className="label">{label}</p>
      <p className={`text-2xl font-display font-extrabold ${color ?? 'text-tx'}`}>{value}</p>
    </div>
  )
}

function CheckAccordion({ check, totalFlags }: { check: CheckResult; totalFlags: number }) {
  const [open, setOpen] = useState(false)
  const [page, setPage] = useState(0)
  const PAGE_SIZE = 25
  const pct = totalFlags > 0 ? ((check.flag_count / totalFlags) * 100).toFixed(1) : '0'
  const rows = check.flagged_rows.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE)
  const totalPages = Math.ceil(check.flagged_rows.length / PAGE_SIZE)
  const cols = check.flagged_rows[0] ? Object.keys(check.flagged_rows[0]).filter((k) => !k.startsWith('_')) : []

  const sev = check.severity
  const badgeClass = sev === 'critical' ? 'badge-critical' : sev === 'warning' ? 'badge-warning' : 'badge-info'

  return (
    <div className="card border-line">
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center gap-3 px-4 py-3 text-left"
      >
        <span className={badgeClass}>{sev}</span>
        <span className="text-sm font-medium text-tx flex-1">{check.check_name.replace(/_/g, ' ')}</span>
        <span className="text-xs text-muted mr-2">{check.flag_count} flags · {pct}%</span>
        {open ? <ChevronUp size={14} className="text-muted" /> : <ChevronDown size={14} className="text-muted" />}
      </button>

      {open && check.flag_count > 0 && (
        <div className="border-t border-line px-4 pb-4 pt-3 space-y-3">
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-line">
                  {cols.map((c) => (
                    <th key={c} className="text-left py-1.5 px-2 text-muted font-normal whitespace-nowrap">{c}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((row, i) => (
                  <tr key={i} className="border-b border-line/50 hover:bg-surface2 transition-colors">
                    {cols.map((c) => (
                      <td key={c} className="py-1.5 px-2 text-tx whitespace-nowrap">
                        {String(row[c] ?? '')}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {totalPages > 1 && (
            <div className="flex items-center gap-2 text-xs text-muted">
              <button disabled={page === 0} onClick={() => setPage((p) => p - 1)} className="btn-ghost px-2 py-0.5 disabled:opacity-30">‹</button>
              <span>Page {page + 1} / {totalPages}</span>
              <button disabled={page >= totalPages - 1} onClick={() => setPage((p) => p + 1)} className="btn-ghost px-2 py-0.5 disabled:opacity-30">›</button>
            </div>
          )}
        </div>
      )}

      {open && check.flag_count === 0 && (
        <p className="border-t border-line px-4 py-3 text-xs text-muted">No rows flagged by this check.</p>
      )}
    </div>
  )
}

export function QCReport() {
  const { results, jobId, jobStatus, jobError } = useAppStore()
  const [downloading, setDownloading] = useState(false)

  const handleDownload = async () => {
    if (!jobId) return
    setDownloading(true)
    try {
      const blob = await downloadReport(jobId)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `qc_report_${jobId.slice(0, 8)}.xlsx`
      a.click()
      URL.revokeObjectURL(url)
    } finally {
      setDownloading(false)
    }
  }

  if (jobStatus === 'idle' || jobStatus === 'queued' || jobStatus === 'running') {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-3 text-muted">
        <Activity size={32} className={jobStatus !== 'idle' ? 'animate-pulse text-accent' : ''} />
        <p className="text-sm">{jobStatus === 'idle' ? 'Configure settings and click Run QC.' : `QC in progress…`}</p>
      </div>
    )
  }

  if (jobStatus === 'failed') {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-3 text-critical">
        <XCircle size={32} />
        <p className="text-sm">{jobError ?? 'QC run failed. Try again.'}</p>
      </div>
    )
  }

  if (!results) return null

  const sorted = [...results.checks].sort((a, b) => (SEV_ORDER[a.severity] ?? 9) - (SEV_ORDER[b.severity] ?? 9))

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Metric cards */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
        <MetricCard label="Checks run" value={results.checks.length} />
        <MetricCard label="Total flags" value={results.total_flags} />
        <MetricCard label="Critical" value={results.flagged_by_severity.critical ?? 0} color="text-critical" />
        <MetricCard label="Warnings" value={results.flagged_by_severity.warning ?? 0} color="text-warning" />
        <MetricCard label="Info" value={results.flagged_by_severity.info ?? 0} color="text-info" />
      </div>

      {/* Download */}
      <div className="flex justify-end">
        <button onClick={handleDownload} disabled={downloading} className="btn-ghost flex items-center gap-2">
          <Download size={14} />
          {downloading ? 'Downloading…' : 'Download Excel report'}
        </button>
      </div>

      {/* Check list */}
      <div className="space-y-2">
        {sorted.map((check) => (
          <CheckAccordion key={check.check_name} check={check} totalFlags={results.total_flags} />
        ))}
      </div>

      {results.total_flags === 0 && (
        <div className="flex items-center gap-2 text-accent text-sm justify-center py-8">
          <Info size={16} />
          No issues found — your data looks clean!
        </div>
      )}
    </div>
  )
}
