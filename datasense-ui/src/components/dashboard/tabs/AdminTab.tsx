import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { UserPlus, Loader2, Trash2, UserCheck, UserX, Plus } from 'lucide-react'
import { useAppStore } from '../../../store/appStore'
import {
  getDashboardUsers, createDashboardUser, updateUserRole, toggleUserActive,
  createProjectFull, updateProject, getProjectAssignees, assignUser, removeAssignee,
  deleteUpload, getAllUploads, getDashboardSummary,
  type DashboardUser, type ProjectAssignee, type ProjectSummary, type UploadLogEntry,
} from '../../../api/dashboard'

const ROLES = ['qc_executive', 'operations_manager', 'qc_officer', 'project_manager', 'researcher', 'management', 'other']

type AdminSection = 'users' | 'projects' | 'assignments' | 'uploads'

interface Props { projectId?: number }

export function AdminTab({ projectId }: Props) {
  const { authUser, authToken } = useAppStore()
  const token = authToken ?? ''
  const qc = useQueryClient()
  const [section, setSection] = useState<AdminSection>('users')

  // ── Users ────────────────────────────────────────────────────────────────────

  const { data: users = [], isLoading: usersLoading } = useQuery({
    queryKey: ['dash-users'],
    queryFn: () => getDashboardUsers(token),
    enabled: !!token,
  })

  const [newUser, setNewUser] = useState({ email: '', password: '', full_name: '', role: 'qc_officer' })
  const createUserMut = useMutation({
    mutationFn: () => createDashboardUser(newUser.email, newUser.password, newUser.full_name, newUser.role, token),
    onSuccess: () => {
      setNewUser({ email: '', password: '', full_name: '', role: 'qc_officer' })
      qc.invalidateQueries({ queryKey: ['dash-users'] })
    },
  })

  const updateRoleMut = useMutation({
    mutationFn: ({ userId, role }: { userId: number; role: string }) => updateUserRole(userId, role, token),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['dash-users'] }),
  })

  const toggleActiveMut = useMutation({
    mutationFn: ({ userId, active }: { userId: number; active: boolean }) => toggleUserActive(userId, active, token),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['dash-users'] }),
  })

  // ── Projects ─────────────────────────────────────────────────────────────────

  const { data: summary = [] } = useQuery({
    queryKey: ['dash-summary'],
    queryFn: () => getDashboardSummary(token),
    enabled: !!token,
  })

  const [newProject, setNewProject] = useState({
    name: '', client: '', job_number: '', sample_target: 0,
    start_date: '', end_date: '',
    backcheck_target: 0.20, listenin_target: 0.10, accompaniment_target: 0.20,
  })

  const createProjMut = useMutation({
    mutationFn: () => createProjectFull({
      name: newProject.name,
      client: newProject.client || undefined,
      job_number: newProject.job_number || undefined,
      sample_target: newProject.sample_target,
      start_date: newProject.start_date || undefined,
      end_date: newProject.end_date || undefined,
      backcheck_target: newProject.backcheck_target,
      listenin_target: newProject.listenin_target,
      accompaniment_target: newProject.accompaniment_target,
    }, token),
    onSuccess: () => {
      setNewProject({ name: '', client: '', job_number: '', sample_target: 0, start_date: '', end_date: '', backcheck_target: 0.20, listenin_target: 0.10, accompaniment_target: 0.20 })
      qc.invalidateQueries({ queryKey: ['dash-summary'] })
    },
  })

  const [editingProjectId, setEditingProjectId] = useState<number | null>(null)
  const [editStatus, setEditStatus] = useState<Record<number, string>>({})

  const updateProjMut = useMutation({
    mutationFn: ({ id, status }: { id: number; status: string }) => updateProject(id, { status }, token),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['dash-summary'] }),
  })

  // ── Assignments ───────────────────────────────────────────────────────────────

  const [assignProjectId, setAssignProjectId] = useState<number | null>(projectId ?? null)
  const [addUserId, setAddUserId] = useState<number | ''>('')

  const { data: assignees = [] } = useQuery({
    queryKey: ['dash-assignees', assignProjectId],
    queryFn: () => getProjectAssignees(assignProjectId!, token),
    enabled: !!token && !!assignProjectId,
  })

  const assignMut = useMutation({
    mutationFn: () => assignUser(assignProjectId!, Number(addUserId), token),
    onSuccess: () => {
      setAddUserId('')
      qc.invalidateQueries({ queryKey: ['dash-assignees', assignProjectId] })
    },
  })

  const removeAssigneeMut = useMutation({
    mutationFn: (userId: number) => removeAssignee(assignProjectId!, userId, token),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['dash-assignees', assignProjectId] }),
  })

  // ── Upload history ────────────────────────────────────────────────────────────

  const { data: uploadLog = [] } = useQuery({
    queryKey: ['dash-all-uploads'],
    queryFn: () => getAllUploads(token),
    enabled: !!token,
  })

  const delUploadMut = useMutation({
    mutationFn: ({ uid, rt }: { uid: string; rt: string }) => deleteUpload(uid, rt, token),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['dash-all-uploads'] }),
  })

  const sections: { key: AdminSection; label: string }[] = [
    { key: 'users', label: 'Users' },
    { key: 'projects', label: 'Projects' },
    { key: 'assignments', label: 'Assignments' },
    { key: 'uploads', label: 'Upload History' },
  ]

  return (
    <div className="space-y-4">
      {/* Section tabs */}
      <div className="flex gap-2 flex-wrap">
        {sections.map(s => (
          <button
            key={s.key}
            onClick={() => setSection(s.key)}
            className={`px-3 py-1.5 rounded text-xs transition-colors ${
              section === s.key
                ? 'bg-accent/20 text-accent border border-accent/40'
                : 'text-muted hover:text-tx border border-line'
            }`}
          >
            {s.label}
          </button>
        ))}
      </div>

      {/* Users section */}
      {section === 'users' && (
        <div className="space-y-4">
          {/* Create user form */}
          <div className="card p-4 space-y-3">
            <p className="label">Create New User</p>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              {[
                { key: 'email', label: 'Email', type: 'email' },
                { key: 'password', label: 'Password', type: 'password' },
                { key: 'full_name', label: 'Full Name' },
              ].map(f => (
                <div key={f.key}>
                  <label className="label mb-1 block">{f.label}</label>
                  <input
                    type={f.type ?? 'text'}
                    value={newUser[f.key as keyof typeof newUser] as string}
                    onChange={e => setNewUser(s => ({ ...s, [f.key]: e.target.value }))}
                    className="w-full bg-surface2 border border-line rounded-lg px-3 py-2 text-sm text-tx"
                  />
                </div>
              ))}
              <div>
                <label className="label mb-1 block">Role</label>
                <select
                  value={newUser.role}
                  onChange={e => setNewUser(s => ({ ...s, role: e.target.value }))}
                  className="w-full bg-surface2 border border-line rounded-lg px-3 py-2 text-sm text-tx"
                >
                  {ROLES.map(r => <option key={r} value={r}>{r.replace(/_/g, ' ')}</option>)}
                </select>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <button
                onClick={() => createUserMut.mutate()}
                disabled={!newUser.email || !newUser.password || !newUser.full_name || createUserMut.isPending}
                className="btn-primary flex items-center gap-2"
              >
                {createUserMut.isPending ? <Loader2 size={14} className="animate-spin" /> : <UserPlus size={14} />}
                Create
              </button>
              {createUserMut.isSuccess && <span className="text-xs text-accent">User created!</span>}
              {createUserMut.isError && <span className="text-xs text-critical">{String(createUserMut.error)}</span>}
            </div>
          </div>

          {/* Users table */}
          <div className="card p-4">
            <p className="label mb-2">All Users ({users.length})</p>
            {usersLoading ? (
              <div className="flex items-center gap-2 text-muted text-sm"><Loader2 size={14} className="animate-spin" /> Loading…</div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-line text-muted">
                      {['Name', 'Email', 'Role', 'Active', 'Actions'].map(h => (
                        <th key={h} className="text-left py-1 pr-3">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {users.map((u: DashboardUser) => (
                      <tr key={u.id} className="border-b border-line/30 hover:bg-surface2/50">
                        <td className="py-1.5 pr-3 text-tx">{u.full_name}</td>
                        <td className="py-1.5 pr-3 text-muted">{u.email}</td>
                        <td className="py-1.5 pr-3">
                          <select
                            defaultValue={u.role}
                            onChange={e => updateRoleMut.mutate({ userId: u.id, role: e.target.value })}
                            className="bg-surface border border-line rounded px-2 py-0.5 text-xs text-tx"
                          >
                            {ROLES.map(r => <option key={r} value={r}>{r.replace(/_/g, ' ')}</option>)}
                          </select>
                        </td>
                        <td className="py-1.5 pr-3">
                          {u.is_active
                            ? <span className="text-accent text-xs">Active</span>
                            : <span className="text-critical text-xs">Inactive</span>}
                        </td>
                        <td className="py-1.5">
                          <button
                            onClick={() => toggleActiveMut.mutate({ userId: u.id, active: !u.is_active })}
                            className="p-1 text-muted hover:text-accent transition-colors"
                            title={u.is_active ? 'Deactivate' : 'Activate'}
                          >
                            {u.is_active ? <UserX size={13} /> : <UserCheck size={13} />}
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Projects section */}
      {section === 'projects' && (
        <div className="space-y-4">
          {/* Create project form */}
          <div className="card p-4 space-y-3">
            <p className="label">Create Project</p>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              {[
                { key: 'name', label: 'Name *' },
                { key: 'job_number', label: 'Job Number' },
                { key: 'client', label: 'Client' },
                { key: 'sample_target', label: 'Sample Target', type: 'number' },
                { key: 'start_date', label: 'Start Date', type: 'date' },
                { key: 'end_date', label: 'End Date', type: 'date' },
                { key: 'backcheck_target', label: 'BC Target %', type: 'number' },
                { key: 'listenin_target', label: 'Listen-in Target %', type: 'number' },
              ].map(f => (
                <div key={f.key}>
                  <label className="label mb-1 block">{f.label}</label>
                  <input
                    type={f.type ?? 'text'}
                    value={newProject[f.key as keyof typeof newProject]}
                    onChange={e => setNewProject(s => ({
                      ...s,
                      [f.key]: f.type === 'number' ? Number(e.target.value) : e.target.value,
                    }))}
                    step={f.type === 'number' && f.key.includes('target') && !f.key.includes('sample') ? '0.01' : undefined}
                    className="w-full bg-surface2 border border-line rounded-lg px-3 py-2 text-sm text-tx"
                  />
                </div>
              ))}
            </div>
            <div className="flex items-center gap-3">
              <button
                onClick={() => createProjMut.mutate()}
                disabled={!newProject.name || createProjMut.isPending}
                className="btn-primary flex items-center gap-2"
              >
                {createProjMut.isPending ? <Loader2 size={14} className="animate-spin" /> : <Plus size={14} />}
                Create Project
              </button>
              {createProjMut.isSuccess && <span className="text-xs text-accent">Created!</span>}
              {createProjMut.isError && <span className="text-xs text-critical">{String(createProjMut.error)}</span>}
            </div>
          </div>

          {/* Projects table */}
          <div className="card p-4">
            <p className="label mb-2">All Projects</p>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-line text-muted">
                    {['Name', 'Client', 'Job #', 'Target', 'Status', 'Actions'].map(h => (
                      <th key={h} className="text-left py-1 pr-3">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {summary.map((p: ProjectSummary) => (
                    <tr key={p.id} className="border-b border-line/30 hover:bg-surface2/50">
                      <td className="py-1.5 pr-3 text-tx">{p.name}</td>
                      <td className="py-1.5 pr-3 text-muted">{p.client ?? '—'}</td>
                      <td className="py-1.5 pr-3 text-muted">{p.job_number ?? '—'}</td>
                      <td className="py-1.5 pr-3 text-muted">{p.sample_target}</td>
                      <td className="py-1.5 pr-3">
                        <select
                          defaultValue={p.status}
                          onChange={e => updateProjMut.mutate({ id: p.id, status: e.target.value })}
                          className="bg-surface border border-line rounded px-2 py-0.5 text-xs text-tx"
                        >
                          {['active', 'closed', 'archived'].map(s => <option key={s} value={s}>{s}</option>)}
                        </select>
                      </td>
                      <td className="py-1.5 pr-3 text-muted">
                        <button
                          onClick={() => setAssignProjectId(p.id)}
                          className="text-accent hover:underline"
                        >
                          Manage
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* Assignments section */}
      {section === 'assignments' && (
        <div className="space-y-4">
          <div className="card p-4 space-y-3">
            <p className="label">Select Project</p>
            <select
              value={assignProjectId ?? ''}
              onChange={e => setAssignProjectId(e.target.value ? Number(e.target.value) : null)}
              className="bg-surface2 border border-line rounded-lg px-3 py-2 text-sm text-tx w-64"
            >
              <option value="">— select project —</option>
              {summary.map((p: ProjectSummary) => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
          </div>

          {assignProjectId && (
            <div className="card p-4 space-y-3">
              <p className="label">Assignees for {summary.find((p: ProjectSummary) => p.id === assignProjectId)?.name}</p>

              {/* Current assignees */}
              {assignees.length === 0 ? (
                <p className="text-xs text-muted">No users assigned.</p>
              ) : (
                <table className="w-full text-xs mb-3">
                  <thead>
                    <tr className="border-b border-line text-muted">
                      {['Name', 'Email', 'Role', ''].map(h => (
                        <th key={h} className="text-left py-1 pr-3">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {assignees.map((a: ProjectAssignee) => (
                      <tr key={a.id} className="border-b border-line/30">
                        <td className="py-1.5 pr-3 text-tx">{a.full_name}</td>
                        <td className="py-1.5 pr-3 text-muted">{a.email}</td>
                        <td className="py-1.5 pr-3 text-muted">{a.role.replace(/_/g, ' ')}</td>
                        <td>
                          <button
                            onClick={() => removeAssigneeMut.mutate(a.id)}
                            className="p-1 text-muted hover:text-critical transition-colors"
                          >
                            <Trash2 size={12} />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}

              {/* Add user */}
              <div className="flex gap-3 items-end">
                <div>
                  <label className="label mb-1 block">Add User</label>
                  <select
                    value={addUserId}
                    onChange={e => setAddUserId(e.target.value ? Number(e.target.value) : '')}
                    className="bg-surface2 border border-line rounded-lg px-3 py-2 text-sm text-tx w-56"
                  >
                    <option value="">— select user —</option>
                    {users
                      .filter((u: DashboardUser) => !assignees.some((a: ProjectAssignee) => a.id === u.id))
                      .map((u: DashboardUser) => (
                        <option key={u.id} value={u.id}>{u.full_name} ({u.role})</option>
                      ))}
                  </select>
                </div>
                <button
                  onClick={() => assignMut.mutate()}
                  disabled={!addUserId || assignMut.isPending}
                  className="btn-primary flex items-center gap-2"
                >
                  {assignMut.isPending ? <Loader2 size={14} className="animate-spin" /> : <Plus size={14} />}
                  Assign
                </button>
                {assignMut.isSuccess && <span className="text-xs text-accent">Assigned!</span>}
                {assignMut.isError && <span className="text-xs text-critical">{String(assignMut.error)}</span>}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Upload history section */}
      {section === 'uploads' && (
        <div className="card p-4">
          <p className="label mb-2">All Uploads</p>
          <div className="overflow-x-auto max-h-[500px]">
            <table className="w-full text-xs">
              <thead className="sticky top-0 bg-surface">
                <tr className="border-b border-line text-muted">
                  {['Project', 'Type', 'File', 'Wave', 'Rows', 'By', 'Date', ''].map(h => (
                    <th key={h} className="text-left py-1 pr-3 whitespace-nowrap">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {uploadLog.map((u: UploadLogEntry) => (
                  <tr key={u.id} className="border-b border-line/30 hover:bg-surface2/50">
                    <td className="py-1.5 pr-3 text-tx">{u.project_name ?? '—'}</td>
                    <td className="py-1.5 pr-3 text-muted">{u.report_type}</td>
                    <td className="py-1.5 pr-3 text-muted">{u.filename}</td>
                    <td className="py-1.5 pr-3 text-muted">{u.wave_label ?? '—'}</td>
                    <td className="py-1.5 pr-3 text-muted">{u.row_count}</td>
                    <td className="py-1.5 pr-3 text-muted">{u.uploader_name ?? '—'}</td>
                    <td className="py-1.5 pr-3 text-muted">{u.upload_date?.slice(0, 10)}</td>
                    <td>
                      <button
                        onClick={() => delUploadMut.mutate({ uid: u.upload_id, rt: u.report_type })}
                        className="p-1 text-muted hover:text-critical transition-colors"
                      >
                        <Trash2 size={12} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
