import React, { useMemo, useState } from 'react'
import { Search, Filter } from 'lucide-react'
import { useAppStore } from '../../store/appStore'
import { useColumns } from '../../hooks/useColumns'

export function DataPreview() {
  const { previewRows, columnNames } = useAppStore()
  const { isLoading } = useColumns()
  const [search, setSearch] = useState('')
  const [visibleCols, setVisibleCols] = useState<string[]>([])

  const displayCols = visibleCols.length > 0 ? visibleCols : columnNames

  const filtered = useMemo(() => {
    if (!search.trim()) return previewRows
    const q = search.toLowerCase()
    return previewRows.filter((row) =>
      Object.values(row).some((v) => String(v ?? '').toLowerCase().includes(q)),
    )
  }, [previewRows, search])

  const toggleCol = (col: string) => {
    setVisibleCols((prev) =>
      prev.includes(col) ? prev.filter((c) => c !== col) : [...prev, col],
    )
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-48 text-muted text-sm">
        Loading preview…
      </div>
    )
  }

  if (previewRows.length === 0) {
    return (
      <div className="flex items-center justify-center h-48 text-muted text-sm">
        Upload a file to preview data.
      </div>
    )
  }

  return (
    <div className="space-y-4 animate-fade-in">
      <div>
        <h2 className="font-display font-extrabold text-base text-tx">Data Preview</h2>
        <p className="text-xs text-muted mt-0.5">
          Showing {filtered.length} of {previewRows.length} sample rows · {columnNames.length} columns
        </p>
      </div>

      {/* Controls */}
      <div className="flex flex-wrap gap-3">
        <div className="relative flex-1 min-w-48">
          <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted" />
          <input
            type="text"
            className="w-full pl-8"
            placeholder="Search rows…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
      </div>

      {/* Column filter chips */}
      {columnNames.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          <span className="text-xs text-muted flex items-center gap-1 mr-1">
            <Filter size={11} /> Columns:
          </span>
          {columnNames.map((col) => {
            const active = visibleCols.includes(col)
            return (
              <button
                key={col}
                onClick={() => toggleCol(col)}
                className={`text-xs px-2 py-0.5 rounded-full border transition-all
                  ${active ? 'border-accent bg-accent/10 text-accent' : 'border-line text-muted hover:border-muted'}`}
              >
                {col}
              </button>
            )
          })}
          {visibleCols.length > 0 && (
            <button onClick={() => setVisibleCols([])} className="text-xs text-muted hover:text-tx underline">
              Show all
            </button>
          )}
        </div>
      )}

      {/* Table */}
      <div className="overflow-auto rounded-lg border border-line">
        <table className="w-full text-xs">
          <thead className="sticky top-0 bg-surface2">
            <tr className="border-b border-line">
              <th className="text-left py-2 px-3 text-muted font-normal w-10">#</th>
              {displayCols.map((c) => (
                <th key={c} className="text-left py-2 px-3 text-muted font-normal whitespace-nowrap">{c}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filtered.map((row, i) => (
              <tr key={i} className="border-b border-line/50 hover:bg-surface2 transition-colors">
                <td className="py-1.5 px-3 text-muted">{i + 1}</td>
                {displayCols.map((c) => (
                  <td key={c} className="py-1.5 px-3 text-tx whitespace-nowrap max-w-xs truncate">
                    {String(row[c] ?? '')}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
        {filtered.length === 0 && (
          <p className="text-center py-8 text-muted text-xs">No rows match your search.</p>
        )}
      </div>
    </div>
  )
}
