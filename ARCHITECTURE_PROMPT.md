# Servallab Architecture Redesign — Claude Code Prompt

> Paste this into a fresh Claude Code session to implement the full redesign.
> Last updated: 2026-06-17

---

You are implementing a targeted redesign of the Servallab QC Engine — a FastAPI + React (Vite/TS)
application. The repo is at /home/dvock/QC-Engine-desktop. Read this entire prompt before touching any file.

─────────────────────────────────────────────────────────────────────────────
STREAMLIT — ALREADY DECIDED: DROP IT
─────────────────────────────────────────────────────────────────────────────

The Streamlit app (dashboard/app.py and dashboard/pages_modules/) is dead code.
The only reference to it in the live app was a broken "Register on the dashboard" link
pointing to http://localhost:8502 in LoginModal.tsx — that has already been replaced
with a native Sign In / Register tabbed modal backed by POST /api/auth/register.

Do NOT touch dashboard/app.py or any file inside dashboard/pages_modules/.
Do NOT run or deploy the Streamlit app.
The SQLite database (dashboard/qc_dashboard.db) is still the shared database — keep it.

─────────────────────────────────────────────────────────────────────────────
WHAT EXISTS (do not rebuild, extend)
─────────────────────────────────────────────────────────────────────────────

Backend (Python/FastAPI, api.py + routers/):
  - routers/auth.py         JWT login, register (POST /api/auth/register just added),
                            get_current_user dependency
  - routers/dashboard.py    Full CRUD for projects, users, quality records, backcheck,
                            listen-in, supervisors, interviewers, upload log, combined report
  - routers/projects.py     POST /api/projects, POST /api/projects/{id}/qc-results
  - shared_db.py            FastAPI bridge to dashboard/qc_dashboard.db — includes
                            get_interviewer_metrics(), upsert_interviewer(),
                            supervisors CRUD, init_tables()

Frontend (datasense-ui/src/):
  - store/appStore.ts       Zustand; authUser/authToken (JWT in localStorage),
                            dashboardMode (boolean toggle), dashboardProjectId, dashboardView
  - api/auth.ts             login(), register() (just added), me()
  - api/dashboard.ts        Full API client: projects, quality records, backcheck, listen-in,
                            supervisors, interviewers, metrics, templates, combined report
  - api/projects.ts         getProjects(), createProject(), saveQCResults()
  - components/dashboard/   Dashboard.tsx (wrapper), Overview.tsx, ProjectDetail.tsx,
                            InterviewerDirectory.tsx,
                            tabs/{AdminTab, BackcheckTab, ListenInTab, QualityReportTab,
                            CombinedReportTab}.tsx
  - components/auth/        LoginModal.tsx — now has Sign In + Register tabs (already done)
  - components/tabs/        Interviewers.tsx (local risk analysis from uploaded file),
                            QCReport.tsx (shows results after a run)
  - App.tsx                 Renders <Dashboard /> when dashboardMode===true,
                            else renders the QC tool. Dashboard button is in Header.tsx.

Dashboard SQLite schema (dashboard/qc_dashboard.db):
  users, projects, project_assignments, quality_report_records, backcheck_records,
  listen_in_records, performance_records, timing_records, cancelled_interview_records,
  upload_log, supervisors, interviewers

─────────────────────────────────────────────────────────────────────────────
REQUIREMENT 1 — Dashboard accessible from servallab.com AND dashboard.servallab.com
─────────────────────────────────────────────────────────────────────────────

Current problem: dashboardMode is toggled via a Header button only — no URL or subdomain
awareness. On dashboard.servallab.com there is no QC tool, so the toggle makes no sense.

Changes:

1a. datasense-ui/src/App.tsx
    On mount, detect window.location.hostname. If it contains "dashboard." set
    dashboardMode(true) immediately and keep it locked (no toggle visible).
    Also accept ?mode=dashboard in the query string as a fallback trigger.

1b. datasense-ui/src/components/layout/Header.tsx
    The "Dashboard" toggle button should only render when the hostname does NOT
    contain "dashboard." (i.e. on the main QC tool domain only).
    When dashboardMode is true on the main domain, show an "Exit Dashboard" button
    that calls setDashboardMode(false).

1c. datasense-ui/src/components/dashboard/Dashboard.tsx
    Add an "Open QC Tool" button in the dashboard header, but only render it when
    window.location.hostname does NOT contain "dashboard." — on the subdomain there
    is no QC tool to return to.

1d. No build changes needed. The same dist/ bundle serves both domains.
    Document in CLAUDE.md: deploy datasense-ui/dist/ to both servallab.com and
    dashboard.servallab.com.

