import React, { useCallback, useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { Upload, GitCompare, ArrowUp, ArrowDown, Minus } from 'lucide-react'
import { useAppStore } from '../../store/appStore'
import {
  uploadWave2, computeDiff, computeInterviewerShift,
  type DiffResponse, type InterviewerShiftRow,
} from '../../api/compare'

type SubTab = 'new' | 'removed' | 'changed' | 'interviewers'

function DataTable({ rows, caption }: { rows: Record<string, unknown>[]; caption?: string }) {
  const [page, setPage] = useState(0)
  const PAGE = 50
  const cols = rows[0] ? Object.keys(rows[0]) : []
  const totalPages = Math.ceil(rows.length / PAGE)
  const visible = rows.slice(page * PAGE, (page + 1) * PAGE)

  return (
    <div className="space-y-2">
      {caption && <p className="text-xs text-muted">{caption}</p>}
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-line">
              {cols.map((c) => <th key={c} className="text-left py-1.5 px-2 text-muted font-normal whitespace-nowrap">{c}</th>)}
            </tr>
          </thead>
          <tbody>
            {visible.map((row, i) => (
              <tr key={i} className="border-b border-line/50 hover:bg-surface2 transition-colors">
                {cols.map((c) => <td key={c} className="py-1.5 px-2 whitespace-nowrap text-tx">{String(row[c] ?? '')}</td>)}
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
  )
}

function MetricCard({ label, value, color }: { label: string; value: number; color?: string }) {
  return (
    <div className="card2 px-4 py-3 space-y-1">
      <p className="label">{label}</p>
      <p className={`text-2xl font-display font-extrabold ${color ?? 'text-tx'}`}>{value}</p>
    </div>
  )
}

export function WaveCompare() {
  const { fileId, filename } = useAppStore()
  const [wave2FileId, setWave2FileId] = useState<string | null>(null)
  const [wave2Info, setWave2Info] = useState<{ filename: string; rows: number; columns: number; column_names: string[] } | null>(null)
  const [idCol, setIdCol] = useState('')
  const [compareCols, setCompareCols] = useState<string[]>([])
  const [diffResult, setDiffResult] = useState<DiffResponse | null>(null)
  const [activeTab, setActiveTab] = useState<SubTab>('new')
  const [intCol, setIntCol] = useState('')
  const [shiftRows, setShiftRows] = useState<InterviewerShiftRow[]>([])
  const [intColName, setIntColName] = useState('')

  const uploadMutation = useMutation({
    mutationFn: (file: File) => uploadWave2(file),
    onSuccess: (data) => {
      setWave2FileId(data.file_id)
      setWave2Info({ filename: data.filename ?? '', rows: data.rows, columns: data.columns, column_names: data.column_names })
      setCompareCols((data.column_names ?? []).slice(0, 10))
    },
  })

  const diffMutation = useMutation({
    mutationFn: () => computeDiff(fileId!, wave2FileId!, idCol, compareCols),
    onSuccess: (data) => { setDiffResult(data); setActiveTab('new') },
  })

  const shiftMutation = useMutation({
    mutationFn: () => computeInterviewerShift(fileId!, wave2FileId!, intCol),
    onSuccess: (data) => { setShiftRows(data.rows); setIntColName(data.interviewer_column) },
  })

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    const file = e.dataTransfer.files[0]
    if (file) uploadMutation.mutate(file)
  }, [uploadMutation])

  const summary = diffResult?.summary
  const commonCols = diffResult?.common_columns ?? wave2Info?.column_names ?? []

  const toggleCompareCol = (col: string) => {
    setCompareCols((cs) => cs.includes(col) ? cs.filter((c) => c !== col) : [...cs, col])
  }

  const SUB_TABS: { key: SubTab; label: string; count?: number }[] = [
    { key: 'new',          label: 'New records',  count: summary?.new_count },
    { key: 'removed',      label: 'Removed',       count: summary?.removed_count },
    { key: 'changed',      label: 'Changed values', count: summary?.changed_count },
    { key: 'interviewers', label: 'Interviewer shifts' },
  ]

  return (
    <div className="space-y-6 animate-fade-in">
      <div>
        <h2 className="font-display font-extrabold text-base text-tx">Wave Comparison</h2>
        <p className="text-xs text-muted mt-0.5">
          Upload a second wave of the same survey to compare records, detect changes, and track interviewer shifts.
        </p>
      </div>

      {/* Upload wave 2 */}
      {!wave2FileId ? (
        <div
          onDrop={onDrop}
          onDragOver={(e) => e.preventDefault()}
          className="border-2 border-dashed border-line rounded-lg p-8 text-center space-y-3 hover:border-muted transition-colors"
        >
          <Upload size={24} className="text-muted mx-auto" />
          <p className="text-sm text-muted">Drop wave 2 file here, or</p>
          <label className="btn-ghost cursor-pointer inline-flex items-center gap-2 text-sm">
            <input
              type="file" accept=".csv,.xlsx,.xls" className="hidden"
              onChange={(e) => { const f = e.target.files?.[0]; if (f) uploadMutation.mutate(f) }}
            />
            Browse file
          </label>
          {uploadMutation.isPending && <p className="text-xs text-muted">Uploading…</p>}
          {uploadMutation.isError && (
            <p className="text-xs text-critical">{(uploadMutation.error as Error).message}</p>
          )}
        </div>
      ) : (
        <div className="card p-3 flex items-center justify-between">
          <div className="text-xs text-muted">
            <span className="text-tx font-medium">{wave2Info?.filename}</span>
            {' · '}{wave2Info?.rows?.toLocaleString()} rows · {wave2Info?.columns} columns
          </div>
          <button
            onClick={() => { setWave2FileId(null); setWave2Info(null); setDiffResult(null) }}
            className="text-xs text-critical hover:underline"
          >
            Remove
          </button>
        </div>
      )}

      {wave2FileId && (
        <>
          <div className="text-xs text-muted">
            Wave 1: <span className="text-tx">{filename}</span>
            {' '} · Wave 2: <span className="text-tx">{wave2Info?.filename}</span>
          </div>

          {/* ID column + compare columns */}
          <div className="space-y-3">
            <div className="space-y-1">
              <p className="text-xs text-muted">Unique ID column (to match records across waves)</p>
              <select className="w-full max-w-xs" value={idCol} onChange={(e) => setIdCol(e.target.value)}>
                <option value="">— select —</option>
                {commonCols.map((c) => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>

            {idCol && (
              <div className="space-y-1">
                <p className="text-xs text-muted">Columns to compare for changed values</p>
                <div className="flex flex-wrap gap-1.5 max-h-28 overflow-y-auto">
                  {commonCols.filter((c) => c !== idCol).map((col) => (
                    <button
                      key={col}
                      onClick={() => toggleCompareCol(col)}
                      className={`text-[10px] px-2 py-0.5 rounded border transition-colors ${
                        compareCols.includes(col)
                          ? 'border-accent text-accent bg-accent/10'
                          : 'border-line text-muted hover:border-muted'
                      }`}
                    >
                      {col}
                    </button>
                  ))}
                </div>
                <p className="text-[10px] text-muted">{compareCols.length} columns selected</p>
              </div>
            )}

            <button
              onClick={() => diffMutation.mutate()}
              disabled={!idCol || diffMutation.isPending}
              className="btn-primary flex items-center gap-2"
            >
              <GitCompare size={14} />
              {diffMutation.isPending ? 'Comparing…' : 'Compare waves'}
            </button>
            {diffMutation.isError && (
              <p className="text-xs text-critical">{(diffMutation.error as Error).message}</p>
            )}
          </div>
        </>
      )}

      {/* Results */}
      {diffResult && summary && (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <MetricCard label="New records" value={summary.new_count} color="text-accent" />
            <MetricCard label="Removed records" value={summary.removed_count} color="text-critical" />
            <MetricCard label="Matching records" value={summary.common_count} />
            <MetricCard label="Changed values" value={summary.changed_count} color="text-warning" />
          </div>

          {/* Sub-tabs */}
          <div className="border-b border-line flex gap-0">
            {SUB_TABS.map(({ key, label, count }) => (
              <button
                key={key}
                onClick={() => setActiveTab(key)}
                className={`px-4 py-2.5 text-xs border-b-2 transition-colors ${
                  activeTab === key ? 'border-accent text-accent' : 'border-transparent text-muted hover:text-tx'
                }`}
              >
                {label}{count !== undefined ? ` (${count})` : ''}
              </button>
            ))}
          </div>

          <div className="space-y-3">
            {activeTab === 'new' && (
              diffResult.new_rows.length > 0
                ? <DataTable rows={diffResult.new_rows} caption={`${diffResult.new_rows.length} new records in wave 2`} />
                : <p className="text-xs text-accent">No new records in wave 2.</p>
            )}

            {activeTab === 'removed' && (
              diffResult.removed_rows.length > 0
                ? <DataTable rows={diffResult.removed_rows} caption={`${diffResult.removed_rows.length} records present in wave 1 but not wave 2`} />
                : <p className="text-xs text-accent">No records removed in wave 2.</p>
            )}

            {activeTab === 'changed' && (
              diffResult.changed_rows.length > 0
                ? <DataTable rows={diffResult.changed_rows} caption={`${diffResult.changed_rows.length} records with changed values`} />
                : <p className="text-xs text-accent">No changed values found across selected columns.</p>
            )}

            {activeTab === 'interviewers' && (
              <div className="space-y-3">
                <div className="flex gap-2 items-end">
                  <div className="flex-1 space-y-1">
                    <p className="text-xs text-muted">Interviewer column</p>
                    <select className="w-full" value={intCol} onChange={(e) => setIntCol(e.target.value)}>
                      <option value="">— select —</option>
                      {commonCols.map((c) => <option key={c} value={c}>{c}</option>)}
                    </select>
                  </div>
                  <button
                    onClick={() => shiftMutation.mutate()}
                    disabled={!intCol || shiftMutation.isPending}
                    className="btn-primary shrink-0"
                  >
                    {shiftMutation.isPending ? 'Loading…' : 'Compare'}
                  </button>
                </div>
                {shiftMutation.isError && (
                  <p className="text-xs text-critical">{(shiftMutation.error as Error).message}</p>
                )}
                {shiftRows.length > 0 && (
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="border-b border-line">
                          {[intColName, 'wave1_count', 'wave2_count', 'change', 'change_pct'].map((c) => (
                            <th key={c} className="text-left py-2 px-3 text-muted font-normal whitespace-nowrap">
                              {c.replace(/_/g, ' ')}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {shiftRows.map((row, i) => (
                          <tr key={i} className="border-b border-line/50 hover:bg-surface2 transition-colors">
                            <td className="py-2 px-3 text-tx font-medium">{String(row[intColName] ?? '')}</td>
                            <td className="py-2 px-3 text-muted">{row.wave1_count}</td>
                            <td className="py-2 px-3 text-muted">{row.wave2_count}</td>
                            <td className={`py-2 px-3 font-medium ${row.change > 0 ? 'text-accent' : row.change < 0 ? 'text-critical' : 'text-muted'}`}>
                              <span className="flex items-center gap-1">
                                {row.change > 0 ? <ArrowUp size={10} /> : row.change < 0 ? <ArrowDown size={10} /> : <Minus size={10} />}
                                {row.change > 0 ? '+' : ''}{row.change}
                              </span>
                            </td>
                            <td className={`py-2 px-3 ${row.change_pct > 0 ? 'text-accent' : row.change_pct < 0 ? 'text-critical' : 'text-muted'}`}>
                              {row.change_pct > 0 ? '+' : ''}{row.change_pct}%
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  )
}
