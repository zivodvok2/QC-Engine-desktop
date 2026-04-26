import React, { useEffect, useMemo, useState } from 'react'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, Cell } from 'recharts'
import { Plus, Trash2, Target } from 'lucide-react'
import { useQueries } from '@tanstack/react-query'
import { useAppStore } from '../../store/appStore'
import { runEDA } from '../../api/eda'

interface QuotaCell {
  id: number
  column: string
  value: string
  target_n: number
  target_pct: number
}

interface QuotaRow extends QuotaCell {
  achieved_n: number
  achieved_pct: number
  fill_rate: number
  remaining: number
  status: 'OVERFILLED' | 'ON TRACK' | 'AT RISK' | 'BEHIND'
}

const TOOLTIP_STYLE = {
  contentStyle: { background: '#111318', border: '1px solid #1f2330', borderRadius: 6 },
  labelStyle: { color: '#e8eaf2' },
}

function statusStyle(s: string) {
  if (s === 'OVERFILLED') return 'text-critical'
  if (s === 'ON TRACK')   return 'text-accent'
  if (s === 'AT RISK')    return 'text-warning'
  return 'text-muted'
}

function statusIcon(s: string) {
  if (s === 'OVERFILLED') return '🔴'
  if (s === 'ON TRACK')   return '✅'
  if (s === 'AT RISK')    return '🟡'
  return '❌'
}

function barColor(s: string) {
  if (s === 'OVERFILLED') return '#f04a6a'
  if (s === 'ON TRACK')   return '#4af0a0'
  if (s === 'AT RISK')    return '#f0c04a'
  return '#666'
}

let _id = 0
const newId = () => ++_id

const STORAGE_KEY = 'ds_quota_cells'