─────────────────────────────────────────────────────────────────────────────
REQUIREMENT 2 — File uploads through the dashboard (all QC files except survey data)
─────────────────────────────────────────────────────────────────────────────

Current state: ProjectDetail.tsx has BackcheckTab and ListenInTab. Performance, Timing,
and Cancelled Interviews exist in the SQLite schema and shared_db.py but have no
React UI or API endpoints.

2a. Backend — routers/dashboard.py
    Add (mirroring the existing backcheck pattern):
      POST /api/dashboard/projects/{id}/performance
      POST /api/dashboard/projects/{id}/timing
      POST /api/dashboard/projects/{id}/cancelled
      GET  /api/dashboard/projects/{id}/performance-records
      GET  /api/dashboard/projects/{id}/timing-records
      GET  /api/dashboard/projects/{id}/cancelled-records
    Column expectations: check dashboard/pages_modules/performance_report.py,
    timing_report.py, cancelled_interviews.py for the exact column names used there.

2b. shared_db.py
    Add insert_performance_records(), insert_timing_records(), insert_cancelled_records()
    following the same pattern as insert_backcheck_records().

2c. datasense-ui/src/api/dashboard.ts
    Add uploadPerformance(), uploadTiming(), uploadCancelled() and the three
    corresponding get*Records() fetch functions.

2d. Create new tab components:
      datasense-ui/src/components/dashboard/tabs/PerformanceTab.tsx
      datasense-ui/src/components/dashboard/tabs/TimingTab.tsx
      datasense-ui/src/components/dashboard/tabs/CancelledTab.tsx
    Each follows the BackcheckTab pattern: file uploader → wave label → upload button
    → records table with delete-by-upload capability.

2e. datasense-ui/src/components/dashboard/ProjectDetail.tsx
    Add the three new tabs. Final tab order:
    Quality Report | Backcheck | Listen-In | Performance | Timing | Cancelled |
    Combined Report | Admin

2f. routers/dashboard.py — template endpoints
    Add GET /api/dashboard/templates/performance, /timing, /cancelled returning
    minimal Excel files with correct column headers.
    Add the three types to downloadTemplate() in api/dashboard.ts.

─────────────────────────────────────────────────────────────────────────────
REQUIREMENT 3 — Push QC results to dashboard after a run
─────────────────────────────────────────────────────────────────────────────

Current state: POST /api/projects/{id}/qc-results exists and saveQCResults() is in
api/projects.ts. There is no UI button in QCReport.tsx that triggers this.

3a. Create datasense-ui/src/components/modals/SendToDashboardModal.tsx

    Props: { fileId: string; filename: string; onClose: () => void }

    Behaviour:
    - If authUser is null: show "Sign in to send results to the dashboard" + Sign In
      button (calls openLogin()) without closing the modal.
    - If authUser is present:
      a. Searchable dropdown of existing projects (getProjects()).
      b. "New project" option at the bottom revealing an inline name input — calls
         createProject(name, token) then uses the returned id.
      c. Optional "Wave label" text input (e.g. "Wave 1").
      d. "Send" calls saveQCResults(projectId, fileId, filename, token, waveLabel).
      e. On success: green confirmation + "View in Dashboard" button that calls
         setDashboardMode(true) and setDashboardProject(projectId).

3b. datasense-ui/src/components/tabs/QCReport.tsx
    Add a "Send to Dashboard" button in the report action bar (top-right area near
    the existing download button). On click, open SendToDashboardModal.

3c. routers/projects.py — after inserting quality records, extract unique interviewer_id
    values from the uploaded file rows and call shared_db.upsert_interviewer() for each.
    Use name=None, supervisor_id=None — this seeds the registry without overwriting
    existing data.

3d. api.py lifespan — call shared_db.init_tables() on startup so supervisors and
    interviewers tables always exist.

─────────────────────────────────────────────────────────────────────────────
REQUIREMENT 4 — Save results on session (guest) or account (logged in)
─────────────────────────────────────────────────────────────────────────────

4a. datasense-ui/src/store/appStore.ts
    When jobStatus transitions to 'complete', write to sessionStorage['sl_session']:
      { fileId, filename, rowCount, columnNames, results, config, ts: Date.now() }
    On store init, read sessionStorage['sl_session']. If found and ts is within 8 hours,
    restore fileId, filename, rowCount, columnNames, results, config into the store
    and set a new flag sessionRestored: boolean = true.
    Do NOT restore jobId (the job is gone from the server).
    In clearFile() and reset(), delete sessionStorage['sl_session'] and set
    sessionRestored: false.

