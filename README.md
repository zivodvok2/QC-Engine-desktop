# QC Automation Engine

A Python-based Quality Control system for CATI survey data with a Streamlit UI.

## Setup

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run the app
streamlit run app.py
```

Then open http://localhost:8501 in your browser.

## Features

- **File Upload** — CSV, XLSX, XLS via drag-and-drop or browse
- **QC Report** — Missing values, range outliers, duplicates, logic rule violations, constant columns
- **EDA** — Distributions, correlation matrix, missing value heatmap
- **Data Preview** — Filterable, column-selectable table
- **Logic Rules** — Add skip-pattern rules from the sidebar (e.g. "If Q5=No then Q6 must be null")
- **Export** — One-click Excel report with QC flags + EDA sheets

## Project Structure

```
qc_project/
├── app.py               ← Streamlit UI (run this)
├── requirements.txt
├── config/
│   └── rules.json       ← Default QC rules (edit to customise)
├── core/
│   ├── loader.py        ← CSV/XLSX/SAV ingestion
│   ├── cleaner.py       ← Null normalisation, type coercion
│   ├── validator.py     ← BaseCheck + CheckResult classes
│   ├── rule_engine.py   ← Config-driven check orchestrator
│   ├── reporter.py      ← Excel/CSV output generation
│   └── utils.py         ← Logging, config helpers
├── checks/
│   ├── missing_checks.py
│   ├── range_checks.py
│   ├── logic_checks.py
│   └── pattern_checks.py
└── tests/
    └── test_validations.py
```

## CLI Usage (no UI)

```bash
python main.py --input data/survey.csv --config config/rules.json --output outputs/
```

## Adding Custom Rules

Edit `config/rules.json` to add range rules, pattern checks, or logic rules permanently.
Or use the sidebar in the UI to add logic rules on the fly.
