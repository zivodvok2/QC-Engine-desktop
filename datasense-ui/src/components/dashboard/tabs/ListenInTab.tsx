import React, { useRef, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  PieChart, Pie, Cell, Tooltip, Legend,
  BarChart, Bar, XAxis, YAxis, CartesianGrid, ResponsiveContainer,
} from 'recharts'
import { Upload, Loader2, Plus, Trash2, Download } from 'lucide-react'
import { useAppStore } from '../../../store/appStore'
import {
  getListenInRecords, uploadListenIn, addManualListenIn, deleteListenIn, downloadTemplate,
  type ListenInRecord,
} from '../../../api/dashboard'

const C = {
  accent: '#4af0a0', critical: '#f04a6a', warning: '#f0c04a', info: '#4a9ef0',
  purple: '#a078f0', muted: '#8b90a8', surface: '#111318', surface2: '#181b22',
  line: '#1f2330', tx: '#e8eaf2',
}
const PALETTE = ['#4af0a0', '#f0c04a', '#f04a6a', '#4a9ef0', '#a078f0']
const UPLOAD_ROLES = new Set(['qc_executive', 'operations_manager', 'qc_officer'])

const TooltipStyle = {
  contentStyle: { backgroundColor: C.surface2, border: `1px solid ${C.line}`, borderRadius: 6, color: C.tx },
  itemStyle: { color: C.tx },
  labelStyle: { color: C.muted },
}

interface Props { projectId: number; target?: number }

