import { client } from './client'

function authHeader(token: string) {
  return { Authorization: `Bearer ${token}` }
}

// ── Types ──────────────────────────────────────────────────────────────────────

export interface ProjectSummary {
  id: number
  name: string
  client: string | null
  job_number: string | null
  status: string
  sample_target: number
  approved: number
  completion_pct: number
  backcheck_rate: number
  listenin_rate: number
  flagged: number
  total_submitted: number
  backcheck_count: number
  backcheck_target: number
  listenin_target: number
  flag_warning_pct: number
  flag_critical_pct: number
  end_date: string | null
  start_date: string | null
  loi_min_minutes: number | null
}

export interface QualityRecord {
  id: number
  instance_id: string | null
  interviewer_id: string | null
  interview_date: string | null
  start_time: string | null
  end_time: string | null
  duration_minutes: number | null
  duration_flag: string | null
  straight_lining: string | null
  long_pause: string | null
  gps_status: string | null
  region: string | null
  location: string | null
  sample_point_id: string | null
  approval_status: string | null
  qc_comments: string | null
  extra_data: string | null
}

export interface BackcheckRecord {
  id: number
  bc_instance_id: string | null
  original_instance_id: string | null
  interview_status: string | null
  region: string | null
  interviewer_id: string | null
  backchecker_id: string | null
  interview_date: string | null
  backcheck_date: string | null
  error_01: number
  error_02: number
  error_03: number
  error_04: number
  error_05: number
  error_06: number
  error_07: number
  error_08: number
  error_09: number
  error_10: number
  error_11: number
  error_12: number
  error_13: number
}

export interface ListenInRecord {
  id: number
  instance_id: string | null
  interviewer_id: string | null
  region: string | null
  listen_date: string | null
  listen_type: string | null
  result: string | null
  issues_noted: string | null
  action_taken: string | null
}

export interface UploadLogEntry {
  id: number
  upload_id: string
  report_type: string
  filename: string | null
  row_count: number
  upload_date: string
  uploader_name: string | null
  wave_label: string | null
  project_name?: string | null
  is_locked: number
}

export interface ActivityEntry {
  upload_date: string
  report_type: string
  filename: string | null
  row_count: number
  wave_label: string | null
  project_name: string | null
  uploader: string | null
}

export interface DashboardUser {
  id: number
  email: string
  full_name: string
  role: string
  is_active: number
  created_at: string
}

export interface ProjectAssignee {
  id: number
  email: string
  full_name: string
  role: string
}

export interface Supervisor {
  id: number
  name: string
  email: string | null
  phone: string | null
  region: string | null
  created_at: string
}

export interface Interviewer {
  id: number
  interviewer_code: string
  name: string | null
  supervisor_id: number | null
  supervisor_name: string | null
  region: string | null
  is_active: number
  created_at: string
}

export interface InterviewerMetrics {
  info: Interviewer | null
  quality: {
    total_interviews: number
    duration_flags: number
    sl_flags: number
    approved: number
    cancelled: number
    avg_duration: number | null
  }
  backcheck: { bc_count: number; total_errors: number }
  listen_in: { li_count: number; li_pass: number; li_fail: number }
  by_project: { project_name: string; project_id: number; interviews: number; dur_flags: number; sl_flags: number; approved: number }[]
}

export interface ItvAnalyticsRow {
  code: string
  name: string | null
  supervisor_name: string | null
  supervisor_id: number | null
  region: string | null
  is_active: number
  total_interviews: number
  duration_flags: number
  sl_flags: number
  approved: number
  cancelled: number
  avg_duration: number
  bc_count: number
  bc_errors: number
  li_count: number
  li_pass: number
  li_fail: number
  flag_rate: number
}

export interface SupAnalyticsRow {
  supervisor_name: string
  interviewer_count: number
  total_interviews: number
  total_flags: number
  flag_rate: number
  bc_errors: number
}

export interface InterviewerAnalytics {
  interviewers: ItvAnalyticsRow[]
  by_supervisor: SupAnalyticsRow[]
  projects: { id: number; name: string }[]
}

export interface ManualListenInBody {
  instance_id?: string
  interviewer_id: string
  region?: string
  listen_date: string
  listen_type: string
  result: string
  issues_noted?: string
  action_taken?: string
}

export interface CreateProjectFullBody {
  name: string
  client?: string
  job_number?: string
  sample_target?: number
  start_date?: string
  end_date?: string
  backcheck_target?: number
  listenin_target?: number
  accompaniment_target?: number
  loi_min_minutes?: number
  loi_pct_threshold?: number
  flag_warning_pct?: number
  flag_critical_pct?: number
}

// ── API calls ──────────────────────────────────────────────────────────────────

