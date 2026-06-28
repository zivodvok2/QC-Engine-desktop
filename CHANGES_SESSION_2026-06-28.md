# Session Changes — 2026-06-28

## Goal
Connect Servallab (React+FastAPI QC tool) to the manager dashboard so:
- Non-technical users (ops managers, project leads) can access results at `dashboard.servallab.com` without ever touching Servallab
- QC officers save results + supporting files directly from Servallab
- Interviewer and supervisor registries are auto-populated from QC data
- Dashboard shows real QC flag counts per interviewer

---

## Files Modified

### 1. `shared_db.py`
**Added** `upsert_supervisors_bulk(names: list) -> dict` at the bottom of the Supervisors section.

```python
def upsert_supervisors_bulk(names: list) -> dict:
    if not db_available() or not names:
        return {}
    conn = get_conn()
    result: dict = {}
    for raw in names:
        name = str(raw).strip()
        if not name or name.lower() in ("none", "null", "nan", ""):
            continue
        existing = conn.execute("SELECT id FROM supervisors WHERE name=?", (name,)).fetchone()
        if existing:
            result[name] = existing["id"]
        else:
            cur = conn.execute("INSERT INTO supervisors (name) VALUES (?)", (name,))
            result[name] = cur.lastrowid
    conn.commit()
    conn.close()
    return result
```

---

### 2. `routers/dashboard.py`
**Two changes:**

a) `POST /interviewers` — changed auth from `_require_admin(user)` to `_require_upload(user)`.
   - This was the root cause of the empty interviewer registry: non-admins (QC officers) couldn't register interviewers.

b) Added `BulkUpsertSupervisorsBody` model and `POST /supervisors/bulk-upsert` endpoint:

```python
class BulkUpsertSupervisorsBody(BaseModel):
    names: list[str]

@router.post("/supervisors/bulk-upsert")
def bulk_upsert_supervisors(body: BulkUpsertSupervisorsBody, user: dict = Depends(get_current_user)):
    _require_db()
    _require_upload(user)
    return shared_db.upsert_supervisors_bulk(body.names)
```

---

### 3. `routers/projects.py`
**Added QC flag overlay when saving results.**

a) Added `job_id: Optional[str] = None` to `SaveQCRequest` model.

b) Added imports: `from job_store import file_store, job_store`

c) After loading records, added overlay block that reads the in-memory job results
   and stamps `duration_flag` / `straight_lining` on each record based on which
   instance IDs appeared in the QC check flagged rows:

```python
if req.job_id:
    try:
        job = await job_store.get(req.job_id)
        if job and job.status == "complete":
            checks = (job.results or {}).get("checks", [])
            dur_flagged: set = set()
            sl_flagged: set = set()
            for check in checks:
                cname = check.get("check_name", "")
                for row in check.get("flagged_rows", []):
                    iid = str(
                        row.get("INSTANCE_ID") or row.get("instance_id") or
                        row.get("Instance ID") or row.get("Instance_ID") or ""
                    ).strip()
                    if not iid:
                        continue
                    if "duration" in cname:
                        dur_flagged.add(iid)
                    if "straight" in cname:
                        sl_flagged.add(iid)
            for rec in records:
                iid = str(rec.get("instance_id") or "").strip()
                if not iid:
                    continue
                if rec.get("duration_flag") is None:
                    rec["duration_flag"] = "Flag" if iid in dur_flagged else "Pass"
                if rec.get("straight_lining") is None:
                    rec["straight_lining"] = "Flag" if iid in sl_flagged else "Pass"
    except Exception:
        pass  # non-blocking
```

---

### 4. `datasense-ui/src/api/projects.ts`
**Added `jobId` parameter to `saveQCResults()`.**

```typescript
export async function saveQCResults(
  projectId: number,
  fileId: string,
  filename: string,
  token: string,
  waveLabel?: string,
  jobId?: string,          // NEW
): Promise<SaveQCResult> {
  const { data } = await client.post<SaveQCResult>(
    `/api/projects/${projectId}/qc-results`,
    { file_id: fileId, filename, wave_label: waveLabel || null, job_id: jobId || null },
    { headers: authHeader(token) },
  )
  return data
}
```

---

### 5. `datasense-ui/src/api/dashboard.ts`
**Added `bulkUpsertSupervisors()` function.**

```typescript
export async function bulkUpsertSupervisors(names: string[], token: string): Promise<Record<string, number>> {
  const { data } = await client.post<Record<string, number>>(
    '/api/dashboard/supervisors/bulk-upsert',
    { names },
    { headers: authHeader(token) },
  )
  return data
}
```

---

### 6. `datasense-ui/src/components/tabs/Interviewers.tsx`
**Added supervisor auto-registration in `riskMutation.onSuccess`.**

After unregistered interviewers are auto-registered, this block fires:

