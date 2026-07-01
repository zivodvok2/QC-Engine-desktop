import React from 'react'
import { Filter, X, Download, FileSpreadsheet } from 'lucide-react'

const C = {
  accent: '#00B5A3', muted: '#6B7280', surface: '#FFFFFF', surface2: '#F1F4F8',
  line: '#E2E6ED', tx: '#1B2A4A',
}

// ── CSV export ─────────────────────────────────────────────────────────────────
export function exportCSV(rows: Record<string, unknown>[], filename: string) {
  if (!rows.length) return
  const keys = Object.keys(rows[0])
  const csv = [
    keys.join(','),
    ...rows.map(r => keys.map(k => {
      const v = r[k]
      if (v === null || v === undefined) return ''
      const s = String(v)
      return s.includes(',') || s.includes('"') || s.includes('\n') ? `"${s.replace(/"/g, '""')}"` : s
    }).join(','))
  ].join('\n')
  const a = document.createElement('a')
  a.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv' }))
  a.download = filename
  a.click()
  URL.revokeObjectURL(a.href)
}

// ── Excel export via backend ───────────────────────────────────────────────────
export async function exportExcel(
  projectId: number,
  reportType: string,
  rows: Record<string, unknown>[],
  chartSpec: Record<string, unknown>,
  token: string,
  filename: string,
) {
  const res = await fetch(`/api/dashboard/projects/${projectId}/export`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
    body: JSON.stringify({ report_type: reportType, rows, chart_spec: chartSpec }),
  })
  if (!res.ok) throw new Error('Export failed')
  const blob = await res.blob()
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = filename
  a.click()
  URL.revokeObjectURL(a.href)
}

// ── Select helper ──────────────────────────────────────────────────────────────
function FilterSelect({
  label, value, options, onChange,
}: { label: string; value: string; options: string[]; onChange: (v: string) => void }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-[10px] text-muted uppercase tracking-wide">{label}</span>
      <select
        value={value}
        onChange={e => onChange(e.target.value)}
        className="bg-surface2 border border-line rounded px-2 py-1 text-xs text-tx min-w-[110px]"
      >
        <option value="">All</option>
        {options.map(o => <option key={o} value={o}>{o}</option>)}
      </select>
    </div>
  )
}

function FilterInput({
  label, value, onChange, type = 'text', placeholder = '',
}: { label: string; value: string; onChange: (v: string) => void; type?: string; placeholder?: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-[10px] text-muted uppercase tracking-wide">{label}</span>
      <input
        type={type}
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder={placeholder}
        className="bg-surface2 border border-line rounded px-2 py-1 text-xs text-tx w-32"
      />
    </div>
  )
}

export interface FilterDef {
  key: string
  label: string
  type: 'select' | 'input' | 'date'
  options?: string[]
  placeholder?: string
}

interface FilterBarProps {
  filters: Record<string, string>
  defs: FilterDef[]
  onChange: (key: string, val: string) => void
  onClear: () => void
  activeCount: number
  onCsvDownload: () => void
  onExcelDownload?: () => void
  isExporting?: boolean
  totalRows: number
  filteredRows: number
}

export function FilterBar({
  filters, defs, onChange, onClear, activeCount,
  onCsvDownload, onExcelDownload, isExporting,
  totalRows, filteredRows,
}: FilterBarProps) {
  return (
    <div className="card p-3 space-y-2">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <Filter size={13} className="text-muted" />
          <span className="text-xs font-medium text-tx">Filters</span>
          {activeCount > 0 && (
            <span className="bg-accent/15 text-accent text-[10px] px-1.5 py-0.5 rounded-full font-medium">
              {activeCount} active
            </span>
          )}
          <span className="text-[10px] text-muted">
            {filteredRows === totalRows ? `${totalRows} rows` : `${filteredRows} / ${totalRows} rows`}
          </span>
        </div>
        <div className="flex items-center gap-2">
          {activeCount > 0 && (
            <button onClick={onClear} className="flex items-center gap-1 text-xs text-muted hover:text-tx">
              <X size={11} /> Clear
            </button>
          )}
          <button
            onClick={onCsvDownload}
            className="btn-ghost flex items-center gap-1.5 text-xs py-1"
          >
            <Download size={12} /> CSV
          </button>
          {onExcelDownload && (
            <button
              onClick={onExcelDownload}
              disabled={isExporting}
              className="btn-primary flex items-center gap-1.5 text-xs py-1"
            >
              <FileSpreadsheet size={12} />
              {isExporting ? 'Generating…' : 'Excel Report'}
            </button>
          )}
        </div>
      </div>
      <div className="flex flex-wrap gap-3">
        {defs.map(def => {
          if (def.type === 'select') {
            return (
              <FilterSelect
                key={def.key}
                label={def.label}
                value={filters[def.key] ?? ''}
                options={def.options ?? []}
                onChange={v => onChange(def.key, v)}
              />
            )
          }
          return (
            <FilterInput
              key={def.key}
              label={def.label}
              value={filters[def.key] ?? ''}
              onChange={v => onChange(def.key, v)}
              type={def.type === 'date' ? 'date' : 'text'}
              placeholder={def.placeholder}
            />
          )
        })}
      </div>
    </div>
  )
}

export function useFilters<T extends Record<string, unknown>>(
  records: T[], filterKeys: (keyof T)[], dateField = 'interview_date',
) {
  const [filters, setFilters] = React.useState<Record<string, string>>({})

  const uniqueVals = React.useMemo(() => {
    const out: Record<string, string[]> = {}
    filterKeys.forEach(k => {
      const vals = [...new Set(records.map(r => String(r[k] ?? '')).filter(Boolean))].sort()
      out[k as string] = vals
    })
    return out
  }, [records])

  const filtered = React.useMemo(() => {
    return records.filter(r =>
      Object.entries(filters).every(([k, v]) => {
        if (!v) return true
        if (k === 'date_from') return (r[dateField] as string ?? '') >= v
        if (k === 'date_to') return (r[dateField] as string ?? '') <= v
        return String(r[k] ?? '') === v
      })
    )
  }, [records, filters])

  const activeCount = Object.values(filters).filter(Boolean).length

  const setFilter = (key: string, val: string) => setFilters(f => ({ ...f, [key]: val }))
  const clearFilters = () => setFilters({})

  return { filters, filtered, activeCount, setFilter, clearFilters, uniqueVals }
}