export function ListenInTab({ projectId, target = 0.10 }: Props) {
  const { authUser, authToken } = useAppStore()
  const token = authToken ?? ''
  const qc = useQueryClient()

  const fileRef = useRef<HTMLInputElement>(null)
  const [waveLabel, setWaveLabel] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [activeInput, setActiveInput] = useState<'manual' | 'batch'>('manual')

  // Manual form state
  const [form, setForm] = useState({
    interviewer_id: '',
    instance_id: '',
    region: '',
    listen_date: '',
    listen_type: 'Telephone',
    result: 'Pass',
    issues_noted: '',
    action_taken: '',
  })

  const { data: records = [], isLoading } = useQuery({
    queryKey: ['dash-listenin', projectId],
    queryFn: () => getListenInRecords(projectId, token),
    enabled: !!token,
  })

  const manualMut = useMutation({
    mutationFn: () => addManualListenIn(projectId, {
      interviewer_id: form.interviewer_id,
      instance_id: form.instance_id || undefined,
      region: form.region || undefined,
      listen_date: form.listen_date,
      listen_type: form.listen_type,
      result: form.result,
      issues_noted: form.issues_noted || undefined,
      action_taken: form.action_taken || undefined,
    }, token),
    onSuccess: () => {
      setForm({ interviewer_id: '', instance_id: '', region: '', listen_date: '', listen_type: 'Telephone', result: 'Pass', issues_noted: '', action_taken: '' })
      qc.invalidateQueries({ queryKey: ['dash-listenin', projectId] })
      qc.invalidateQueries({ queryKey: ['dash-summary'] })
    },
  })

  const batchMut = useMutation({
    mutationFn: () => {
      if (!file) throw new Error('No file selected')
      return uploadListenIn(projectId, file, token, waveLabel || undefined)
    },
    onSuccess: () => {
      setFile(null)
      setWaveLabel('')
      qc.invalidateQueries({ queryKey: ['dash-listenin', projectId] })
      qc.invalidateQueries({ queryKey: ['dash-summary'] })
    },
  })

  const delMut = useMutation({
    mutationFn: (id: number) => deleteListenIn(projectId, id, token),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['dash-listenin', projectId] })
      qc.invalidateQueries({ queryKey: ['dash-summary'] })
    },
  })

  const canUpload = authUser && UPLOAD_ROLES.has(authUser.role)

  // KPIs
  const total = records.length
  const passed = records.filter((r: ListenInRecord) => r.result === 'Pass').length
  const failed = records.filter((r: ListenInRecord) => r.result === 'Fail').length
  const partial = records.filter((r: ListenInRecord) => r.result === 'Partial').length
  const passRate = total > 0 ? Math.round(passed / total * 100) : 0

  // Pie data
  const pieData = [
    { name: 'Pass', value: passed },
    { name: 'Fail', value: failed },
    { name: 'Partial', value: partial },
  ].filter(d => d.value > 0)
  const pieColors = [C.accent, C.critical, C.warning]

  // Sessions by interviewer
  const byItv: Record<string, number> = {}
  records.forEach((r: ListenInRecord) => {
    const id = r.interviewer_id ?? 'Unknown'
    byItv[id] = (byItv[id] ?? 0) + 1
  })
  const itvData = Object.entries(byItv)
    .map(([name, count]) => ({ name, count }))
    .sort((a, b) => b.count - a.count)
    .slice(0, 15)

  return (
    <div className="space-y-6">
      {canUpload && (
        <div className="card p-4 space-y-4">
          {/* Tab switcher */}
          <div className="flex gap-2">
            {(['manual', 'batch'] as const).map(t => (
              <button
                key={t}
                onClick={() => setActiveInput(t)}
                className={`px-3 py-1.5 rounded text-xs transition-colors capitalize ${
                  activeInput === t
                    ? 'bg-accent/20 text-accent border border-accent/40'
                    : 'text-muted hover:text-tx'
                }`}
              >
                {t === 'manual' ? 'Manual Entry' : 'Batch Upload'}
              </button>
            ))}
          </div>

          {activeInput === 'manual' ? (
            <div className="space-y-3">
              <p className="label">Add Listen-in Session</p>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                {[
                  { key: 'interviewer_id', label: 'Interviewer ID', required: true },
                  { key: 'instance_id', label: 'Instance ID' },
                  { key: 'region', label: 'Region' },
                  { key: 'listen_date', label: 'Listen Date', type: 'date', required: true },
                ].map(f => (
                  <div key={f.key}>
                    <label className="label mb-1 block">{f.label}{f.required && ' *'}</label>
                    <input
                      type={f.type ?? 'text'}
                      value={form[f.key as keyof typeof form]}
                      onChange={e => setForm(s => ({ ...s, [f.key]: e.target.value }))}
                      className="w-full bg-surface2 border border-line rounded-lg px-3 py-2 text-sm text-tx placeholder:text-muted focus:outline-none focus:border-accent"
                    />
                  </div>
                ))}
                <div>
                  <label className="label mb-1 block">Listen Type</label>
                  <select
                    value={form.listen_type}
                    onChange={e => setForm(s => ({ ...s, listen_type: e.target.value }))}
                    className="w-full bg-surface2 border border-line rounded-lg px-3 py-2 text-sm text-tx"
                  >
                    {['Telephone', 'F2F', 'Audio Playback'].map(o => <option key={o}>{o}</option>)}
                  </select>
                </div>
                <div>
                  <label className="label mb-1 block">Result</label>
                  <select
                    value={form.result}
                    onChange={e => setForm(s => ({ ...s, result: e.target.value }))}
                    className="w-full bg-surface2 border border-line rounded-lg px-3 py-2 text-sm text-tx"
                  >
                    {['Pass', 'Fail', 'Partial'].map(o => <option key={o}>{o}</option>)}
                  </select>
                </div>
                <div>
                  <label className="label mb-1 block">Issues Noted</label>
                  <input
                    value={form.issues_noted}
                    onChange={e => setForm(s => ({ ...s, issues_noted: e.target.value }))}
                    className="w-full bg-surface2 border border-line rounded-lg px-3 py-2 text-sm text-tx"
                  />
                </div>
                <div>
                  <label className="label mb-1 block">Action Taken</label>
                  <input
                    value={form.action_taken}
                    onChange={e => setForm(s => ({ ...s, action_taken: e.target.value }))}
                    className="w-full bg-surface2 border border-line rounded-lg px-3 py-2 text-sm text-tx"
                  />
                </div>
              </div>
              <div className="flex items-center gap-3">
                <button
                  onClick={() => manualMut.mutate()}
                  disabled={!form.interviewer_id || !form.listen_date || manualMut.isPending}
                  className="btn-primary flex items-center gap-2"
                >
                  {manualMut.isPending ? <Loader2 size={14} className="animate-spin" /> : <Plus size={14} />}
                  Add Session
                </button>
                {manualMut.isSuccess && <span className="text-xs text-accent">Added!</span>}
                {manualMut.isError && <span className="text-xs text-critical">{String(manualMut.error)}</span>}
              </div>
            </div>
          ) : (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <p className="label">Batch Upload (Excel)</p>
                <button
                  onClick={() => downloadTemplate('listen_in', token)}
                  className="btn-ghost flex items-center gap-1.5 text-xs"
                  title="Download the Excel template with correct column headers"
                >
                  <Download size={12} /> Download template
                </button>
              </div>
              <div className="flex flex-wrap gap-3 items-end">
                <div>
                  <label className="label mb-1 block">File</label>
                  <input
                    ref={fileRef}
                    type="file"
                    accept=".xlsx,.xls"
                    onChange={e => setFile(e.target.files?.[0] ?? null)}
                    className="text-sm text-muted"
                  />
                </div>
                <div>
                  <label className="label mb-1 block">Wave Label</label>
                  <input
                    value={waveLabel}
                    onChange={e => setWaveLabel(e.target.value)}
                    placeholder="e.g. Wave 1"
                    className="bg-surface2 border border-line rounded-lg px-3 py-2 text-sm text-tx w-36"
                  />
                </div>
                <button
                  onClick={() => batchMut.mutate()}
                  disabled={!file || batchMut.isPending}
                  className="btn-primary flex items-center gap-2"
                >
                  {batchMut.isPending ? <Loader2 size={14} className="animate-spin" /> : <Upload size={14} />}
                  Upload
                </button>
                {batchMut.isSuccess && <span className="text-xs text-accent">Uploaded!</span>}
                {batchMut.isError && <span className="text-xs text-critical">{String(batchMut.error)}</span>}
              </div>
            </div>
          )}
        </div>
      )}

      {isLoading && (
        <div className="flex items-center gap-2 text-muted text-sm">
          <Loader2 size={14} className="animate-spin" /> Loading…
        </div>
      )}

      {!isLoading && records.length === 0 && (
        <div className="card p-8 text-center text-muted text-sm">
          No listen-in sessions yet. Add sessions manually or upload a batch file.
        </div>
      )}

      {records.length > 0 && (
        <>
          {/* KPIs */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className="card p-4">
              <p className="label mb-1">Total Sessions</p>
              <p className="text-2xl font-bold font-display text-accent">{total}</p>
            </div>
            <div className="card p-4">
              <p className="label mb-1">Pass Rate</p>
              <p className="text-2xl font-bold font-display text-accent">{passRate}%</p>
            </div>
            <div className="card p-4">
              <p className="label mb-1">Target</p>
              <p className="text-2xl font-bold font-display text-muted">{Math.round(target * 100)}%</p>
            </div>
            <div className="card p-4">
              <p className="label mb-1">Failed</p>
              <p className="text-2xl font-bold font-display text-critical">{failed}</p>
            </div>
          </div>

          {/* Charts */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {/* Pie */}
            <div className="card p-4">
              <p className="label mb-3">Result Breakdown</p>
              <ResponsiveContainer width="100%" height={220}>
                <PieChart>
                  <Pie data={pieData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={80} label>
                    {pieData.map((_, i) => <Cell key={i} fill={pieColors[i % pieColors.length]} />)}
                  </Pie>
                  <Tooltip {...TooltipStyle} />
                  <Legend wrapperStyle={{ color: C.muted, fontSize: 11 }} />
                </PieChart>
              </ResponsiveContainer>
            </div>

            {/* Sessions by interviewer */}
            {itvData.length > 0 && (
              <div className="card p-4">
                <p className="label mb-3">Sessions by Interviewer</p>
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart data={itvData} margin={{ left: -20 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke={C.line} />
                    <XAxis dataKey="name" tick={{ fill: C.muted, fontSize: 10 }} />
                    <YAxis tick={{ fill: C.muted, fontSize: 10 }} />
                    <Tooltip {...TooltipStyle} />
                    <Bar dataKey="count" fill={C.info} radius={[2, 2, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>

          {/* Sessions table */}
          <div className="card p-4">
            <p className="label mb-2">Sessions</p>
            <div className="overflow-x-auto max-h-80">
              <table className="w-full text-xs">
                <thead className="sticky top-0 bg-surface">
                  <tr className="border-b border-line text-muted">
                    {['Interviewer', 'Date', 'Type', 'Result', 'Region', 'Issues', 'Action', ''].map(h => (
                      <th key={h} className="text-left py-1 pr-3 whitespace-nowrap">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {records.map((r: ListenInRecord) => (
                    <tr key={r.id} className="border-b border-line/30 hover:bg-surface2/50">
                      <td className="py-1 pr-3 text-tx">{r.interviewer_id ?? '—'}</td>
                      <td className="py-1 pr-3 text-muted">{r.listen_date ?? '—'}</td>
                      <td className="py-1 pr-3 text-muted">{r.listen_type ?? '—'}</td>
                      <td className="py-1 pr-3">
                        {r.result === 'Pass'
                          ? <span className="text-accent">Pass</span>
                          : r.result === 'Fail'
                          ? <span className="text-critical">Fail</span>
                          : <span className="text-warning">{r.result}</span>}
                      </td>
                      <td className="py-1 pr-3 text-muted">{r.region ?? '—'}</td>
                      <td className="py-1 pr-3 text-muted max-w-[120px] truncate">{r.issues_noted ?? '—'}</td>
                      <td className="py-1 pr-3 text-muted max-w-[120px] truncate">{r.action_taken ?? '—'}</td>
                      <td className="py-1">
                        {canUpload && (
                          <button
                            onClick={() => delMut.mutate(r.id)}
                            className="p-1 text-muted hover:text-critical transition-colors"
                          >
                            <Trash2 size={12} />
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