export async function getDashboardSummary(token: string): Promise<ProjectSummary[]> {
  const { data } = await client.get<ProjectSummary[]>('/api/dashboard/summary', {
    headers: authHeader(token),
  })
  return data
}

export async function getDashboardActivity(token: string, limit = 20): Promise<ActivityEntry[]> {
  const { data } = await client.get<ActivityEntry[]>('/api/dashboard/activity', {
    params: { limit },
    headers: authHeader(token),
  })
  return data
}

export async function getQualityRecords(projectId: number, token: string): Promise<QualityRecord[]> {
  const { data } = await client.get<QualityRecord[]>(`/api/dashboard/projects/${projectId}/quality-records`, {
    headers: authHeader(token),
  })
  return data
}

export async function getBackcheckRecords(projectId: number, token: string): Promise<BackcheckRecord[]> {
  const { data } = await client.get<BackcheckRecord[]>(`/api/dashboard/projects/${projectId}/backcheck-records`, {
    headers: authHeader(token),
  })
  return data
}

export async function getListenInRecords(projectId: number, token: string): Promise<ListenInRecord[]> {
  const { data } = await client.get<ListenInRecord[]>(`/api/dashboard/projects/${projectId}/listen-in-records`, {
    headers: authHeader(token),
  })
  return data
}

export async function getUploadLog(projectId: number, token: string): Promise<UploadLogEntry[]> {
  const { data } = await client.get<UploadLogEntry[]>(`/api/dashboard/projects/${projectId}/upload-log`, {
    headers: authHeader(token),
  })
  return data
}

export async function getAllUploads(token: string): Promise<UploadLogEntry[]> {
  // Uses the admin upload-log endpoint (no project filter) via the users/upload-log pattern
  // The backend get_upload_log(project_id=None) returns all uploads
  const { data } = await client.get<UploadLogEntry[]>('/api/dashboard/uploads', {
    headers: authHeader(token),
  })
  return data
}

export async function uploadBackcheck(
  projectId: number,
  file: File,
  token: string,
  waveLabel?: string,
): Promise<{ upload_id: string; row_count: number }> {
  const fd = new FormData()
  fd.append('file', file)
  if (waveLabel) fd.append('wave_label', waveLabel)
  const { data } = await client.post(`/api/dashboard/projects/${projectId}/backcheck`, fd, {
    headers: { ...authHeader(token), 'Content-Type': 'multipart/form-data' },
  })
  return data
}

export async function uploadListenIn(
  projectId: number,
  file: File,
  token: string,
  waveLabel?: string,
): Promise<{ upload_id: string; row_count: number }> {
  const fd = new FormData()
  fd.append('file', file)
  if (waveLabel) fd.append('wave_label', waveLabel)
  const { data } = await client.post(`/api/dashboard/projects/${projectId}/listen-in`, fd, {
    headers: { ...authHeader(token), 'Content-Type': 'multipart/form-data' },
  })
  return data
}

export async function addManualListenIn(
  projectId: number,
  body: ManualListenInBody,
  token: string,
): Promise<void> {
  await client.post(`/api/dashboard/projects/${projectId}/listen-in/manual`, body, {
    headers: authHeader(token),
  })
}

export async function deleteListenIn(projectId: number, recordId: number, token: string): Promise<void> {
  await client.delete(`/api/dashboard/projects/${projectId}/listen-in/${recordId}`, {
    headers: authHeader(token),
  })
}

export async function deleteUpload(uploadId: string, reportType: string, token: string): Promise<void> {
  await client.delete(`/api/dashboard/uploads/${uploadId}`, {
    params: { report_type: reportType },
    headers: authHeader(token),
  })
}

// Users

export async function getDashboardUsers(token: string): Promise<DashboardUser[]> {
  const { data } = await client.get<DashboardUser[]>('/api/dashboard/users', {
    headers: authHeader(token),
  })
  return data
}

export async function createDashboardUser(
  email: string,
  password: string,
  full_name: string,
  role: string,
  token: string,
): Promise<void> {
  await client.post('/api/dashboard/users', { email, password, full_name, role }, {
    headers: authHeader(token),
  })
}

export async function updateUserRole(userId: number, role: string, token: string): Promise<void> {
  await client.put(`/api/dashboard/users/${userId}/role`, { role }, {
    headers: authHeader(token),
  })
}

export async function toggleUserActive(userId: number, is_active: boolean, token: string): Promise<void> {
  await client.patch(`/api/dashboard/users/${userId}/active`, { is_active }, {
    headers: authHeader(token),
  })
}

// Projects

export async function createProjectFull(body: CreateProjectFullBody, token: string): Promise<ProjectSummary> {
  const { data } = await client.post<ProjectSummary>('/api/dashboard/projects/full', body, {
    headers: authHeader(token),
  })
  return data
}

