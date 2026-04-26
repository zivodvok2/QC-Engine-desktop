import React, { useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import {
  BarChart, Bar, LineChart, Line, ScatterChart, Scatter,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, Cell,
} from 'recharts'
import { Play, AlertCircle, Sparkles, ChevronDown, ChevronUp } from 'lucide-react'
import { ColumnSelector } from '../columns/ColumnSelector'
import { runEDA } from '../../api/eda'
import { askDataQuestion } from '../../api/ai'
import { client } from '../../api/client'
import { useColumns } from '../../hooks/useColumns'
import { useAppStore } from '../../store/appStore'
import type { EDAResponse, EDABarData, EDAHeatmap } from '../../types'

const CHART_TYPES = ['bar', 'line', 'scatter', 'histogram', 'heatmap', 'box'] as const
const AGG_FUNCS = ['mean', 'sum', 'count', 'min', 'max']
const ACCENT_COLORS = ['#4af0a0', '#4a9ef0', '#f0c04a', '#f04a6a', '#c04af0', '#f08a4a']

const TOOLTIP_STYLE = {
  contentStyle: { background: '#111318', border: '1px solid #1f2330', borderRadius: 6 },
  labelStyle: { color: '#e8eaf2' },
  itemStyle: { color: '#4af0a0' },
}

function HeatmapChart({ data }: { data: EDAHeatmap }) {
  const { columns, matrix } = data
  const n = columns.length
  const cell = 52
  const labelW = 90
  const labelH = 24

  const getColor = (v: number | null) => {
    if (v === null) return '#1f2330'
    if (v >= 0) return `rgba(74,240,160,${Math.min(Math.abs(v), 1)})`
    return `rgba(240,74,106,${Math.min(Math.abs(v), 1)})`
  }

  return (
    <div className="overflow-auto">
      <svg width={labelW + n * cell} height={labelH + n * cell + 20}>
        {/* Column labels */}
        {columns.map((col, j) => (
          <text key={col} x={labelW + j * cell + cell / 2} y={labelH - 4} fill="#8b90a8" fontSize={10}
            textAnchor="middle" transform={`rotate(-40,${labelW + j * cell + cell / 2},${labelH - 4})`}>
            {col.length > 10 ? col.slice(0, 10) + '…' : col}
          </text>
        ))}
        {/* Row labels */}
        {columns.map((col, i) => (
          <text key={col} x={labelW - 4} y={labelH + i * cell + cell / 2 + 4} fill="#8b90a8" fontSize={10} textAnchor="end">
            {col.length > 12 ? col.slice(0, 12) + '…' : col}
          </text>
        ))}
        {/* Cells */}
        {matrix.map((row, i) =>
          row.map((val, j) => (
            <g key={`${i}-${j}`}>
              <rect x={labelW + j * cell} y={labelH + i * cell} width={cell} height={cell}
                fill={getColor(val)} rx={2} />
              {val !== null && (
                <text x={labelW + j * cell + cell / 2} y={labelH + i * cell + cell / 2 + 4}
                  fill="#e8eaf2" fontSize={9} textAnchor="middle">
                  {val.toFixed(2)}
                </text>
              )}
            </g>
          ))
        )}
      </svg>
    </div>
  )
}

function BoxPlotChart({ data }: { data: Record<string, unknown>[] }) {
  // Render box stats as a table with a mini visual bar
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-line">
            {['Name', 'Min', 'Q1', 'Median', 'Q3', 'Max', 'Outliers'].map((h) => (
              <th key={h} className="text-left py-2 px-3 text-muted font-normal">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row, i) => {
            const stats = Object.entries(row).find(([k]) => k !== 'name' && typeof row[k] === 'object')
            if (!stats) {
              const s = row as { name: string; min: number; q1: number; median: number; q3: number; max: number; outliers: number[] }
              return (
                <tr key={i} className="border-b border-line/50 hover:bg-surface2">
                  <td className="py-2 px-3 text-accent">{String(s.name)}</td>
                  <td className="py-2 px-3">{Number(s.min).toFixed(2)}</td>
                  <td className="py-2 px-3">{Number(s.q1).toFixed(2)}</td>
                  <td className="py-2 px-3 text-tx font-medium">{Number(s.median).toFixed(2)}</td>
                  <td className="py-2 px-3">{Number(s.q3).toFixed(2)}</td>
                  <td className="py-2 px-3">{Number(s.max).toFixed(2)}</td>
                  <td className="py-2 px-3 text-muted">{(s.outliers ?? []).length}</td>
                </tr>
              )
            }
            const [colName, s] = stats as [string, { min: number; q1: number; median: number; q3: number; max: number; outliers: number[] }]
            return (
              <tr key={i} className="border-b border-line/50 hover:bg-surface2">
                <td className="py-2 px-3 text-accent">{String(row.name)} / {colName}</td>
                <td className="py-2 px-3">{Number(s.min).toFixed(2)}</td>
                <td className="py-2 px-3">{Number(s.q1).toFixed(2)}</td>
                <td className="py-2 px-3 text-tx font-medium">{Number(s.median).toFixed(2)}</td>
                <td className="py-2 px-3">{Number(s.q3).toFixed(2)}</td>
                <td className="py-2 px-3">{Number(s.max).toFixed(2)}</td>
                <td className="py-2 px-3 text-muted">{(s.outliers ?? []).length}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

function ChartRenderer({ res }: { res: EDAResponse }) {
  const { chart_type: ct, data, metadata } = res
  const yKeys = (metadata.y_cols as string[] | undefined) ?? []
  const yKey = (metadata.y_col as string | undefined) ?? yKeys[0] ?? 'y'

  if (ct === 'heatmap') {
    return <HeatmapChart data={data as EDAHeatmap} />
  }

  if (ct === 'box') {
    return <BoxPlotChart data={data as Record<string, unknown>[]} />
  }

  const arr = data as Record<string, unknown>[]

  if (ct === 'histogram') {
    return (
      <ResponsiveContainer width="100%" height={280}>
        <BarChart data={arr} margin={{ top: 4, right: 8, left: 0, bottom: 40 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1f2330" />
          <XAxis dataKey="bin" tick={{ fill: '#8b90a8', fontSize: 10 }} angle={-35} textAnchor="end" interval={0} />
          <YAxis tick={{ fill: '#8b90a8', fontSize: 11 }} />
          <Tooltip {...TOOLTIP_STYLE} />
          <Bar dataKey="count" fill="#4af0a0" radius={[3, 3, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    )
  }

  if (ct === 'scatter') {
    return (
      <ResponsiveContainer width="100%" height={280}>
        <ScatterChart margin={{ top: 4, right: 8, left: 0, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1f2330" />
          <XAxis dataKey="x" name={String(metadata.x_col ?? 'x')} tick={{ fill: '#8b90a8', fontSize: 11 }} />
          <YAxis dataKey="y" name={yKey} tick={{ fill: '#8b90a8', fontSize: 11 }} />
          <Tooltip {...TOOLTIP_STYLE} cursor={{ strokeDasharray: '3 3' }} />
          <Scatter data={arr} fill="#4af0a0" fillOpacity={0.7} />
        </ScatterChart>
      </ResponsiveContainer>
    )
  }

  // bar or line
  const Chart = ct === 'line' ? LineChart : BarChart
  const DataEl = ct === 'line' ? Line : Bar

  return (
    <ResponsiveContainer width="100%" height={280}>
      <Chart data={arr} margin={{ top: 4, right: 8, left: 0, bottom: 4 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#1f2330" />
        <XAxis dataKey="name" tick={{ fill: '#8b90a8', fontSize: 11 }} />
        <YAxis tick={{ fill: '#8b90a8', fontSize: 11 }} />
        <Tooltip {...TOOLTIP_STYLE} />
        <Legend wrapperStyle={{ color: '#8b90a8', fontSize: 12 }} />
        {yKeys.map((k, i) =>
          ct === 'line'
            ? <Line key={k} type="monotone" dataKey={k} stroke={ACCENT_COLORS[i % ACCENT_COLORS.length]} dot={false} strokeWidth={2} />
            : <Bar key={k} dataKey={k} fill={ACCENT_COLORS[i % ACCENT_COLORS.length]} radius={[3, 3, 0, 0]} />
        )}
      </Chart>
    </ResponsiveContainer>
  )
}

interface SummaryData {
  shape: { rows: number; columns: number }
  numeric_summary: { column: string; count: number; mean: number; std: number; min: number; p25: number; median: number; p75: number; max: number }[]
  missing_summary: { column: string; missing_count: number; missing_pct: number }[]
  categorical_summary: { column: string; unique_count: number; top_values: { value: string; count: number }[] }[]
}

type SummaryTab = 'numeric' | 'missing' | 'categorical'

export function EDA() {
  const { fileId, groqApiKey } = useAppStore()
  const { columns, dtypes } = useColumns()

  const [chartType, setChartType] = useState<(typeof CHART_TYPES)[number]>('bar')
  const [xCol, setXCol] = useState<string[]>([])
  const [yCols, setYCols] = useState<string[]>([])
  const [colorCol, setColorCol] = useState<string[]>([])
  const [aggFunc, setAggFunc] = useState('mean')
  const [edaResult, setEdaResult] = useState<EDAResponse | null>(null)

  // Summary stats
  const [summaryTab, setSummaryTab] = useState<SummaryTab>('numeric')
  const { data: summary, isLoading: summaryLoading } = useQuery({
    queryKey: ['eda-summary', fileId],
    enabled: !!fileId,
    queryFn: () => client.get<SummaryData>(`/api/eda/summary/${fileId}`).then((r) => r.data),
    staleTime: 60_000,
  })

  // AI question
  const [aiOpen, setAiOpen] = useState(false)
  const [question, setQuestion] = useState('')
  const [answer, setAnswer] = useState('')
  const aiMutation = useMutation({
    mutationFn: () => askDataQuestion(fileId!, question, groqApiKey),
    onSuccess: (data) => setAnswer(data.answer),
  })

  const mutation = useMutation({
    mutationFn: () =>
      runEDA({
        file_id: fileId!,
        x_col: xCol[0] ?? '',
        y_cols: yCols,
        color_col: colorCol[0],
        chart_type: chartType,
        agg_func: aggFunc,
      }),
    onSuccess: setEdaResult,
  })

  const hideX = chartType === 'histogram' || chartType === 'heatmap'

  return (
    <div className="space-y-6 animate-fade-in">
      <div>
        <h2 className="font-display font-extrabold text-base text-tx">Exploratory Data Analysis</h2>
        <p className="text-xs text-muted mt-0.5">Build interactive charts and explore summary statistics.</p>
      </div>

      {/* Summary stats */}
      {summary && (
        <div className="card border-line">
          <div className="px-4 py-3 border-b border-line flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-tx">Dataset Summary</p>
              <p className="text-[10px] text-muted">{summary.shape.rows.toLocaleString()} rows · {summary.shape.columns} columns</p>
            </div>
            <div className="flex gap-0">
              {(['numeric', 'missing', 'categorical'] as SummaryTab[]).map((t) => (
                <button key={t} onClick={() => setSummaryTab(t)}
                  className={`text-xs px-3 py-1.5 border-b-2 transition-colors capitalize ${summaryTab === t ? 'border-accent text-accent' : 'border-transparent text-muted hover:text-tx'}`}>
                  {t}
                </button>
              ))}
            </div>
          </div>
          <div className="p-4 overflow-x-auto max-h-64 overflow-y-auto">
            {summaryTab === 'numeric' && (
              summary.numeric_summary.length === 0
                ? <p className="text-xs text-muted">No numeric columns found.</p>
                : (
                  <table className="w-full text-xs">
                    <thead><tr className="border-b border-line">
                      {['Column', 'Count', 'Mean', 'Std', 'Min', 'P25', 'Median', 'P75', 'Max'].map((h) => (
                        <th key={h} className="text-left py-1.5 px-2 text-muted font-normal whitespace-nowrap">{h}</th>
                      ))}
                    </tr></thead>
                    <tbody>
                      {summary.numeric_summary.map((row) => (
                        <tr key={row.column} className="border-b border-line/50 hover:bg-surface2">
                          <td className="py-1.5 px-2 font-mono text-accent">{row.column}</td>
                          {[row.count, row.mean, row.std, row.min, row.p25, row.median, row.p75, row.max].map((v, i) => (
                            <td key={i} className="py-1.5 px-2 text-tx tabular-nums">
                              {typeof v === 'number' && !Number.isInteger(v) ? v.toFixed(4) : v}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )
            )}
            {summaryTab === 'missing' && (
              summary.missing_summary.length === 0
                ? <p className="text-xs text-accent">No missing values found.</p>
                : (
                  <table className="w-full text-xs">
                    <thead><tr className="border-b border-line">
                      {['Column', 'Missing count', 'Missing %'].map((h) => (
                        <th key={h} className="text-left py-1.5 px-2 text-muted font-normal">{h}</th>
                      ))}
                    </tr></thead>
                    <tbody>
                      {summary.missing_summary.map((row) => (
                        <tr key={row.column} className="border-b border-line/50 hover:bg-surface2">
                          <td className="py-1.5 px-2 font-mono text-tx">{row.column}</td>
                          <td className="py-1.5 px-2 text-warning">{row.missing_count.toLocaleString()}</td>
                          <td className="py-1.5 px-2 text-warning">{row.missing_pct.toFixed(2)}%</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )
            )}
            {summaryTab === 'categorical' && (
              summary.categorical_summary.length === 0
                ? <p className="text-xs text-muted">No categorical columns found.</p>
                : (
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                    {summary.categorical_summary.map((col) => (
                      <div key={col.column} className="space-y-1 p-2 rounded border border-line">
                        <p className="text-[10px] font-mono text-accent">{col.column}</p>
                        <p className="text-[10px] text-muted">{col.unique_count} unique values</p>
                        {col.top_values.map((v) => (
                          <div key={v.value} className="flex items-center gap-1.5">
                            <div className="flex-1 bg-line rounded-full h-1" style={{ position: 'relative' }}>
                              <div className="h-full rounded-full bg-accent/40" style={{ width: `${Math.min(v.count / (col.top_values[0]?.count || 1) * 100, 100)}%` }} />
                            </div>
                            <span className="text-[9px] text-muted w-12 text-right truncate">{v.value}</span>
                            <span className="text-[9px] text-tx w-8 text-right">{v.count}</span>
                          </div>
                        ))}
                      </div>
                    ))}
                  </div>
                )
            )}
          </div>
        </div>
      )}

      {/* AI data question */}
      <div className="card border-line">
        <button
          onClick={() => setAiOpen((o) => !o)}
          className="w-full flex items-center justify-between px-4 py-3 text-xs text-muted hover:text-tx transition-colors"
        >
          <span className="flex items-center gap-1.5"><Sparkles size={11} className="text-accent" /> Ask a question about your data (AI)</span>
          {aiOpen ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
        </button>
        {aiOpen && (
          <div className="px-4 pb-4 pt-3 border-t border-line space-y-3">
            <p className="text-[10px] text-muted">
              Groq AI will answer questions based on the dataset summary.
              {!groqApiKey && <span className="text-warning ml-1">Set Groq API key in Settings first.</span>}
            </p>
            <div className="flex gap-2">
              <input
                type="text" className="flex-1 text-sm" value={question}
                onChange={(e) => setQuestion(e.target.value)}
                placeholder="e.g. Which columns have the most missing values?"
                onKeyDown={(e) => e.key === 'Enter' && !aiMutation.isPending && groqApiKey && question.trim() && aiMutation.mutate()}
              />
              <button
                onClick={() => aiMutation.mutate()}
                disabled={!question.trim() || !groqApiKey || !fileId || aiMutation.isPending}
                className="btn-primary flex items-center gap-1.5"
              >
                <Sparkles size={12} />
                {aiMutation.isPending ? 'Thinking…' : 'Ask'}
              </button>
            </div>
            {aiMutation.isError && <p className="text-xs text-critical">{(aiMutation.error as Error).message}</p>}
            {answer && (
              <div className="p-3 rounded-lg bg-surface2 border border-line text-xs text-tx whitespace-pre-wrap leading-relaxed">
                {answer}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Chart builder */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Controls */}
        <div className="space-y-4 card p-4">
          <div className="space-y-1">
            <p className="label">Chart type</p>
            <div className="flex flex-wrap gap-1.5">
              {CHART_TYPES.map((t) => (
                <button key={t} onClick={() => setChartType(t)}
                  className={`text-xs px-2.5 py-1 rounded-full border transition-all capitalize
                    ${chartType === t ? 'border-accent bg-accent/10 text-accent' : 'border-line text-muted hover:border-muted hover:text-tx'}`}>
                  {t}
                </button>
              ))}
            </div>
          </div>

          {!hideX && (
            <ColumnSelector label="X axis" multi={false} selected={xCol} onChange={setXCol} />
          )}

          <ColumnSelector label={chartType === 'heatmap' ? 'Columns (leave empty for all numeric)' : 'Y axis'} multi selected={yCols} onChange={setYCols} />

          {!hideX && (
            <ColumnSelector label="Color / group by (optional)" multi={false} selected={colorCol} onChange={setColorCol} />
          )}

          {!['histogram', 'heatmap', 'scatter', 'box'].includes(chartType) && (
            <div className="space-y-1">
              <p className="label">Aggregation</p>
              <select value={aggFunc} onChange={(e) => setAggFunc(e.target.value)} className="w-full">
                {AGG_FUNCS.map((f) => <option key={f}>{f}</option>)}
              </select>
            </div>
          )}

          <button
            onClick={() => mutation.mutate()}
            disabled={!fileId || mutation.isPending}
            className="btn-primary w-full flex items-center justify-center gap-2"
          >
            <Play size={14} />
            {mutation.isPending ? 'Loading…' : 'Plot'}
          </button>

          {mutation.isError && (
            <div className="flex items-center gap-2 text-critical text-xs">
              <AlertCircle size={12} />
              {(mutation.error as Error).message}
            </div>
          )}
        </div>

        {/* Chart */}
        <div className="lg:col-span-2 card p-4 min-h-72">
          {edaResult ? (
            <ChartRenderer res={edaResult} />
          ) : (
            <div className="flex items-center justify-center h-full text-muted text-sm">
              Configure a chart and click Plot.
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
