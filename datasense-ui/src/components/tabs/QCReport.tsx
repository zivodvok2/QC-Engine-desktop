import React, { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { Download, ChevronDown, ChevronUp, Info, XCircle, Activity, Sparkles, FileText } from 'lucide-react'
import { useAppStore } from '../../store/appStore'
import { downloadReport } from '../../api/qc'
import { explainFlags, generateQCSummary } from '../../api/ai'
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

function CheckAccordion({
  check,
  totalFlags,
  totalRows,
  groqApiKey,
  model,
}: {
  check: CheckResult
  totalFlags: number
  totalRows: number
  groqApiKey: string
  model: string
}) {
  const [open, setOpen] = useState(false)
  const [page, setPage] = useState(0)
  const [explanation, setExplanation] = useState('')
  const PAGE_SIZE = 25
  const pct = totalFlags > 0 ? ((check.flag_count / totalFlags) * 100).toFixed(1) : '0'
  const rows = check.flagged_rows.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE)
  const totalPages = Math.ceil(check.flagged_rows.length / PAGE_SIZE)
  const cols = check.flagged_rows[0] ? Object.keys(check.flagged_rows[0]).filter((k) => !k.startsWith('_')) : []

  const sev = check.severity
  const badgeClass = sev === 'critical' ? 'badge-critical' : sev === 'warning' ? 'badge-warning' : 'badge-info'

  const explainMutation = useMutation({
    mutationFn: () =>
      explainFlags(
        check.check_name,
        check.severity,
        check.flag_count,
        totalRows,
        check.flagged_rows.slice(0, 5),
        {},
        groqApiKey,
        model,
      ),
    onSuccess: (data) => setExplanation(data.explanation),
  })

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
          {/* AI Explain button */}
          {groqApiKey && (
            <div className="space-y-2">
              <button
                onClick={() => explainMutation.mutate()}
                disabled={explainMutation.isPending}
                className="btn-ghost flex items-center gap-1.5 text-xs"
              >
                <Sparkles size={11} className="text-accent" />
                {explainMutation.isPending ? 'Explaining…' : 'Explain with AI'}
              </button>
              {explainMutation.isError && (
                <p className="text-xs text-critical">{(explainMutation.error as Error).message}</p>
              )}
              {explanation && (
                <div className="p-3 rounded-lg bg-accent/5 border border-accent/20 text-xs text-tx leading-relaxed whitespace-pre-wrap">
                  {explanation}
                </div>
              )}
            </div>
          )}

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
  const { results, jobId, jobStatus, jobError, rowCount, groqApiKey, config, supplementalChecks } = useAppStore()
  const [downloading, setDownloading] = useState(false)
  const [summary, setSummary] = useState('')

  const summaryMutation = useMutation({
    mutationFn: () =>
      generateQCSummary(
        results!.total_flags,
        rowCount ?? 0,
        results!.checks.map((c) => ({
          check_name: c.check_name,
          severity: c.severity,
          flag_count: c.flag_count,
        })),
        groqApiKey,
        config.verbatim_check.model,
      ),
    onSuccess: (data) => setSummary(data.summary),
  })

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
  const totalChecks = results.checks.length + supplementalChecks.length
  const totalFlags = results.total_flags + supplementalChecks.reduce((s, c) => s + c.flag_count, 0)

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Metric cards */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
        <MetricCard label="Checks run" value={totalChecks} />
        <MetricCard label="Total flags" value={totalFlags} />
        <MetricCard label="Critical" value={results.flagged_by_severity.critical ?? 0} color="text-critical" />
        <MetricCard label="Warnings" value={results.flagged_by_severity.warning ?? 0} color="text-warning" />
        <MetricCard label="Info" value={results.flagged_by_severity.info ?? 0} color="text-info" />
      </div>

      {/* AI Summary */}
      {groqApiKey && (
        <div className="card p-4 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-medium text-tx flex items-center gap-1.5">
              <FileText size={14} className="text-accent" />
              AI Executive Summary
            </h3>
            <button
              onClick={() => summaryMutation.mutate()}
              disabled={summaryMutation.isPending}
              className="btn-ghost flex items-center gap-1.5 text-xs"
            >
              <Sparkles size={11} className="text-accent" />
              {summaryMutation.isPending ? 'Generating…' : summary ? 'Regenerate' : 'Generate summary'}
            </button>
          </div>
          {summaryMutation.isError && (
            <p className="text-xs text-critical">{(summaryMutation.error as Error).message}</p>
          )}
          {summary && (
            <p className="text-xs text-tx leading-relaxed whitespace-pre-wrap">{summary}</p>
          )}
          {!summary && !summaryMutation.isPending && (
            <p className="text-xs text-muted">
              Click "Generate summary" to get an AI-written executive narrative of these QC results.
            </p>
          )}
        </div>
      )}

      {/* Download */}
      <div className="flex justify-end">
        <button onClick={handleDownload} disabled={downloading} className="btn-ghost flex items-center gap-2">
          <Download size={14} />
          {downloading ? 'Downloading…' : 'Download Excel report'}
        </button>
      </div>

      {/* Main pipeline checks */}
      <div className="space-y-2">
        <h3 className="text-xs font-semibold text-muted uppercase tracking-wide">Main QC Pipeline</h3>
        {sorted.map((check) => (
          <CheckAccordion
            key={check.check_name}
            check={check}
            totalFlags={totalFlags}
            totalRows={rowCount ?? 0}
            groqApiKey={groqApiKey}
            model={config.verbatim_check.model}
          />
        ))}
        {results.total_flags === 0 && supplementalChecks.length === 0 && (
          <div className="flex items-center gap-2 text-accent text-sm justify-center py-8">
            <Info size={16} />
            No issues found — your data looks clean!
          </div>
        )}
      </div>

      {/* Supplemental checks from tabs */}
      {supplementalChecks.length > 0 && (
        <div className="space-y-2">
          <h3 className="text-xs font-semibold text-muted uppercase tracking-wide">Ad-hoc Checks (from tabs)</h3>
          {supplementalChecks.map((check) => (
            <CheckAccordion
              key={check.check_name}
              check={check}
              totalFlags={totalFlags}
              totalRows={rowCount ?? 0}
              groqApiKey={groqApiKey}
              model={config.verbatim_check.model}
            />
          ))}
        </div>
      )}
    </div>
  )
}