export async function updateProject(
  projectId: number,
  body: Partial<CreateProjectFullBody & { status: string }>,
  token: string,
): Promise<ProjectSummary> {
  const { data } = await client.put<ProjectSummary>(`/api/dashboard/projects/${projectId}`, body, {
    headers: authHeader(token),
  })
  return data
}

// Assignments

export async function getProjectAssignees(projectId: number, token: string): Promise<ProjectAssignee[]> {
  const { data } = await client.get<ProjectAssignee[]>(`/api/dashboard/projects/${projectId}/assignees`, {
    headers: authHeader(token),
  })
  return data
}

export async function assignUser(projectId: number, userId: number, token: string): Promise<void> {
  await client.post(`/api/dashboard/projects/${projectId}/assignees`, { user_id: userId }, {
    headers: authHeader(token),
  })
}

export async function removeAssignee(projectId: number, userId: number, token: string): Promise<void> {
  await client.delete(`/api/dashboard/projects/${projectId}/assignees/${userId}`, {
    headers: authHeader(token),
  })
}

// Supervisors

export async function getSupervisors(token: string): Promise<Supervisor[]> {
  const { data } = await client.get<Supervisor[]>('/api/dashboard/supervisors', { headers: authHeader(token) })
  return data
}

export async function createSupervisor(body: Omit<Supervisor, 'id' | 'created_at'>, token: string): Promise<Supervisor> {
  const { data } = await client.post<Supervisor>('/api/dashboard/supervisors', body, { headers: authHeader(token) })
  return data
}

export async function updateSupervisor(id: number, body: Omit<Supervisor, 'id' | 'created_at'>, token: string): Promise<void> {
  await client.put(`/api/dashboard/supervisors/${id}`, body, { headers: authHeader(token) })
}

export async function deleteSupervisor(id: number, token: string): Promise<void> {
  await client.delete(`/api/dashboard/supervisors/${id}`, { headers: authHeader(token) })
}

// Interviewers registry

export async function getInterviewers(token: string): Promise<Interviewer[]> {
  const { data } = await client.get<Interviewer[]>('/api/dashboard/interviewers', { headers: authHeader(token) })
  return data
}

export async function upsertInterviewer(
  body: { interviewer_code: string; name?: string; supervisor_id?: number | null; region?: string; is_active?: number },
  token: string,
): Promise<Interviewer> {
  const { data } = await client.post<Interviewer>('/api/dashboard/interviewers', body, { headers: authHeader(token) })
  return data
}

export async function bulkUpsertSupervisors(names: string[], token: string): Promise<Record<string, number>> {
  const { data } = await client.post<Record<string, number>>('/api/dashboard/supervisors/bulk-upsert', { names }, {
    headers: authHeader(token),
  })
  return data
}

export async function getInterviewerMetrics(code: string, token: string): Promise<InterviewerMetrics> {
  const { data } = await client.get<InterviewerMetrics>(`/api/dashboard/interviewers/${encodeURIComponent(code)}/metrics`, {
    headers: authHeader(token),
  })
  return data
}

export async function getInterviewerAnalytics(
  token: string,
  params?: { project_id?: number; supervisor_id?: number; region?: string },
): Promise<InterviewerAnalytics> {
  const p = new URLSearchParams()
  if (params?.project_id) p.set('project_id', String(params.project_id))
  if (params?.supervisor_id) p.set('supervisor_id', String(params.supervisor_id))
  if (params?.region) p.set('region', params.region)
  const qs = p.toString() ? `?${p.toString()}` : ''
  const { data } = await client.get<InterviewerAnalytics>(`/api/dashboard/interviewers/analytics${qs}`, {
    headers: authHeader(token),
  })
  return data
}

export function buildExportUrl(
  token: string,
  params?: { project_id?: number; supervisor_id?: number; region?: string },
): string {
  const p = new URLSearchParams()
  if (params?.project_id) p.set('project_id', String(params.project_id))
  if (params?.supervisor_id) p.set('supervisor_id', String(params.supervisor_id))
  if (params?.region) p.set('region', params.region)
  const qs = p.toString() ? `?${p.toString()}` : ''
  return `/api/dashboard/interviewers/export${qs}`
}

export async function downloadInterviewerReport(
  token: string,
  params?: { project_id?: number; supervisor_id?: number; region?: string },
): Promise<void> {
  const p = new URLSearchParams()
  if (params?.project_id) p.set('project_id', String(params.project_id))
  if (params?.supervisor_id) p.set('supervisor_id', String(params.supervisor_id))
  if (params?.region) p.set('region', params.region)
  const qs = p.toString() ? `?${p.toString()}` : ''
  const resp = await client.get(`/api/dashboard/interviewers/export${qs}`, {
    headers: authHeader(token),
    responseType: 'blob',
  })
  const url = URL.createObjectURL(new Blob([resp.data]))
  const a = document.createElement('a')
  a.href = url
  const cd = (resp.headers['content-disposition'] as string | undefined) ?? ''
  const match = cd.match(/filename="([^"]+)"/)
  a.download = match?.[1] ?? 'interviewer_report.xlsx'
  a.click()
  URL.revokeObjectURL(url)
}