```typescript
if (authToken && supervisorCol && data.rows.length > 0) {
  const uniqueSupNames = [...new Set(
    (data.rows as RiskRow[])
      .map(r => r.supervisor)
      .filter((s): s is string => !!s && s !== 'None' && s !== 'null' && s !== 'nan')
  )]
  if (uniqueSupNames.length > 0) {
    bulkUpsertSupervisors(uniqueSupNames, authToken).then(nameToId => {
      Promise.allSettled(
        (data.rows as RiskRow[]).map(row => {
          const code = String(row[data.interviewer_column] ?? '')
          const supName = row.supervisor && row.supervisor !== 'None' && row.supervisor !== 'null'
            ? String(row.supervisor) : null
          const supId = supName ? (nameToId[supName] ?? null) : null
          if (code && supId) {
            return upsertInterviewer({ interviewer_code: code, supervisor_id: supId }, authToken)
          }
        }).filter(Boolean) as Promise<unknown>[]
      )
    }).catch(() => {})
  }
}
```

---

### 7. `datasense-ui/src/components/tabs/QCReport.tsx`
**Three additions:**

a) New imports at top:
```typescript
import { getUploadLog, uploadBackcheck, uploadListenIn, uploadPerformance, uploadCancelled } from '../../api/dashboard'
```

b) `InterviewerRiskPanel` — changed early return when no interviewer column is set.
   Instead of returning `null`, renders an inline prompt:
```tsx
if (!interviewerCol && !hasItvRows) {
  return (
    <div className="card border-line px-4 py-3 flex flex-wrap items-center gap-3">
      <Users size={14} className="text-muted shrink-0" />
      <span className="text-xs text-muted flex-1 min-w-0">
        Enter the interviewer column name to auto-compute risk scores inline
      </span>
      <input
        type="text"
        value={promptCol}
        onChange={e => setPromptCol(e.target.value)}
        onKeyDown={e => { if (e.key === 'Enter' && promptCol.trim()) setItvTabState({ intCol: promptCol.trim() }) }}
        placeholder="e.g. interviewer_id"
        className="w-36 text-xs"
      />
      <button
        onClick={() => { if (promptCol.trim()) setItvTabState({ intCol: promptCol.trim() }) }}
        disabled={!promptCol.trim()}
        className="btn-ghost text-xs shrink-0"
      >
        Analyze →
      </button>
    </div>
  )
}
```

c) New `SupportingFilesSection` component (above `SaveToProject`) and updated `if (saved)` block.

`SupportingFilesSection` renders 4 upload rows (Backcheck, Listen-in, Performance, Cancelled).
Each row has a file picker + Upload button that calls the matching dashboard API endpoint.

`if (saved)` block in `SaveToProject` was updated from a simple flex row to:
```tsx
if (saved) {
  return (
    <div className="card p-4 space-y-0">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2 text-accent text-sm">
          <Check size={14} />
          Results saved to project.
        </div>
        {savedProjectId !== null && (
          <button
            onClick={() => { setDashboardMode(true); setDashboardProject(savedProjectId) }}
            className="btn-ghost text-xs flex items-center gap-1.5"
          >
            <Database size={12} /> View in Dashboard
          </button>
        )}
      </div>
      {savedProjectId !== null && authToken && (
        <SupportingFilesSection
          projectId={savedProjectId}
          waveLabel={waveLabel}
          token={authToken}
        />
      )}
    </div>
  )
}
```

Also: `jobId` is destructured from `useAppStore()` inside `SaveToProject` and passed as the 6th argument to `saveQCResults()`.

---

### 8. `dashboard/database.py`
**Added two helper functions** before `get_project_activity()`:
- `get_all_interviewers()` — returns all rows from `interviewers` table
- `get_all_supervisors()` — returns all rows from `supervisors` table

---

### 9. `dashboard/pages_modules/interviewers.py` (NEW FILE)
New Streamlit page for the Interviewers registry in the manager dashboard.

Shows:
- KPI cards: total interviewers, active, supervisors, high-risk count
- Supervisor summary cards
- Filterable table: code, name, supervisor, region, total interviews, duration flags, SL flags, flag rate, risk level, status

Uses:
- `db.get_all_interviewers()`
- `db.get_all_supervisors()`
- `db.get_at_risk_interviewers_cross_project(min_interviews=1, flag_pct_threshold=0)`

---

### 10. `dashboard/app.py`
**Two additions to the sidebar and router:**

Sidebar nav:
```python
_nav_button("Interviewers", "interviewers", "◈")
```

Router:
```python
elif page == "interviewers":
    from pages_modules import interviewers
    interviewers.show()
```

---

### 11. `datasense-ui/.env.production` (NEW FILE)
```
VITE_API_URL=https://servalab.onrender.com
```

Ensures `npm run build` points the frontend at the production backend automatically.
`.env.local` (dev, `http://localhost:8000`) is unchanged.

---

## End-to-End Flow After These Changes

1. QC officer uploads survey data to Servallab → runs QC checks
2. On QC Report tab: interviewer column prompt appears inline if not already configured
3. Officer clicks "Save to dashboard project" → picks/creates project → saves
   - `job_id` is passed so duration & SL flags are overlaid on every record in the DB
4. After save: "Results saved to project ✓" + **SupportingFilesSection** appears immediately
   - Officer uploads Backcheck / Listen-in / Performance / Cancelled files right there
5. Meanwhile, when the Interviewers tab was computed, supervisors were auto-registered into the DB
6. Manager/project lead opens `dashboard.servallab.com` (React dashboard mode)
   - Sees project with real flag counts per interviewer
   - Interviewers page shows full registry with supervisor linkage and flag rates