4b. datasense-ui/src/components/upload/FileUpload.tsx
    If sessionRestored is true, show an inline notice above the dropzone:
    "Session restored from [formatted timestamp] — upload a new file to replace it."

─────────────────────────────────────────────────────────────────────────────
REQUIREMENT 5 — Interviewer metrics in QC tool, supervisor lookup, registry management
─────────────────────────────────────────────────────────────────────────────

5a. Enrich Interviewers tab with global database metrics

    datasense-ui/src/components/tabs/Interviewers.tsx:
    After local risk rows are computed, if authToken is not null, call
    getInterviewerMetrics(code, token) for each unique interviewer code. This is already
    in api/dashboard.ts and returns: info (name, supervisor_name), quality stats,
    backcheck stats, listen_in stats, by_project breakdown.

    Merge into each risk row: supervisor_name, cross_project_interviews,
    cross_project_flag_rate, bc_error_rate.

    In the risk table, add a "Supervisor" column (show "Unassigned" if null).
    In the expanded interviewer detail panel, add a "Cross-project history" section
    showing the by_project array as a compact table.

    If authToken is null, show a subtle inline note:
    "Sign in to see cross-project history and supervisor assignments."

5b. Composite risk score (QC leads will notice this)

    After merging DB metrics, compute an Overall QC Score (0–100):
      local risk score    → 40%
      cross-project flag rate → 30%
      backcheck error rate   → 20%
      listen-in fail rate    → 10%
    Show as "Overall QC Score" alongside the local score. Same colour scale.
    When DB data is unavailable (no auth), show only the local score with a note.

5c. Admin tab — supervisor and interviewer management

    datasense-ui/src/components/dashboard/tabs/AdminTab.tsx:
    After the user management section add two collapsible sections:

    SUPERVISORS
    - Table: name, email, phone, region + derived interviewer count
    - Add form: name (required), email, phone, region
    - Inline edit and delete with confirmation
    - Uses: getSupervisors(), createSupervisor(), updateSupervisor(), deleteSupervisor()

    INTERVIEWERS REGISTRY
    - Table: interviewer_code (Ipsos global ID), name, supervisor (dropdown), region,
      active toggle
    - Search/filter by code or name
    - Add form: code (required), name, supervisor (dropdown from supervisors list), region
    - "Import CSV" button: accepts CSV with columns interviewer_code, name,
      supervisor_id, region — calls upsertInterviewer() for each row
    - Uses: getInterviewers(), upsertInterviewer()
    - Roles: admin and manager can edit; qc_executive is read-only.

5d. shared_db.py init_tables()
    Add an ALTER TABLE IF NOT EXISTS guard to add interviewer_code (TEXT, nullable)
    to the users table. This lets a user account be linked to an Ipsos interviewer ID.
    Example migration pattern:
      try: conn.execute("ALTER TABLE users ADD COLUMN interviewer_code TEXT")
      except: pass  # column already exists

─────────────────────────────────────────────────────────────────────────────
REQUIREMENT 6 — Interviewer ID is global (Ipsos-wide)
─────────────────────────────────────────────────────────────────────────────

Already handled by shared_db.get_interviewer_metrics() querying across all projects.
Req 5a wires it to the UI. No additional backend work.

One UI addition in SendToDashboardModal (Req 3): after a successful send, show:
"X interviewers from this file. Y already have a supervisor assigned. Z are new."
Calculate by comparing the file's interviewer IDs against getInterviewers() before sending.

─────────────────────────────────────────────────────────────────────────────
ADDITIONAL FEATURES — implement these
─────────────────────────────────────────────────────────────────────────────

A. PROJECT HEALTH BADGES
   Overview.tsx: add a traffic-light badge per project card.
     green  → all thresholds met
     amber  → flagged% between flag_warning_pct and flag_critical_pct, OR backcheck < target
     red    → flagged% > flag_critical_pct, OR (completion < 50% AND days_to_deadline < 7)
   All inputs are already in the ProjectSummary type from the API.

B. WAVE LABEL SUGGESTION
   In SendToDashboardModal, when the user selects an existing project, call getUploadLog()
   for that project and suggest the next wave label automatically (if "Wave 1" exists →
   suggest "Wave 2").

C. AUDIT TRAIL IN PROJECT DETAIL
   In the Admin tab of ProjectDetail.tsx, add an "Upload History" section showing the
   full upload log (getUploadLog() — already available): uploader, file type, filename,
   row count, wave label, timestamp, delete button per upload.

