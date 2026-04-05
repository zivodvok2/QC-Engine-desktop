# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run the Streamlit UI
streamlit run app.py

# Run CLI (no UI)
python main.py --input data/survey.csv --config config/rules.json --output outputs/

# Run all tests
pytest tests/

# Run a single test
pytest tests/test_validations.py::test_duration_check -v
```

## Architecture

This is a CATI survey data Quality Control engine with two entry points:
- **`app.py`** — Streamlit UI (the primary interface)
- **`main.py`** — CLI for headless/batch processing

### Pipeline: Load → Clean → Validate → Report

1. **`core/loader.py`** — ingests CSV/XLSX/SAV into a DataFrame (`load()` for file paths, `load_from_buffer()` for Streamlit uploads)
2. **`core/cleaner.py`** — normalises nulls and coerces types
3. **`core/rule_engine.py`** (`RuleEngine`) — reads a config dict or JSON file, instantiates check objects, and calls `.run(df)` on each
4. **`core/reporter.py`** — generates Excel/CSV output; the Streamlit UI uses `build_report()` in `app.py` directly instead

### Check System

All checks extend `BaseCheck` (`core/validator.py`) and return a `CheckResult`. The `CheckResult` carries:
- `flagged_rows` — a DataFrame of problematic rows (internal columns prefixed with `_`)
- `severity` — `"info"` | `"warning"` | `"critical"`
- `metadata` — a dict with check-specific stats

Check modules:
- **`checks/missing_checks.py`** — `MissingValueCheck`, `HighMissingColumnCheck`
- **`checks/range_checks.py`** — `RangeCheck`, `DurationCheck`
- **`checks/logic_checks.py`** — `LogicCheck` (rich multi-condition IF/THEN), `DuplicateCheck`; exports `_evaluate_condition()` which is reused by `advanced_checks.py`
- **`checks/pattern_checks.py`** — `PatternCheck` (regex), `AnomalyCheck` (IQR outliers)
- **`checks/advanced_checks.py`** — `StraightliningCheck`, `InterviewerDurationCheck`, `InterviewerProductivityCheck`, `ConsentEligibilityCheck`, `FabricationCheck`

### Adding a New Check

1. Create a class in the appropriate `checks/` module extending `BaseCheck`
2. Set class attributes `name`, `issue_type`, `severity`
3. Implement `run(self, df) -> CheckResult` using `self._make_result(flagged_df, metadata)`
4. Register it in `RuleEngine._build_checks()` in `core/rule_engine.py`

### Logic Rule Format

`config/rules.json` uses a legacy single-condition format. The `LogicCheck` also supports a rich multi-condition format (used by the UI):

```json
{
  "description": "Under-18 should not have a salary",
  "if_conditions":   [{"column": "age",    "operator": "<",       "value": 18}],
  "then_conditions": [{"column": "salary", "operator": "is_null"}]
}
```

Supported operators: `>`, `<`, `>=`, `<=`, `==`, `!=`, `is_null`, `not_null`, `is_numeric`, `is_string`, `in_list`, `not_in_list`.

### Config

`RuleEngine` accepts either a `config_path` (JSON file) or a `config` dict directly. The Streamlit UI passes a dict built from session state, merging sidebar-defined logic rules with `st.session_state.custom_logic_rules`. The default config shape is defined in `DEFAULT_CONFIG` at the top of `app.py`.