// Templates

export async function uploadPerformance(
  projectId: number,
  file: File,
  token: string,
  waveLabel?: string,
): Promise<{ upload_id: string; row_count: number }> {
  const fd = new FormData()
  fd.append('file', file)
  if (waveLabel) fd.append('wave_label', waveLabel)
  const { data } = await client.post(`/api/dashboard/projects/${projectId}/performance`, fd, {
    headers: { ...authHeader(token), 'Content-Type': 'multipart/form-data' },
  })
  return data
}

export async function uploadTiming(
  projectId: number,
  file: File,
  token: string,
  waveLabel?: string,
): Promise<{ upload_id: string; row_count: number }> {
  const fd = new FormData()
  fd.append('file', file)
  if (waveLabel) fd.append('wave_label', waveLabel)
  const { data } = await client.post(`/api/dashboard/projects/${projectId}/timing`, fd, {
    headers: { ...authHeader(token), 'Content-Type': 'multipart/form-data' },
  })
  return data
}

export async function uploadCancelled(
  projectId: number,
  file: File,
  token: string,
  waveLabel?: string,
): Promise<{ upload_id: string; row_count: number }> {
  const fd = new FormData()
  fd.append('file', file)
  if (waveLabel) fd.append('wave_label', waveLabel)
  const { data } = await client.post(`/api/dashboard/projects/${projectId}/cancelled`, fd, {
    headers: { ...authHeader(token), 'Content-Type': 'multipart/form-data' },
  })
  return data
}

export interface PerformanceRecord {
  id: number
  interviewer_id: string | null
  region: string | null
  first_interview: string | null
  last_interview: string | null
  interview_completes: number
  accompaniments: number
  backcheck_completed: number
  cancelled_interviews: number
}

export interface TimingRecord {
  id: number
  instance_id: string | null
  interviewer_id: string | null
  region: string | null
  interview_date: string | null
  duration_minutes: number | null
}

export interface CancelledRecord {
  id: number
  instance_id: string | null
  interviewer_id: string | null
  region: string | null
  interview_date: string | null
  interview_length: number | null
  active_length: number | null
  interviewer_performance: string | null
}

export async function getPerformanceRecords(projectId: number, token: string): Promise<PerformanceRecord[]> {
  const { data } = await client.get<PerformanceRecord[]>(`/api/dashboard/projects/${projectId}/performance-records`, {
    headers: authHeader(token),
  })
  return data
}

export async function getTimingRecords(projectId: number, token: string): Promise<TimingRecord[]> {
  const { data } = await client.get<TimingRecord[]>(`/api/dashboard/projects/${projectId}/timing-records`, {
    headers: authHeader(token),
  })
  return data
}

export async function getCancelledRecords(projectId: number, token: string): Promise<CancelledRecord[]> {
  const { data } = await client.get<CancelledRecord[]>(`/api/dashboard/projects/${projectId}/cancelled-records`, {
    headers: authHeader(token),
  })
  return data
}

export function getTemplateUrl(type: 'backcheck' | 'listen_in' | 'quality_report', token: string): string {
  const base = (client.defaults.baseURL ?? '') + `/api/dashboard/templates/${type}`
  return base
}

export async function downloadTemplate(
  type: 'backcheck' | 'listen_in' | 'quality_report' | 'performance' | 'timing' | 'cancelled',
  token: string,
): Promise<void> {
  const { data } = await client.get(`/api/dashboard/templates/${type}`, {
    headers: authHeader(token),
    responseType: 'blob',
  })
  const names = {
    backcheck: 'backcheck_template.xlsx',
    listen_in: 'listen_in_template.xlsx',
    quality_report: 'quality_report_template.xlsx',
    performance: 'performance_template.xlsx',
    timing: 'timing_template.xlsx',
    cancelled: 'cancelled_template.xlsx',
  }
  const url = URL.createObjectURL(new Blob([data]))
  const a = document.createElement('a')
  a.href = url
  a.download = names[type]
  a.click()
  URL.revokeObjectURL(url)
}

// Combined report

export async function downloadCombinedReport(projectId: number, token: string, projectName: string): Promise<void> {
  const { data } = await client.get(`/api/dashboard/projects/${projectId}/combined-report`, {
    headers: authHeader(token),
    responseType: 'blob',
  })
  const url = URL.createObjectURL(new Blob([data]))
  const a = document.createElement('a')
  a.href = url
  a.download = `${projectName.replace(/\s+/g, '_')}_combined_report.xlsx`
  a.click()
  URL.revokeObjectURL(url)
}
