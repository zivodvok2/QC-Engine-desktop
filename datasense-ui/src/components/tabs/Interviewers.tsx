import React, { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell,
} from 'recharts'
import { Users, AlertTriangle, Download, Sparkles, ChevronDown, ChevronUp } from 'lucide-react'
import { useAppStore } from '../../store/appStore'
import { computeRisk, type RiskRow } from '../../api/interviewers'
import { generateFeedbackLetter } from '../../api/ai'

const TOOLTIP_STYLE = {
  contentStyle: { background: '#111318', border: '1px solid #1f2330', borderRadius: 6 },
  labelStyle: { color: '#e8eaf2' },
  itemStyle: { color: '#4af0a0' },
}

function riskColor(score: number, red: number, amber: number) {
  if (score >= red) return '#f04a6a'
  if (score >= amber) return '#f0c04a'
  return '#4af0a0'
}

function riskBadge(level: string) {
  if (level === 'HIGH') return 'bg-critical/10 text-critical border border-critical/30'
  if (level === 'MEDIUM') return 'bg-warning/10 text-warning border border-warning/30'
  return 'bg-accent/10 text-accent border border-accent/30'
}

function MetricCard({ label, value, color }: { label: string; value: number | string; color?: string }) {
  return (
    <div className="card2 px-4 py-3 space-y-1">
      <p className="label">{label}</p>
      <p className={`text-2xl font-display font-extrabold ${color ?? 'text-tx'}`}>{value}</p>
    </div>
  )
}