D. QUICK STATS PILL IN SIDEBAR
   Sidebar.tsx: when authUser is logged in, show at the bottom:
   "[N] active projects · [M] interviewers on watch"
   Derive from store cache if the dashboard data has been loaded; skip if not.

E. ROLE-BASED "YOUR PERFORMANCE" BANNER
   In Interviewers.tsx: if authUser.interviewer_code is set (see Req 5d), show a
   highlighted banner at the top of the tab with the user's own metrics pulled from
   getInterviewerMetrics(authUser.interviewer_code, token). Show flag rate, projects
   worked, avg duration vs. team average. This needs no new backend work.
   Add the interviewer_code field to the user edit form in AdminTab.

─────────────────────────────────────────────────────────────────────────────
FILE MAP
─────────────────────────────────────────────────────────────────────────────

New files:
  datasense-ui/src/components/modals/SendToDashboardModal.tsx
  datasense-ui/src/components/dashboard/tabs/PerformanceTab.tsx
  datasense-ui/src/components/dashboard/tabs/TimingTab.tsx
  datasense-ui/src/components/dashboard/tabs/CancelledTab.tsx

Modified files:
  api.py                                          call shared_db.init_tables() in lifespan
  shared_db.py                                    insert_performance/timing/cancelled_records(),
                                                  interviewer_code migration in init_tables()
  routers/auth.py                                 register endpoint (ALREADY DONE)
  routers/dashboard.py                            3 upload + 3 get + 3 template endpoints
  routers/projects.py                             auto-register interviewers on QC push
  datasense-ui/src/api/auth.ts                    register() (ALREADY DONE)
  datasense-ui/src/api/dashboard.ts               upload/get for performance, timing, cancelled
  datasense-ui/src/App.tsx                        hostname/query-param dashboard detection
  datasense-ui/src/store/appStore.ts              sessionStorage snapshot + sessionRestored flag
  datasense-ui/src/components/auth/LoginModal.tsx Sign In + Register tabs (ALREADY DONE)
  datasense-ui/src/components/layout/Header.tsx   conditional dashboard toggle
  datasense-ui/src/components/layout/Sidebar.tsx  quick stats pill
  datasense-ui/src/components/dashboard/Dashboard.tsx    "Open QC Tool" conditional link
  datasense-ui/src/components/dashboard/Overview.tsx     health badges
  datasense-ui/src/components/dashboard/ProjectDetail.tsx  3 new tabs
  datasense-ui/src/components/dashboard/tabs/AdminTab.tsx  supervisors + interviewers sections
  datasense-ui/src/components/tabs/QCReport.tsx   "Send to Dashboard" button
  datasense-ui/src/components/tabs/Interviewers.tsx  DB metrics enrichment + composite score
  datasense-ui/src/components/upload/FileUpload.tsx  session restored notice

─────────────────────────────────────────────────────────────────────────────
IMPLEMENTATION ORDER
─────────────────────────────────────────────────────────────────────────────

1.  api.py lifespan → call shared_db.init_tables()
2.  shared_db.py → insert_performance/timing/cancelled, interviewer_code migration
3.  routers/dashboard.py → 3 upload + 3 get + 3 template endpoints
4.  routers/projects.py → auto-register interviewers
5.  datasense-ui/src/api/dashboard.ts → new functions
6.  SendToDashboardModal.tsx → wire to QCReport.tsx (Req 3)
7.  appStore.ts sessionStorage + FileUpload.tsx notice (Req 4)
8.  App.tsx hostname detection + Header.tsx + Dashboard.tsx nav (Req 1)
9.  PerformanceTab, TimingTab, CancelledTab + ProjectDetail.tsx tab bar (Req 2)
10. Interviewers.tsx DB enrichment + composite score (Req 5a, 5b)
11. AdminTab.tsx supervisors + interviewers sections + interviewer_code in user edit (Req 5c, 5d)
12. Bonus features A–E

─────────────────────────────────────────────────────────────────────────────
CONSTRAINTS
─────────────────────────────────────────────────────────────────────────────
- Do NOT add React Router — the app uses state-based navigation; keep that pattern.
- Do NOT touch dashboard/app.py or dashboard/pages_modules/.
- Do NOT change existing SQLite table columns — only add new columns with ALTER TABLE
  guarded by try/except, and add new tables in init_tables().
- Do NOT introduce a second database.
- Keep all styling in the existing Tailwind class system (card, card2, label, text-accent,
  text-critical, text-warning, font-display, btn-primary, etc.).
- All dashboard API endpoints require a Bearer token via get_current_user dependency.