export function Quotas() {
  const { fileId, columnNames, rowCount } = useAppStore()
  const [cells, setCells] = useState<QuotaCell[]>(() => {
    try {
      return JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]')
    } catch { return [] }
  })
  const [qCol, setQCol] = useState('')
  const [qVal, setQVal] = useState('')
  const [qN, setQN] = useState(0)
  const [qPct, setQPct] = useState(0)

  // Unique columns needed across all quota cells
  const uniqueColumns = useMemo(() => [...new Set(cells.map((c) => c.column))], [cells])

  // Fetch histogram (value counts) for each unique column
  const histQueries = useQueries({
    queries: uniqueColumns.map((col) => ({
      queryKey: ['quota-hist', fileId, col],
      enabled: !!fileId,
      staleTime: 60_000,
      queryFn: () =>
        runEDA({ file_id: fileId!, x_col: col, y_cols: [], chart_type: 'histogram', agg_func: 'count' }).then(
          (r) => ({ col, bins: r.data as { bin: string; count: number }[] }),
        ),
    })),
  })

  // Build lookup: column → value → count
  const valueCounts = useMemo<Record<string, Record<string, number>>>(() => {
    const out: Record<string, Record<string, number>> = {}
    for (const q of histQueries) {
      if (q.data) {
        out[q.data.col] = {}
        for (const { bin, count } of q.data.bins) {
          out[q.data.col][bin.toLowerCase()] = count
        }
      }
    }
    return out
  }, [histQueries])

  const totalRowsForCalc = rowCount || 1

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(cells))
  }, [cells])

  const computedRows: QuotaRow[] = cells.map((cell) => {
    let achieved_n = 0
    const colCounts = valueCounts[cell.column]
    if (colCounts) {
      achieved_n = colCounts[cell.value.toLowerCase()] ?? 0
    }

    const achieved_pct = Math.round((achieved_n / totalRowsForCalc) * 1000) / 10
    const fill_rate = cell.target_n > 0
      ? achieved_n / cell.target_n
      : cell.target_pct > 0 ? achieved_pct / cell.target_pct : 0
    const remaining = Math.max(0, cell.target_n - achieved_n)

    let status: QuotaRow['status']
    if (fill_rate > 1.05)   status = 'OVERFILLED'
    else if (fill_rate >= 0.90) status = 'ON TRACK'
    else if (fill_rate >= 0.60) status = 'AT RISK'
    else                        status = 'BEHIND'

    return { ...cell, achieved_n, achieved_pct, fill_rate, remaining, status }
  })

  const onTrack   = computedRows.filter((r) => r.status === 'ON TRACK').length
  const overfilled = computedRows.filter((r) => r.status === 'OVERFILLED').length
  const atRisk    = computedRows.filter((r) => r.status === 'AT RISK' || r.status === 'BEHIND').length

  const addCell = () => {
    if (!qCol || !qVal.trim()) return
    const target_n  = qN > 0 ? qN : Math.round((qPct / 100) * totalRowsForCalc)
    const target_pct = qPct > 0 ? qPct : Math.round((qN / totalRowsForCalc) * 1000) / 10
    if (!target_n && !target_pct) return
    setCells((cs) => [...cs, { id: newId(), column: qCol, value: qVal.trim(), target_n, target_pct }])
    setQCol(''); setQVal(''); setQN(0); setQPct(0)
  }

  const removeCell = (id: number) => setCells((cs) => cs.filter((c) => c.id !== id))

  const chartData = computedRows.map((r) => ({
    name: `${r.column}=${r.value}`,
    Target: r.target_n,
    Achieved: r.achieved_n,
    status: r.status,
  }))

  if (!fileId) {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-3 text-muted">
        <Target size={32} />
        <p className="text-sm">Upload a file to manage quota monitoring.</p>
      </div>
    )
  }

  return (
    <div className="space-y-6 animate-fade-in">
      <div>
        <h2 className="font-display font-extrabold text-base text-tx">Quota Monitoring</h2>
        <p className="text-xs text-muted mt-0.5">
          Define target quotas and track achieved sample counts in real time. Over-filled and at-risk cells are flagged automatically.
        </p>
      </div>

      {/* Add quota form */}
      <div className="card p-4 space-y-3">
        <h3 className="text-sm font-medium text-tx">Add Quota Cell</h3>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 items-end">
          <div className="space-y-1">
            <p className="text-xs text-muted">Column</p>
            <select className="w-full" value={qCol} onChange={(e) => setQCol(e.target.value)}>
              <option value="">— select —</option>
              {columnNames.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
          <div className="space-y-1">
            <p className="text-xs text-muted">Value</p>
            <input type="text" className="w-full" placeholder="Female" value={qVal} onChange={(e) => setQVal(e.target.value)} />
          </div>
          <div className="space-y-1">
            <p className="text-xs text-muted">Target n</p>
            <input type="number" className="w-full" min={0} value={qN || ''} onChange={(e) => setQN(+e.target.value)} placeholder="0" />
          </div>
          <div className="space-y-1">
            <p className="text-xs text-muted">Target %</p>
            <input type="number" className="w-full" min={0} max={100} step={0.1} value={qPct || ''} onChange={(e) => setQPct(+e.target.value)} placeholder="0.0" />
          </div>
        </div>
        <p className="text-[10px] text-muted">Enter either Target n or Target % — the other will be calculated from the dataset total.</p>
        <button onClick={addCell} disabled={!qCol || !qVal.trim() || (!qN && !qPct)} className="btn-primary flex items-center gap-1.5">
          <Plus size={13} /> Add quota cell
        </button>
      </div>

      {cells.length === 0 && (
        <div className="flex flex-col items-center justify-center h-32 gap-2 text-muted">
          <p className="text-sm">No quota cells defined yet. Add your first above.</p>
        </div>
      )}

      {computedRows.length > 0 && (
        <>
          {/* Metrics */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {[
              { label: 'Quota cells', value: cells.length },
              { label: '✅ On track',  value: onTrack,   color: 'text-accent' },
              { label: '🔴 Overfilled', value: overfilled, color: 'text-critical' },
              { label: '⚠️ At risk / behind', value: atRisk, color: 'text-warning' },
            ].map(({ label, value, color }) => (
              <div key={label} className="card2 px-4 py-3 space-y-1">
                <p className="label">{label}</p>
                <p className={`text-2xl font-display font-extrabold ${color ?? 'text-tx'}`}>{value}</p>
              </div>
            ))}
          </div>

          {/* Table */}
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-line">
                  {['Column', 'Value', 'Target n', 'Target %', 'Achieved n', 'Achieved %', 'Fill rate', 'Remaining', 'Status', ''].map((h) => (
                    <th key={h} className="text-left py-2 px-3 text-muted font-normal whitespace-nowrap">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {computedRows.map((row) => (
                  <tr key={row.id} className="border-b border-line/50 hover:bg-surface2 transition-colors">
                    <td className="py-2 px-3 font-mono text-tx">{row.column}</td>
                    <td className="py-2 px-3 text-tx">{row.value}</td>
                    <td className="py-2 px-3 text-tx">{row.target_n.toLocaleString()}</td>
                    <td className="py-2 px-3 text-muted">{row.target_pct.toFixed(1)}%</td>
                    <td className="py-2 px-3 text-tx font-medium">{row.achieved_n.toLocaleString()}</td>
                    <td className="py-2 px-3 text-muted">{row.achieved_pct.toFixed(1)}%</td>
                    <td className="py-2 px-3">
                      <div className="flex items-center gap-1.5">
                        <div className="flex-1 bg-line rounded-full h-1.5 w-16">
                          <div
                            className="h-full rounded-full transition-all"
                            style={{
                              width: `${Math.min(row.fill_rate * 100, 100)}%`,
                              background: barColor(row.status),
                            }}
                          />
                        </div>
                        <span className={statusStyle(row.status)}>{(row.fill_rate * 100).toFixed(1)}%</span>
                      </div>
                    </td>
                    <td className="py-2 px-3 text-muted">{row.remaining.toLocaleString()}</td>
                    <td className={`py-2 px-3 font-medium text-xs ${statusStyle(row.status)}`}>
                      {statusIcon(row.status)} {row.status}
                    </td>
                    <td className="py-2 px-3">
                      <button onClick={() => removeCell(row.id)} className="text-muted hover:text-critical transition-colors">
                        <Trash2 size={12} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Bar chart */}
          {chartData.length > 0 && (
            <div className="card p-4">
              <h3 className="text-sm font-medium text-tx mb-3">Achieved vs. Target by Quota Cell</h3>
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={chartData} margin={{ top: 5, right: 20, left: 0, bottom: 60 }} barGap={4}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1f2330" />
                  <XAxis dataKey="name" tick={{ fill: '#8b90a8', fontSize: 10 }} angle={-35} textAnchor="end" interval={0} />
                  <YAxis tick={{ fill: '#8b90a8', fontSize: 10 }} />
                  <Tooltip {...TOOLTIP_STYLE} />
                  <Legend wrapperStyle={{ color: '#8b90a8', fontSize: 11, paddingTop: 8 }} />
                  <Bar dataKey="Target" fill="rgba(255,255,255,0.06)" stroke="rgba(255,255,255,0.2)" strokeWidth={1} radius={[3, 3, 0, 0] as [number,number,number,number]} />
                  <Bar dataKey="Achieved" radius={[3, 3, 0, 0] as [number,number,number,number]}>
                    {chartData.map((entry, i) => (
                      <Cell key={i} fill={barColor(entry.status)} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}

          <button
            onClick={() => { setCells([]); localStorage.removeItem(STORAGE_KEY) }}
            className="btn-ghost text-xs text-critical hover:text-critical border-critical/30"
          >
            Clear all quotas
          </button>
        </>
      )}
    </div>
  )
}
