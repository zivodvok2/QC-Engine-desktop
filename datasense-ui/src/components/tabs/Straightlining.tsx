import React, { useState } from 'react'
import { Play, AlertCircle } from 'lucide-react'
import { useMutation } from '@tanstack/react-query'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import { ColumnSelector } from '../columns/ColumnSelector'
import { runQC, getStatus, getResults } from '../../api/qc'
import { useAppStore } from '../../store/appStore'
import type { QCResults } from '../../types'

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms))

async function runAndWait(fileId: string, slConfig: QCResults['checks'][0] extends infer _ ? Parameters<typeof runQC>[1] : never): Promise<QCResults> {
  const job = await runQC(fileId, slConfig)
  let status = await getStatus(job.job_id)
  while (status.status === 'queued' || status.status === 'running') {
    await sleep(1500)
    status = await getStatus(job.job_id)
  }
  if (status.status === 'failed') throw new Error('QC job failed')
  return getResults(job.job_id)
}

export function Straightlining() {
  const { fileId, config } = useAppStore()
  const [baseVar, setBaseVar] = useState<string[]>([])
  const [qCols, setQCols] = useState<string[]>([])
  const [threshold, setThreshold] = useState(0.9)
  const [minQ, setMinQ] = useState(3)
  const [result, setResult] = useState<QCResults | null>(null)

  const mutation = useMutation({
    mutationFn: () =>
      runAndWait(fileId!, {
        ...config,
        straightlining: {
          enabled: true,
          question_columns: qCols,
          threshold,
          min_questions: minQ,
          interviewer_column: baseVar[0] ?? '',
        },
      }),
    onSuccess: setResult,
  })

  const slCheck = result?.checks.find((c) => c.check_name === 'straightlining_check')
  const total = result?.total_flags ?? 0

  // Bar chart: flag count per base variable value
  const chartData = (() => {
    if (!slCheck || !baseVar[0]) return []
    const counts: Record<string, number> = {}
    for (const row of slCheck.flagged_rows) {
      const key = String(row[baseVar[0]] ?? 'Unknown')
      counts[key] = (counts[key] ?? 0) + 1
    }
    return Object.entries(counts)
      .map(([name, count]) => ({ name, count }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 20)
  })()

  return (
    <div className="space-y-6 max-w-3xl animate-fade-in">
      <div>
        <h2 className="font-display font-extrabold text-base text-tx">Straightlining Detection</h2>
        <p className="text-xs text-muted mt-0.5">Identify respondents who gave identical answers across all rating scale questions.</p>
      </div>

      <div className="card p-4 space-y-4">
        <ColumnSelector label="Base variable (e.g. interviewer ID)" multi={false}
          selected={baseVar} onChange={setBaseVar} />

        <ColumnSelector label="Question columns (rating scales)" multi
          selected={qCols} onChange={setQCols} />

        <div className="flex flex-wrap gap-4">
          <div className="space-y-1 flex-1 min-w-36">
            <p className="text-xs text-muted">Threshold — {threshold.toFixed(2)}</p>
            <input type="range" min={0.5} max={1} step={0.05} className="w-full" value={threshold}
              onChange={(e) => setThreshold(parseFloat(e.target.value))} />
          </div>
          <div className="space-y-1">
            <p className="text-xs text-muted">Min questions</p>
            <input type="number" className="w-24" min={2} max={50} value={minQ}
              onChange={(e) => setMinQ(+e.target.value)} />
          </div>
        </div>

        <button
          onClick={() => mutation.mutate()}
          disabled={!fileId || qCols.length === 0 || mutation.isPending}
          className="btn-primary flex items-center gap-2"
        >
          <Play size={14} />
          {mutation.isPending ? 'Running…' : 'Run check'}
        </button>

        {mutation.isError && (
          <div className="flex items-center gap-2 text-critical text-sm">
            <AlertCircle size={14} />
            {(mutation.error as Error).message}
          </div>
        )}
      </div>

      {slCheck && (
        <div className="space-y-4 animate-fade-in">
          <div className="grid grid-cols-3 gap-3">
            <div className="card2 px-4 py-3">
              <p className="label">Flagged</p>
              <p className="text-2xl font-display font-extrabold text-critical">{slCheck.flag_count}</p>
            </div>
            <div className="card2 px-4 py-3">
              <p className="label">Total rows</p>
              <p className="text-2xl font-display font-extrabold">{result?.checks[0]?.flagged_rows.length ?? '—'}</p>
            </div>
            <div className="card2 px-4 py-3">
              <p className="label">% flagged</p>
              <p className="text-2xl font-display font-extrabold text-warning">
                {total > 0 ? ((slCheck.flag_count / total) * 100).toFixed(1) : 0}%
              </p>
            </div>
          </div>

          {chartData.length > 0 && (
            <div className="card p-4">
              <p className="label mb-3">Flags by {baseVar[0] ?? 'base variable'}</p>
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={chartData} margin={{ top: 0, right: 8, left: 0, bottom: 40 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1f2330" />
                  <XAxis dataKey="name" tick={{ fill: '#8b90a8', fontSize: 11 }} angle={-35} textAnchor="end" interval={0} />
                  <YAxis tick={{ fill: '#8b90a8', fontSize: 11 }} />
                  <Tooltip contentStyle={{ background: '#111318', border: '1px solid #1f2330', borderRadius: 6 }} labelStyle={{ color: '#e8eaf2' }} itemStyle={{ color: '#4af0a0' }} />
                  <Bar dataKey="count" fill="#4af0a0" radius={[3, 3, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}

          {slCheck.flag_count > 0 && (
            <div className="card p-4 overflow-x-auto">
              <p className="label mb-3">Flagged respondents</p>
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-line">
                    {Object.keys(slCheck.flagged_rows[0] ?? {}).filter((k) => !k.startsWith('_')).map((k) => (
                      <th key={k} className="text-left py-1.5 px-2 text-muted font-normal whitespace-nowrap">{k}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {slCheck.flagged_rows.slice(0, 100).map((row, i) => (
                    <tr key={i} className="border-b border-line/50 hover:bg-surface2 transition-colors">
                      {Object.entries(row).filter(([k]) => !k.startsWith('_')).map(([k, v]) => (
                        <td key={k} className="py-1.5 px-2 whitespace-nowrap">{String(v ?? '')}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
