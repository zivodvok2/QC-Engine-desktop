# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## Project Overview

**Servallab** — CATI survey data Quality Control engine.  
GitHub: `https://github.com/zivodvok2/QC-Engine-desktop`

The project has **three stacks**:

| Stack | Purpose | Status | URL |
|---|---|---|---|
| React + FastAPI | Primary QC analysis UI + API | Active — deployed | `servallab.com` |
| Streamlit (`dashboard/`) | Manager/QC Officer tracking dashboard | Active — subdomain | `dashboard.servallab.com` |
| Streamlit (`app.py`) | Legacy local-only UI | Secondary — not deployed | local only |

**Key distinction:** `dashboard/` is for managers and QC officers to track project health across all active surveys. It is **not** connected to the Interviewers tab in the main React UI — it is a fully separate app deployed under its own subdomain.

---

## Running the Project

### Production stack (React + FastAPI)

Run both servers — frontend on 5173, backend on 8000.

```bash
# Backend (FastAPI) — from repo root
python -m uvicorn api:app --port 8000 --reload

# Frontend (React/Vite) — from datasense-ui/
cd datasense-ui
npm run dev
# → http://localhost:5173
```

Frontend proxies `/api` → `http://localhost:8000` in dev (configured in `vite.config.ts`).  
In production set `VITE_API_URL` env var to the deployed backend URL.

### Manager/QC Dashboard (subdomain app)

```bash
# From dashboard/ directory
cd dashboard
pip install -r requirements.txt   # first time only
streamlit run app.py --server.port 8502
# → http://localhost:8502
```

Default admin credentials (first run): `admin@servallab.com` / `admin1234`  
In production: deployed to `dashboard.servallab.com` via `dashboard/fly.toml`

### Legacy Streamlit UI

```bash
python -m streamlit run app.py
# → http://localhost:8501
```

### CLI (headless)

```bash
python main.py --input data/survey.csv --config config/rules.json --output outputs/
```

### Tests

```bash
pytest tests/
pytest tests/test_validations.py::test_duration_check -v
```

### Install dependencies

```bash
# Python
pip install -r requirements.txt

# Frontend
cd datasense-ui && npm install
```

---

## Architecture

### Frontend — `datasense-ui/` (React + TypeScript + Tailwind + Vite)

```
datasense-ui/src/
  App.tsx                     # Root: LandingPage, AppShell, DemosModal, TabContent
  store/appStore.ts           # Zustand store — file state, job state, config, ui flags
  components/
    layout/
      Sidebar.tsx             # Left panel: file upload, QC config toggles, demos link
      Header.tsx              # Tab bar with icons (10 tabs)
    upload/FileUpload.tsx     # Dropzone; compact mode has X (clear) + compare button
    tabs/
      QCReport.tsx            Straightlining.tsx  Interviewers.tsx
      LogicChecks.tsx         EDA.tsx             WaveCompare.tsx
      Quotas.tsx              DataPreview.tsx     Config.tsx
      Demos.tsx               # Demo video gallery (10 cards, tag filter, modal on landing)
    settings/SettingsPanel.tsx
    onboarding/OnboardingTooltip.tsx
  api/                        # Axios wrappers: upload.ts, qc.ts, eda.ts, interviewers.ts,
                              #   compare.ts, ai.ts, client.ts
  hooks/                      # useQCRun.ts, useColumns.ts, useHealth.ts
  types/index.ts              # QCConfig, QCResults, DEFAULT_CONFIG
```

Key UX behaviours:
- **No file loaded**: landing page shown; Demos opens as a modal overlay (X to close, click-outside closes)
- **File loaded**: full header tab bar; Demos is a regular tab; X button on file clears state without refresh; "Compare with another file" navigates to Wave Compare tab
- `clearFile()` in store resets file/job/results but **keeps config**
- `reset()` resets everything including config

### Backend — `api.py` + `routers/` (FastAPI + Python)

