# DataSense — QC Automation Engine

A Python + Streamlit quality control system for CATI survey data with interactive charts, AI-powered verbatim scoring, and a modular UI.

## Quick Start

```bash
pip install -r requirements.txt
streamlit run app.py
```

Open http://localhost:8501. Upload a CSV or Excel file from the sidebar to begin.

### With Groq AI (verbatim checks)

```bash
# Windows PowerShell
$env:GROQ_API_KEY="gsk_your_key"; python -m streamlit run app.py

# macOS / Linux
GROQ_API_KEY=gsk_your_key streamlit run app.py
```

Get a free key at [console.groq.com](https://console.groq.com). When the server key is pre-configured, users see "✓ Server key active" and can optionally add their own personal key as a fallback if the server limit is reached.

## Features

| Tab | What it does |
|-----|-------------|
| **QC Report** | Missing values, range outliers, duplicates, logic violations, pattern checks — grouped by severity |
| **Logic** | Interactive IF/THEN rule builder with multi-condition support and rich operators |
| **Straightlining** | Detects respondents who gave the same answer across a question battery |
| **Verbatim** | Groq AI batch-scores open-ended responses for grammar, coherence, relevance, and length quality |
| **Interviewers** | Duration anomalies, productivity outliers, fabrication detection per interviewer |
| **EDA** | Interactive Plotly charts (bar, line, scatter, histogram, heatmap, box) with column pickers; cached for performance |
| **Data** | Filterable, column-selectable data preview |
| **Config** | Live view of the active QC config and custom logic rules |

## CLI Usage (no UI)

```bash
python main.py --input data/survey.csv --config config/rules.json --output outputs/
```

## Project Structure

```
├── app.py                      ← Streamlit entry point
├── main.py                     ← CLI entry point
├── requirements.txt
├── config/
│   ├── rules.json              ← Default QC rules
│   └── themes.json             ← Dark / Light / Midnight themes
├── core/
│   ├── loader.py               ← CSV / XLSX / SAV ingestion
│   ├── cleaner.py              ← Null normalisation, type coercion
│   ├── validator.py            ← BaseCheck + CheckResult base classes
│   ├── rule_engine.py          ← Config-driven check orchestrator
│   ├── reporter.py             ← Excel / CSV output
│   └── utils.py                ← Logging, config helpers
├── checks/
│   ├── missing_checks.py
│   ├── range_checks.py
│   ├── logic_checks.py
│   ├── pattern_checks.py
│   ├── advanced_checks.py      ← Straightlining, interviewer, consent, fabrication
│   └── verbatim_checks.py      ← Groq AI verbatim quality scoring
├── ui/
│   ├── sidebar.py              ← Upload, QC settings, all check toggles
│   ├── settings.py             ← Theme picker, Groq key, version/changelog
│   ├── onboarding.py           ← First-run guide
│   ├── components/
│   │   └── drag_drop.py        ← Column picker widgets (multiselect/selectbox)
│   └── tabs/
│       ├── qc_tab.py
│       ├── logic_tab.py
│       ├── straightlining_tab.py
│       ├── verbatim_tab.py
│       ├── eda_tab.py
│       └── data_tab.py
├── static/
│   ├── manifest.json           ← PWA manifest
│   ├── icon-192.svg
│   └── icon-512.svg
├── assets/
│   ├── app_version.json
│   └── onboarding_steps.json
└── tests/
    └── test_validations.py
```

## Adding Custom Rules

**Permanent rules** — edit `config/rules.json`:

```json
{
  "range_rules":  [{"column": "age", "min": 18, "max": 99}],
  "logic_rules":  [{
    "description": "Under 18 must not have job title",
    "if_conditions":   [{"column": "age",       "operator": "<",       "value": 18}],
    "then_conditions": [{"column": "job_title",  "operator": "is_null"}]
  }],
  "pattern_rules": [{"column": "email", "pattern": "^[^@]+@[^@]+\\.[^@]+$", "description": "Valid email"}]
}
```

**Ad-hoc rules** — use the Logic tab in the UI.

**Custom check** — subclass `BaseCheck` in `checks/`, implement `run(df) -> CheckResult`, register in `core/rule_engine.py`.

## Logic Rule Operators

`>` `<` `>=` `<=` `==` `!=` `is_null` `not_null` `is_numeric` `is_string` `in_list` `not_in_list`

## Running Tests

```bash
pytest tests/ -v
```

## Installing as a Desktop App (Chrome)

1. Open the app in Chrome
2. Click ⋮ menu → **Save and share → Create shortcut**
3. Check **"Open as window"** → Create

This opens DataSense as a standalone window with no browser chrome, identical to a PWA install. A full PWA install button appears automatically after deploying to HTTPS.

## Deployment (Streamlit Community Cloud)

1. Push to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io) → New app → select this repo, `main`, `app.py`
3. Under **Advanced → Secrets**, add:
   ```toml
   GROQ_API_KEY = "gsk_your_key"
   ```
