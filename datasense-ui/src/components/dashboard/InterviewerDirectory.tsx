import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, ResponsiveContainer,
} from 'recharts'
import { Users, Plus, Trash2, ChevronRight, X, Loader2, Edit2 } from 'lucide-react'
import { useAppStore } from '../../store/appStore'
import {
  getSupervisors, getInterviewers, getInterviewerMetrics, createSupervisor,
  deleteSupervisor, upsertInterviewer,
  type Supervisor, type Interviewer, type InterviewerMetrics,
} from '../../api/dashboard'

const C = {
  accent: '#4af0a0', critical: '#f04a6a', warning: '#f0c04a',
  muted: '#8b90a8', surface: '#111318', surface2: '#181b22', line: '#1f2330', tx: '#e8eaf2',
}

const TooltipStyle = {
  contentStyle: { backgroundColor: C.surface2, border: `1px solid ${C.line}`, borderRadius: 6, color: C.tx },
  itemStyle: { color: C.tx },
  labelStyle: { color: C.muted },
}

const ADMIN_ROLES = new Set(['qc_executive', 'operations_manager'])

// ── Interviewer detail modal ───────────────────────────────────────────────────

function InterviewerDetailModal({ code, onClose }: { code: string; onClose: () => void }) {
  const { authToken } = useAppStore()
  const token = authToken ?? ''

  const { data, isLoading } = useQuery({
    queryKey: ['itv-metrics', code],
    queryFn: () => getInterviewerMetrics(code, token),
    enabled: !!token,
  })

  const m = data as InterviewerMetrics | undefined

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm"
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
    >
      <div className="bg-surface border border-line rounded-xl w-full max-w-3xl max-h-[85vh] flex flex-col shadow-2xl">
        <div className="flex items-center justify-between px-5 py-4 border-b border-line shrink-0">
          <div className="flex items-center gap-2">
            <Users size={15} className="text-accent" />
            <span className="font-display font-bold text-sm text-tx">{code}</span>
            {m?.info?.name && <span className="text-muted text-xs">— {m.info.name}</span>}
          </div>
          <button onClick={onClose} className="p-1.5 text-muted hover:text-tx hover:bg-surface2 rounded transition-colors">
            <X size={15} />
          </button>
        </div>

        <div className="overflow-y-auto p-5 space-y-5">
          {isLoading && (
            <div className="flex items-center gap-2 text-muted text-sm">
              <Loader2 size={14} className="animate-spin" /> Loading metrics…
            </div>
          )}

          {m && (
            <>
              {/* Supervisor */}
              <div className="card p-3 text-sm">
                <span className="text-muted">Supervisor: </span>
                <span className="text-tx">{m.info?.supervisor_name ?? <span className="text-muted italic">Unassigned</span>}</span>
                {m.info?.region && <span className="text-muted ml-3">Region: <span className="text-tx">{m.info.region}</span></span>}
              </div>

              {/* KPIs */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                {[
                  { label: 'Total Interviews', value: m.quality.total_interviews ?? 0, color: 'text-tx' },
                  { label: 'Approved', value: m.quality.approved ?? 0, color: 'text-accent' },
                  { label: 'Duration Flags', value: m.quality.duration_flags ?? 0, color: 'text-critical' },
                  { label: 'SL Flags', value: m.quality.sl_flags ?? 0, color: 'text-warning' },
                  { label: 'BC Sessions', value: m.backcheck.bc_count ?? 0, color: 'text-info' },
                  { label: 'BC Errors', value: m.backcheck.total_errors ?? 0, color: 'text-critical' },
                  { label: 'Listen-ins', value: m.listen_in.li_count ?? 0, color: 'text-tx' },
                  { label: 'LI Pass', value: m.listen_in.li_pass ?? 0, color: 'text-accent' },
                ].map(k => (
                  <div key={k.label} className="card p-3">
                    <p className="label mb-0.5">{k.label}</p>
                    <p className={`text-xl font-bold font-display ${k.color}`}>{k.value}</p>
                  </div>
                ))}
              </div>

              {/* Per-project chart */}
              {m.by_project.length > 0 && (
                <div className="card p-4">
                  <p className="label mb-3">Performance by Project</p>
                  <ResponsiveContainer width="100%" height={200}>
                    <BarChart data={m.by_project} margin={{ left: -20 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke={C.line} />
                      <XAxis dataKey="project_name" tick={{ fill: C.muted, fontSize: 10 }} />
                      <YAxis tick={{ fill: C.muted, fontSize: 10 }} />
                      <Tooltip {...TooltipStyle} />
                      <Bar dataKey="interviews" name="Interviews" fill={C.accent} radius={[2, 2, 0, 0]} />
                      <Bar dataKey="dur_flags" name="Dur Flags" fill={C.critical} radius={[2, 2, 0, 0]} />
                      <Bar dataKey="sl_flags" name="SL Flags" fill={C.warning} radius={[2, 2, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>

                  <table className="w-full text-xs mt-3">
                    <thead>
                      <tr className="border-b border-line text-muted">
                        {['Project', 'Interviews', 'Dur Flags', 'SL Flags', 'Approved'].map(h => (
                          <th key={h} className="text-left py-1 pr-3">{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {m.by_project.map(p => (
                        <tr key={p.project_id} className="border-b border-line/30">
                          <td className="py-1 pr-3 text-tx">{p.project_name}</td>
                          <td className="py-1 pr-3 text-muted">{p.interviews}</td>
                          <td className="py-1 pr-3 text-critical">{p.dur_flags}</td>
                          <td className="py-1 pr-3 text-warning">{p.sl_flags}</td>
                          <td className="py-1 pr-3 text-accent">{p.approved}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {m.by_project.length === 0 && (
                <div className="card p-6 text-center text-muted text-sm">
                  No quality records found for this interviewer across any project.
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}

// ── Add interviewer form ───────────────────────────────────────────────────────

function AddInterviewerForm({
  supervisors, onClose,
}: { supervisors: Supervisor[]; onClose: () => void }) {
  const { authToken } = useAppStore()
  const token = authToken ?? ''
  const qc = useQueryClient()

  const [form, setForm] = useState({ interviewer_code: '', name: '', supervisor_id: '', region: '' })

  const mut = useMutation({
    mutationFn: () => upsertInterviewer({
      interviewer_code: form.interviewer_code.trim().toUpperCase(),
      name: form.name.trim() || undefined,
      supervisor_id: form.supervisor_id ? Number(form.supervisor_id) : null,
      region: form.region.trim() || undefined,
    }, token),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['dash-interviewers'] })
      onClose()
    },
  })

  return (
    <div className="card p-4 space-y-3">
      <p className="label">Add / Update Interviewer</p>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="label mb-1 block">Interviewer Code *</label>
          <input
            value={form.interviewer_code}
            onChange={e => setForm(f => ({ ...f, interviewer_code: e.target.value }))}
            placeholder="e.g. NB0664"
            className="w-full bg-surface2 border border-line rounded-lg px-3 py-2 text-sm text-tx placeholder:text-muted"
          />
        </div>
        <div>
          <label className="label mb-1 block">Full Name</label>
          <input
            value={form.name}
            onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
            placeholder="Optional"
            className="w-full bg-surface2 border border-line rounded-lg px-3 py-2 text-sm text-tx placeholder:text-muted"
          />
        </div>
        <div>
          <label className="label mb-1 block">Supervisor</label>
          <select
            value={form.supervisor_id}
            onChange={e => setForm(f => ({ ...f, supervisor_id: e.target.value }))}
            className="w-full bg-surface2 border border-line rounded-lg px-3 py-2 text-sm text-tx"
          >
            <option value="">— None —</option>
            {supervisors.map(s => (
              <option key={s.id} value={s.id}>{s.name}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="label mb-1 block">Region</label>
          <input
            value={form.region}
            onChange={e => setForm(f => ({ ...f, region: e.target.value }))}
            placeholder="Optional"
            className="w-full bg-surface2 border border-line rounded-lg px-3 py-2 text-sm text-tx placeholder:text-muted"
          />
        </div>
      </div>
      <div className="flex items-center gap-3">
        <button
          onClick={() => mut.mutate()}
          disabled={!form.interviewer_code.trim() || mut.isPending}
          className="btn-primary flex items-center gap-2"
        >
          {mut.isPending ? <Loader2 size={13} className="animate-spin" /> : <Plus size={13} />}
          Save
        </button>
        <button onClick={onClose} className="btn-ghost text-sm">Cancel</button>
        {mut.isError && <span className="text-xs text-critical">{String(mut.error)}</span>}
      </div>
    </div>
  )
}

// ── Add supervisor form ────────────────────────────────────────────────────────

function AddSupervisorForm({ onClose }: { onClose: () => void }) {
  const { authToken } = useAppStore()
  const token = authToken ?? ''
  const qc = useQueryClient()

  const [form, setForm] = useState({ name: '', email: '', phone: '', region: '' })

  const mut = useMutation({
    mutationFn: () => createSupervisor({ name: form.name.trim(), email: form.email.trim() || null, phone: form.phone.trim() || null, region: form.region.trim() || null }, token),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['dash-supervisors'] })
      onClose()
    },
  })

  return (
    <div className="card p-4 space-y-3">
      <p className="label">Add Supervisor</p>
      <div className="grid grid-cols-2 gap-3">
        {[
          { key: 'name', label: 'Full Name *', placeholder: 'Jane Supervisor' },
          { key: 'email', label: 'Email', placeholder: 'jane@servalab.com' },
          { key: 'phone', label: 'Phone', placeholder: '+254 7xx xxx xxx' },
          { key: 'region', label: 'Region', placeholder: 'Nairobi' },
        ].map(f => (
          <div key={f.key}>
            <label className="label mb-1 block">{f.label}</label>
            <input
              value={(form as any)[f.key]}
              onChange={e => setForm(prev => ({ ...prev, [f.key]: e.target.value }))}
              placeholder={f.placeholder}
              className="w-full bg-surface2 border border-line rounded-lg px-3 py-2 text-sm text-tx placeholder:text-muted"
            />
          </div>
        ))}
      </div>
      <div className="flex items-center gap-3">
        <button
          onClick={() => mut.mutate()}
          disabled={!form.name.trim() || mut.isPending}
          className="btn-primary flex items-center gap-2"
        >
          {mut.isPending ? <Loader2 size={13} className="animate-spin" /> : <Plus size={13} />}
          Add Supervisor
        </button>
        <button onClick={onClose} className="btn-ghost text-sm">Cancel</button>
      </div>
    </div>
  )
}

// ── Main component ─────────────────────────────────────────────────────────────

export function InterviewerDirectory() {
  const { authUser, authToken } = useAppStore()
  const token = authToken ?? ''
  const qc = useQueryClient()

  const [selectedCode, setSelectedCode] = useState<string | null>(null)
  const [filterSupervisor, setFilterSupervisor] = useState<string>('')
  const [filterRegion, setFilterRegion] = useState<string>('')
  const [showAddItv, setShowAddItv] = useState(false)
  const [showAddSup, setShowAddSup] = useState(false)

  const isAdmin = authUser && ADMIN_ROLES.has(authUser.role)

  const { data: supervisors = [] } = useQuery({
    queryKey: ['dash-supervisors'],
    queryFn: () => getSupervisors(token),
    enabled: !!token,
  })

  const { data: interviewers = [], isLoading } = useQuery({
    queryKey: ['dash-interviewers'],
    queryFn: () => getInterviewers(token),
    enabled: !!token,
  })

  const delSupMut = useMutation({
    mutationFn: (id: number) => deleteSupervisor(id, token),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['dash-supervisors'] }),
  })

  const filtered = (interviewers as Interviewer[]).filter(itv => {
    if (filterSupervisor && String(itv.supervisor_id ?? '') !== filterSupervisor) return false
    if (filterRegion && (itv.region ?? '').toLowerCase() !== filterRegion.toLowerCase()) return false
    return true
  })

  const regions = [...new Set((interviewers as Interviewer[]).map(i => i.region).filter(Boolean))] as string[]

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-display font-bold text-tx">Interviewer Registry</h2>
          <p className="text-xs text-muted mt-0.5">{(interviewers as Interviewer[]).length} interviewers · {(supervisors as Supervisor[]).length} supervisors</p>
        </div>
        {isAdmin && (
          <div className="flex gap-2">
            <button
              onClick={() => { setShowAddSup(s => !s); setShowAddItv(false) }}
              className="btn-ghost flex items-center gap-1.5 text-xs"
            >
              <Plus size={12} /> Supervisor
            </button>
            <button
              onClick={() => { setShowAddItv(s => !s); setShowAddSup(false) }}
              className="btn-primary flex items-center gap-1.5 text-xs"
            >
              <Plus size={12} /> Interviewer
            </button>
          </div>
        )}
      </div>

      {showAddSup && isAdmin && <AddSupervisorForm onClose={() => setShowAddSup(false)} />}
      {showAddItv && isAdmin && <AddInterviewerForm supervisors={supervisors as Supervisor[]} onClose={() => setShowAddItv(false)} />}

      {/* Supervisors panel */}
      {(supervisors as Supervisor[]).length > 0 && (
        <div className="card p-4">
          <p className="label mb-3">Supervisors</p>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2">
            {(supervisors as Supervisor[]).map(s => {
              const count = (interviewers as Interviewer[]).filter(i => i.supervisor_id === s.id).length
              return (
                <div
                  key={s.id}
                  className="bg-surface2 border border-line rounded-lg p-3 flex items-start justify-between gap-2"
                >
                  <div>
                    <p className="text-sm text-tx font-medium">{s.name}</p>
                    {s.region && <p className="text-xs text-muted">{s.region}</p>}
                    <p className="text-xs text-accent mt-0.5">{count} interviewer{count !== 1 ? 's' : ''}</p>
                  </div>
                  {isAdmin && (
                    <button
                      onClick={() => delSupMut.mutate(s.id)}
                      className="p-1 text-muted hover:text-critical transition-colors shrink-0"
                      title="Delete supervisor"
                    >
                      <Trash2 size={12} />
                    </button>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Filter bar */}
      <div className="flex flex-wrap gap-3">
        <select
          value={filterSupervisor}
          onChange={e => setFilterSupervisor(e.target.value)}
          className="bg-surface2 border border-line rounded-lg px-3 py-1.5 text-sm text-tx"
        >
          <option value="">All supervisors</option>
          {(supervisors as Supervisor[]).map(s => (
            <option key={s.id} value={String(s.id)}>{s.name}</option>
          ))}
        </select>
        <select
          value={filterRegion}
          onChange={e => setFilterRegion(e.target.value)}
          className="bg-surface2 border border-line rounded-lg px-3 py-1.5 text-sm text-tx"
        >
          <option value="">All regions</option>
          {regions.map(r => <option key={r} value={r}>{r}</option>)}
        </select>
        {(filterSupervisor || filterRegion) && (
          <button onClick={() => { setFilterSupervisor(''); setFilterRegion('') }} className="text-xs text-muted hover:text-tx">
            Clear filters
          </button>
        )}
      </div>

      {/* Interviewer table */}
      {isLoading ? (
        <div className="flex items-center gap-2 text-muted text-sm">
          <Loader2 size={14} className="animate-spin" /> Loading…
        </div>
      ) : filtered.length === 0 ? (
        <div className="card p-8 text-center text-muted text-sm">
          {(interviewers as Interviewer[]).length === 0
            ? 'No interviewers registered yet. Add one above, or they will be auto-detected when QC data is saved.'
            : 'No interviewers match the current filters.'}
        </div>
      ) : (
        <div className="card overflow-hidden">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-line text-muted bg-surface">
                {['Code', 'Name', 'Supervisor', 'Region', 'Status', ''].map(h => (
                  <th key={h} className="text-left px-4 py-2.5 whitespace-nowrap">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.map((itv: Interviewer) => (
                <tr
                  key={itv.id}
                  className="border-b border-line/30 hover:bg-surface2/60 cursor-pointer"
                  onClick={() => setSelectedCode(itv.interviewer_code)}
                >
                  <td className="px-4 py-2.5 font-mono text-accent">{itv.interviewer_code}</td>
                  <td className="px-4 py-2.5 text-tx">{itv.name ?? <span className="text-muted italic">—</span>}</td>
                  <td className="px-4 py-2.5 text-muted">{itv.supervisor_name ?? <span className="italic">Unassigned</span>}</td>
                  <td className="px-4 py-2.5 text-muted">{itv.region ?? '—'}</td>
                  <td className="px-4 py-2.5">
                    <span className={`text-xs ${itv.is_active ? 'text-accent' : 'text-muted line-through'}`}>
                      {itv.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </td>
                  <td className="px-4 py-2.5">
                    <ChevronRight size={12} className="text-muted" />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {selectedCode && (
        <InterviewerDetailModal code={selectedCode} onClose={() => setSelectedCode(null)} />
      )}
    </div>
  )
}