```
api.py              # FastAPI app, CORS, lifespan (temp-file cleanup every 3600s)
routers/
  qc.py             # POST /api/upload, POST /api/run, GET /api/job/{id}
  eda.py            # POST /api/eda/summary, /api/eda/distribution, /api/eda/correlation
  interviewers.py   # POST /api/interviewers/risk
  compare.py        # POST /api/compare/upload-wave2, /api/compare/diff, /api/compare/interviewer-shift
  ai.py             # POST /api/ai/suggest-rules (Groq)
schemas.py          # Pydantic request/response models
job_store.py        # In-memory job registry + UPLOAD_DIR / REPORTS_DIR paths
```

Uploaded files live in a temp directory and are auto-deleted after 1 hour.

### QC Pipeline — `core/` + `checks/`

Pipeline: **Load → Clean → Validate → Report**

1. `core/loader.py` — ingests CSV/XLSX/SAV → DataFrame
2. `core/cleaner.py` — normalises nulls, coerces types
3. `core/rule_engine.py` (`RuleEngine`) — reads config, instantiates checks, calls `.run(df)`
4. `core/reporter.py` — Excel/CSV output (Streamlit path); React gets JSON from API

All checks extend `BaseCheck` (`core/validator.py`) and return `CheckResult`:
- `flagged_rows` — DataFrame of bad rows (internal cols prefixed `_`)
- `severity` — `"info"` | `"warning"` | `"critical"`
- `metadata` — check-specific stats dict

Check modules:
- `checks/missing_checks.py` — `MissingValueCheck`, `HighMissingColumnCheck`
- `checks/range_checks.py` — `RangeCheck`, `DurationCheck`
- `checks/logic_checks.py` — `LogicCheck` (multi-condition IF/THEN), `DuplicateCheck`; exports `_evaluate_condition()` reused by `advanced_checks.py`
- `checks/pattern_checks.py` — `PatternCheck` (regex), `AnomalyCheck` (IQR)
- `checks/advanced_checks.py` — `StraightliningCheck`, `InterviewerDurationCheck`, `InterviewerProductivityCheck`, `ConsentEligibilityCheck`, `FabricationCheck`
- `checks/verbatim_checks.py` — Groq AI grammar scoring
- `checks/consistency_checks.py` — cross-column consistency

### Adding a New Check

1. Add class in appropriate `checks/` module extending `BaseCheck`
2. Set `name`, `issue_type`, `severity` class attrs
3. Implement `run(self, df) -> CheckResult` using `self._make_result(flagged_df, metadata)`
4. Register in `RuleEngine._build_checks()` in `core/rule_engine.py`
5. Add a corresponding API endpoint in `routers/qc.py` if it needs separate exposure

### Logic Rule Format

```json
{
  "description": "Under-18 should not have a salary",
  "if_conditions":   [{"column": "age",    "operator": "<",  "value": 18}],
  "then_conditions": [{"column": "salary", "operator": "is_null"}]
}
```

Supported operators: `>`, `<`, `>=`, `<=`, `==`, `!=`, `is_null`, `not_null`, `is_numeric`, `is_string`, `in_list`, `not_in_list`.

---

## Demo Videos

Demo cards live in `datasense-ui/src/components/tabs/Demos.tsx`.  
To add a real video, set the `video` field on a `DEMO` entry to a local path or URL:

```ts
{ title: 'Uploading Your Data', video: 'demos/upload.mp4' }   // local file
{ title: 'Uploading Your Data', video: 'https://youtu.be/XYZ' } // YouTube
```

`st.video()` / `<video>` handle both. Until set, cards show a "Coming soon" placeholder.

---

## Deployment

- Repo: `https://github.com/zivodvok2/QC-Engine-desktop`
- Frontend built with `npm run build` → `datasense-ui/dist/`
- Backend deployed separately (Render/Fly); set `VITE_API_URL` to point the frontend at it
- Streamlit app (`app.py`) is **not** part of the deployed stack