export function Interviewers() {
  const { fileId, jobId, jobStatus, config, groqApiKey } = useAppStore()

  // Derive default interviewer column from config
  const defaultIntCol =
    config.interviewer_duration_check.interviewer_column ||
    config.interviewer_productivity_check.interviewer_column ||
    config.fabrication_check.interviewer_column || ''

  const [intCol, setIntCol] = useState(defaultIntCol)
  const [redThr, setRedThr] = useState(60)
  const [amberThr, setAmberThr] = useState(30)
  const [flagThr, setFlagThr] = useState(10)
  const [rows, setRows] = useState<RiskRow[]>([])
  const [intColName, setIntColName] = useState('')

  // Feedback letter state
  const [selectedInt, setSelectedInt] = useState('')
  const [letter, setLetter] = useState('')
  const [showMethods, setShowMethods] = useState(false)

  const riskMutation = useMutation({
    mutationFn: () => computeRisk(fileId!, jobId!, intCol, redThr, amberThr),
    onSuccess: (data) => {
      setRows(data.rows)
      setIntColName(data.interviewer_column)
      if (data.rows.length > 0) setSelectedInt(String(data.rows[0][data.interviewer_column] ?? ''))
    },
  })

  const letterMutation = useMutation({
    mutationFn: () => {
      const row = rows.find((r) => String(r[intColName]) === selectedInt)
      if (!row) throw new Error('Interviewer not found')
      return generateFeedbackLetter(selectedInt, row as Record<string, unknown>, groqApiKey)
    },
    onSuccess: (data) => setLetter(data.letter),
  })

  const canRun = !!fileId && !!jobId && jobStatus === 'complete' && !!intCol

  const high   = rows.filter((r) => r.risk_score >= redThr).length
  const medium = rows.filter((r) => r.risk_score >= amberThr && r.risk_score < redThr).length
  const low    = rows.filter((r) => r.risk_score < amberThr).length
  const aboveFlagThr = rows.filter((r) => r.flag_rate_pct > flagThr).length
  const top20 = rows.slice(0, 20)

  const downloadCSV = () => {
    const cols = Object.keys(rows[0] ?? {})
    const csv = [cols.join(','), ...rows.map((r) => cols.map((c) => JSON.stringify(r[c] ?? '')).join(','))].join('\n')
    const a = document.createElement('a')
    a.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv' }))
    a.download = 'interviewer_risk_scores.csv'
    a.click()
  }

  const downloadLetter = () => {
    if (!letter) return
    const a = document.createElement('a')
    a.href = URL.createObjectURL(new Blob([letter], { type: 'text/plain' }))
    a.download = `feedback_letter_${selectedInt}.txt`
    a.click()
  }

  if (jobStatus !== 'complete') {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-3 text-muted">
        <Users size={32} />
        <p className="text-sm">Run QC first to compute interviewer risk scores.</p>
      </div>
    )
  }

  return (
    <div className="space-y-6 animate-fade-in">
      <div>
        <h2 className="font-display font-extrabold text-base text-tx">Interviewer Risk</h2>
        <p className="text-xs text-muted mt-0.5">
          Combines all QC flags into a weighted risk score per interviewer (0–100). Higher = investigate first.
        </p>
      </div>

      {/* Config row */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="space-y-1 col-span-2 sm:col-span-1">
          <p className="text-xs text-muted">Interviewer column</p>
          <input
            type="text" className="w-full" value={intCol}
            onChange={(e) => setIntCol(e.target.value)}
            placeholder="interviewer_id"
          />
        </div>
        <div className="space-y-1">
          <p className="text-xs text-muted">Flag % alert threshold</p>
          <input type="number" className="w-full" min={1} max={100}
            value={flagThr} onChange={(e) => setFlagThr(+e.target.value)} />
        </div>
        <div className="space-y-1">
          <p className="text-xs text-muted">Red score ≥</p>
          <input type="number" className="w-full" min={2} max={100}
            value={redThr} onChange={(e) => setRedThr(+e.target.value)} />
        </div>
        <div className="space-y-1">
          <p className="text-xs text-muted">Amber score ≥</p>
          <input type="number" className="w-full" min={1} max={99}
            value={amberThr} onChange={(e) => setAmberThr(+e.target.value)} />
        </div>
      </div>

      <button
        onClick={() => riskMutation.mutate()}
        disabled={!canRun || riskMutation.isPending}
        className="btn-primary flex items-center gap-2"
      >
        <Users size={14} />
        {riskMutation.isPending ? 'Computing…' : 'Compute Risk Scores'}
      </button>

      {riskMutation.isError && (
        <p className="text-xs text-critical">{(riskMutation.error as Error).message}</p>
      )}

      {rows.length > 0 && (
        <>
          {/* Metrics */}
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
            <MetricCard label="Interviewers" value={rows.length} />
            <MetricCard label="High risk" value={high} color="text-critical" />
            <MetricCard label="Medium risk" value={medium} color="text-warning" />
            <MetricCard label="Low risk" value={low} color="text-accent" />
            <MetricCard label={`Above ${flagThr}% flag rate`} value={aboveFlagThr} />
          </div>

          {/* Table */}
          <div className="card border-line">
            <div className="flex items-center justify-between px-4 py-3 border-b border-line">
              <h3 className="text-sm font-medium text-tx">Interviewer Risk Rankings</h3>
              <button onClick={downloadCSV} className="btn-ghost flex items-center gap-1.5 text-xs">
                <Download size={12} /> Export CSV
              </button>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-line">
                    <th className="text-left py-2 px-3 text-muted font-normal">#</th>
                    {[intColName, 'risk_score', 'risk_level', 'total_interviews', 'total_flags',
                      'flag_rate_pct', 'fabrication_flags', 'duration_flags', 'straightlining_flags',
                      'productivity_flags', 'verbatim_flags'
                    ].map((c) => (
                      <th key={c} className="text-left py-2 px-3 text-muted font-normal whitespace-nowrap">
                        {c.replace(/_/g, ' ')}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row, i) => (
                    <tr key={i} className="border-b border-line/50 hover:bg-surface2 transition-colors">
                      <td className="py-2 px-3 text-muted">{i + 1}</td>
                      <td className="py-2 px-3 font-medium">{String(row[intColName] ?? '')}</td>
                      <td className="py-2 px-3">
                        <div className="flex items-center gap-1.5">
                          <div
                            className="h-1.5 rounded-full"
                            style={{
                              width: `${Math.min(row.risk_score, 100)}%`,
                              maxWidth: 60,
                              background: riskColor(row.risk_score, redThr, amberThr),
                            }}
                          />
                          <span className="text-tx">{row.risk_score}</span>
                        </div>
                      </td>
                      <td className="py-2 px-3">
                        <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${riskBadge(row.risk_level)}`}>
                          {row.risk_level}
                        </span>
                      </td>
                      <td className="py-2 px-3 text-tx">{row.total_interviews}</td>
                      <td className="py-2 px-3 text-tx">{row.total_flags}</td>
                      <td className="py-2 px-3 text-tx">{row.flag_rate_pct}%</td>
                      <td className="py-2 px-3 text-tx">{row.fabrication_flags}</td>
                      <td className="py-2 px-3 text-tx">{row.duration_flags}</td>
                      <td className="py-2 px-3 text-tx">{row.straightlining_flags}</td>
                      <td className="py-2 px-3 text-tx">{row.productivity_flags}</td>
                      <td className="py-2 px-3 text-tx">{row.verbatim_flags}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Bar chart */}
          {top20.length > 1 && (
            <div className="card p-4">
              <h3 className="text-sm font-medium text-tx mb-3">Risk Score Chart (top 20)</h3>
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={top20} margin={{ top: 5, right: 20, left: 0, bottom: 60 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1f2330" />
                  <XAxis
                    dataKey={intColName} tick={{ fill: '#8b90a8', fontSize: 10 }}
                    angle={-40} textAnchor="end" interval={0}
                  />
                  <YAxis domain={[0, 110]} tick={{ fill: '#8b90a8', fontSize: 10 }} />
                  <Tooltip {...TOOLTIP_STYLE} />
                  <Bar dataKey="risk_score" radius={[3, 3, 0, 0]}>
                    {top20.map((row, i) => (
                      <Cell key={i} fill={riskColor(row.risk_score, redThr, amberThr)} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Flag rate alerts */}
          <div className="space-y-2">
            <h3 className="text-sm font-medium text-tx">Flag Rate Alerts — threshold: {flagThr}%</h3>
            {rows.filter((r) => r.flag_rate_pct > flagThr).length === 0 ? (
              <p className="text-xs text-accent">No interviewers exceed the {flagThr}% flag rate threshold.</p>
            ) : (
              rows.filter((r) => r.flag_rate_pct > flagThr).map((row, i) => (
                <div key={i} className="flex items-start gap-2 p-3 rounded-lg bg-warning/5 border border-warning/20 text-xs">
                  <AlertTriangle size={12} className="text-warning shrink-0 mt-0.5" />
                  <span className="text-tx">
                    <span className="font-medium">{String(row[intColName])}</span>
                    : {row.flag_rate_pct}% of interviews flagged ({row.total_flags} / {row.total_interviews}) — above {flagThr}% threshold · Risk: <span className="font-medium">{row.risk_score}</span> · {row.risk_level}
                  </span>
                </div>
              ))
            )}
          </div>

          {/* Feedback letter */}
          <div className="card p-4 space-y-3">
            <h3 className="text-sm font-medium text-tx flex items-center gap-1.5">
              <Sparkles size={14} className="text-accent" />
              Interviewer Feedback Letter
            </h3>
            <p className="text-xs text-muted">
              Select an interviewer and generate a structured feedback letter via Groq AI.
              {!groqApiKey && <span className="text-warning ml-1">Set Groq API key in Settings first.</span>}
            </p>
            <div className="flex gap-2 items-end">
              <div className="flex-1 space-y-1">
                <p className="text-xs text-muted">Interviewer</p>
                <select className="w-full" value={selectedInt} onChange={(e) => setSelectedInt(e.target.value)}>
                  {rows.map((r) => (
                    <option key={String(r[intColName])} value={String(r[intColName])}>
                      {String(r[intColName])} · Risk: {r.risk_score} ({r.risk_level})
                    </option>
                  ))}
                </select>
              </div>
              <button
                onClick={() => letterMutation.mutate()}
                disabled={!groqApiKey || !selectedInt || letterMutation.isPending}
                className="btn-primary flex items-center gap-1.5 shrink-0"
              >
                <Sparkles size={12} />
                {letterMutation.isPending ? 'Writing…' : 'Generate letter'}
              </button>
            </div>
            {letterMutation.isError && (
              <p className="text-xs text-critical">{(letterMutation.error as Error).message}</p>
            )}
            {letter && (
              <div className="space-y-2">
                <textarea
                  className="w-full h-64 text-xs font-mono bg-surface2 border border-line rounded p-3 resize-y text-tx"
                  value={letter} readOnly
                />
                <button onClick={downloadLetter} className="btn-ghost flex items-center gap-1.5 text-xs">
                  <Download size={12} /> Download letter ({selectedInt})
                </button>
              </div>
            )}
          </div>

          {/* Score methodology */}
          <div className="card border-line">
            <button
              onClick={() => setShowMethods((o) => !o)}
              className="w-full flex items-center justify-between px-4 py-3 text-xs text-muted hover:text-tx"
            >
              <span>Score methodology</span>
              {showMethods ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
            </button>
            {showMethods && (
              <div className="px-4 pb-4 overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-line">
                      {['Component', 'Weight', 'Populated by'].map((h) => (
                        <th key={h} className="text-left py-1.5 px-2 text-muted font-normal">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {[
                      ['Fabrication', '40%', 'fabrication_check'],
                      ['Duration anomaly', '25%', 'interviewer_duration_check'],
                      ['Straightlining', '25%', 'straightlining_check'],
                      ['Productivity', '10%', 'interviewer_productivity_check'],
                    ].map(([comp, weight, check]) => (
                      <tr key={comp} className="border-b border-line/50">
                        <td className="py-1.5 px-2 text-tx">{comp}</td>
                        <td className="py-1.5 px-2 text-accent font-medium">{weight}</td>
                        <td className="py-1.5 px-2 text-muted font-mono">{check}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <p className="text-xs text-muted mt-2">
                  Each component contributes points proportional to that interviewer's flag rate (flags ÷ total interviews × weight). Scores are summed and capped at 100.
                </p>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  )
}
