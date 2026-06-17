import React from 'react'
import { X, User, Briefcase, Flag, TrendingUp } from 'lucide-react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell,
} from 'recharts'
import type { RiskRow } from '../../api/interviewers'

interface Props {
  row: RiskRow
  intColName: string
  redThr: number
  amberThr: number
  onClose: () => void
}

const FLAG_METRICS = [
  { key: 'fabrication_flags', label: 'Fabrication', color: '#f04a6a' },
  { key: 'duration_flags',    label: 'Duration',    color: '#f0c04a' },
  { key: 'straightlining_flags', label: 'Straightlining', color: '#a78bfa' },
  { key: 'productivity_flags',   label: 'Productivity',   color: '#60a5fa' },
  { key: 'verbatim_flags',       label: 'Verbatim',       color: '#4af0a0' },
]

function riskHex(score: number, red: number, amber: number) {
  if (score >= red) return '#f04a6a'
  if (score >= amber) return '#f0c04a'
  return '#4af0a0'
}

function riskBadgeClass(level: string) {
  if (level === 'HIGH')   return 'bg-critical/10 text-critical border border-critical/30'
  if (level === 'MEDIUM') return 'bg-warning/10 text-warning border border-warning/30'
  return 'bg-accent/10 text-accent border border-accent/30'
}

function riskNote(level: string) {
  if (level === 'HIGH')   return 'Recommend immediate review and retraining.'
  if (level === 'MEDIUM') return 'Monitor closely — follow up with supervisor.'
  return 'Performance is within acceptable range.'
}

const TOOLTIP_STYLE = {
  contentStyle: { background: '#111318', border: '1px solid #1f2330', borderRadius: 6 },
  labelStyle: { color: '#e8eaf2' },
}

export function InterviewerProfile({ row, intColName, redThr, amberThr, onClose }: Props) {
  const intId    = String(row[intColName] ?? '')
  const initials = intId.slice(0, 2).toUpperCase()
  const color    = riskHex(row.risk_score, redThr, amberThr)

  const chartData = FLAG_METRICS.map((m) => ({
    name:  m.label,
    flags: (row[m.key as keyof RiskRow] as number) ?? 0,
    color: m.color,
  }))

  const stats = [
    { label: 'Risk Score',       value: row.risk_score,         icon: TrendingUp,  color },
    { label: 'Total Interviews', value: row.total_interviews,   icon: Briefcase,   color: '#e8eaf2' },
    { label: 'Total Flags',      value: row.total_flags,        icon: Flag,        color: '#f0c04a' },
    { label: 'Flag Rate',        value: `${row.flag_rate_pct}%`, icon: Flag,       color: '#e8eaf2' },
  ]

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="bg-surface border border-line rounded-xl w-full max-w-2xl shadow-2xl animate-fade-in overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* ── Header ──────────────────────────────────────────────────── */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-line">
          <div className="flex items-center gap-3">
            <div
              className="w-11 h-11 rounded-full flex items-center justify-center text-sm font-bold shrink-0"
              style={{ background: `${color}20`, color }}
            >
              {initials}
            </div>
            <div>
              <p className="font-display font-bold text-tx text-base leading-tight">{intId}</p>
              {row.supervisor && row.supervisor !== 'None' && row.supervisor !== 'null' ? (
                <p className="text-xs text-muted flex items-center gap-1 mt-0.5">
                  <User size={10} />
                  Supervisor: <span className="text-tx ml-0.5">{String(row.supervisor)}</span>
                </p>
              ) : (
                <p className="text-xs text-muted mt-0.5">No supervisor on file</p>
              )}
            </div>
          </div>
          <div className="flex items-center gap-3">
            <span className={`text-xs px-2.5 py-1 rounded-full font-semibold ${riskBadgeClass(row.risk_level)}`}>
              {row.risk_level} RISK
            </span>
            <button onClick={onClose} className="text-muted hover:text-tx transition-colors p-1">
              <X size={18} />
            </button>
          </div>
        </div>

        {/* ── Body ────────────────────────────────────────────────────── */}
        <div className="p-6 space-y-5">
          {/* Stats row */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {stats.map((s) => (
              <div key={s.label} className="card2 px-4 py-3 text-center space-y-1">
                <p className="text-[10px] text-muted uppercase tracking-widest">{s.label}</p>
                <p className="text-xl font-display font-extrabold" style={{ color: s.color }}>
                  {s.value}
                </p>
              </div>
            ))}
          </div>

          {/* Flag breakdown chart */}
          <div className="card2 p-4">
            <p className="text-xs font-semibold text-tx mb-4">Flag Breakdown by Type</p>
            <ResponsiveContainer width="100%" height={150}>
              <BarChart data={chartData} margin={{ top: 4, right: 8, left: -24, bottom: 4 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1f2330" />
                <XAxis dataKey="name" tick={{ fill: '#8b90a8', fontSize: 11 }} />
                <YAxis tick={{ fill: '#8b90a8', fontSize: 10 }} allowDecimals={false} />
                <Tooltip
                  {...TOOLTIP_STYLE}
                  formatter={(v: number) => [v, 'Flags']}
                />
                <Bar dataKey="flags" radius={[4, 4, 0, 0]}>
                  {chartData.map((d, i) => <Cell key={i} fill={d.color} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* Summary note */}
          <div
            className="p-3 rounded-lg border text-xs text-muted leading-relaxed"
            style={{ background: `${color}08`, borderColor: `${color}30` }}
          >
            <span className="font-semibold" style={{ color }}>
              {row.risk_level} risk
            </span>
            {' '}— {row.total_flags} flags across {row.total_interviews} interviews ({row.flag_rate_pct}% flag rate).
            {' '}{riskNote(row.risk_level)}
          </div>
        </div>
      </div>
    </div>
  )
}
