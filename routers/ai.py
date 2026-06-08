"""
routers/ai.py — Groq AI endpoints: NL→rule, feedback letters, data questions,
                flag explanations, QC executive summary
"""

import asyncio
import json
from typing import Any, Dict, List

import requests
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from job_store import file_store
from core.loader import DataLoader

router = APIRouter()

GROQ_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"

AVAILABLE_MODELS = [
    "llama-3.1-8b-instant",
    "llama-3.3-70b-versatile",
    "llama3-8b-8192",
    "gemma2-9b-it",
]


def _call_groq(
    prompt: str,
    api_key: str,
    model: str = "llama-3.1-8b-instant",
    temperature: float = 0.3,
    max_tokens: int = 600,
) -> str:
    if model not in AVAILABLE_MODELS:
        model = "llama-3.1-8b-instant"
    r = requests.post(
        GROQ_ENDPOINT,
        json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": max_tokens,
        },
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        timeout=45,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()


async def _groq(prompt: str, api_key: str, model: str = "llama-3.1-8b-instant",
                temperature: float = 0.3, max_tokens: int = 600) -> str:
    """Non-blocking wrapper — runs _call_groq in a thread-pool executor."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None, lambda: _call_groq(prompt, api_key, model, temperature, max_tokens)
    )


# ── Schemas ────────────────────────────────────────────────────────────────────

class NLToRuleRequest(BaseModel):
    description: str
    groq_api_key: str
    model: str = "llama-3.1-8b-instant"


class FeedbackLetterRequest(BaseModel):
    interviewer_id: str
    stats: Dict[str, Any]
    groq_api_key: str
    model: str = "llama-3.1-8b-instant"


class DataQuestionRequest(BaseModel):
    file_id: str
    question: str
    groq_api_key: str
    model: str = "llama-3.1-8b-instant"


class ExplainFlagsRequest(BaseModel):
    check_name: str
    severity: str
    flag_count: int
    total_rows: int
    sample_rows: List[Dict[str, Any]]
    metadata: Dict[str, Any]
    groq_api_key: str
    model: str = "llama-3.1-8b-instant"


class QCSummaryRequest(BaseModel):
    total_flags: int
    total_rows: int
    checks: List[Dict[str, Any]]   # [{check_name, severity, flag_count}, ...]
    groq_api_key: str
    model: str = "llama-3.1-8b-instant"


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post("/ai/nl-to-rule")
async def nl_to_rule(req: NLToRuleRequest):
    if not req.groq_api_key:
        raise HTTPException(status_code=400, detail={"error": "Groq API key required"})

    prompt = (
        "Convert this survey QC rule description to a JSON configuration object.\n\n"
        "Choose the best rule type and return ONLY valid JSON (no markdown, no explanation):\n\n"
        "Rule types:\n"
        '1. range_rule: {"type":"range","column":"col_name","min":0,"max":100}\n'
        '2. logic_rule: {"type":"logic","description":"...","if_conditions":[{"column":"col","operator":"==","value":"val"}],"then_conditions":[{"column":"col","operator":"is_null"}]}\n'
        "   Operators: >, <, >=, <=, ==, !=, is_null, not_null, in_list, not_in_list\n"
        '3. duration_rule: {"type":"duration","column":"col_name","min_expected":5,"max_expected":120}\n'
        '4. pattern_rule: {"type":"pattern","column":"col_name","pattern":"regex_here","description":"..."}\n\n'
        f"Description: {req.description}"
    )

    try:
        raw = await _groq(prompt, req.groq_api_key, req.model)
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start < 0 or end <= start:
            raise ValueError("No JSON found in Groq response")
        rule_json = json.loads(raw[start:end])
        return {"rule": rule_json, "raw": raw}
    except requests.HTTPError as exc:
        raise HTTPException(status_code=502, detail={"error": f"Groq API error: {exc}"})
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"error": str(exc)})


@router.post("/ai/feedback-letter")
async def feedback_letter(req: FeedbackLetterRequest):
    if not req.groq_api_key:
        raise HTTPException(status_code=400, detail={"error": "Groq API key required"})

    stats = req.stats
    issue_lines = []
    for col, label in [
        ("fabrication_flags",    "Fabrication / sequential-ID flags"),
        ("duration_flags",       "Duration anomaly flags"),
        ("straightlining_flags", "Straightlining flags"),
        ("productivity_flags",   "Productivity outlier flags"),
        ("verbatim_flags",       "Verbatim quality flags"),
    ]:
        n = int(stats.get(col, 0))
        total = max(int(stats.get("total_interviews", 1)), 1)
        if n > 0:
            issue_lines.append(f"  • {label}: {n} ({round(n / total * 100, 1)}%)")

    issues_text = "\n".join(issue_lines) if issue_lines else "  • No specific flags — general review."
    context = (
        f"Interviewer ID: {req.interviewer_id}\n"
        f"Risk Score: {stats.get('risk_score', 0)}/100 ({stats.get('risk_level', 'LOW')})\n"
        f"Total interviews: {int(stats.get('total_interviews', 0))}\n"
        f"Total flags: {int(stats.get('total_flags', 0))} "
        f"({float(stats.get('flag_rate_pct', 0)):.1f}% flag rate)\n\n"
        f"Issues identified:\n{issues_text}"
    )

    prompt = (
        "You are a senior survey QC manager writing a formal but constructive feedback letter "
        "to a field interviewer based on automated QC findings.\n\n"
        f"QC Summary:\n{context}\n\n"
        "Write a professional letter structured as:\n"
        "1. Opening — acknowledge their effort and explain the purpose of the review\n"
        "2. Findings — describe each flagged issue clearly and what it indicates\n"
        "3. Standards — briefly state what good quality looks like\n"
        "4. Required actions — specific, actionable steps to improve\n"
        "5. Next steps — what happens next (re-check, retraining, etc.)\n"
        "6. Closing — supportive, professional tone\n\n"
        f"Address it: 'Dear Interviewer {req.interviewer_id},'\n"
        "Write the complete letter. Plain business English, no bullet points in the letter body."
    )

    try:
        letter = await _groq(prompt, req.groq_api_key, req.model, temperature=0.35, max_tokens=900)
        return {"letter": letter}
    except requests.HTTPError as exc:
        raise HTTPException(status_code=502, detail={"error": f"Groq API error: {exc}"})
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"error": str(exc)})


@router.post("/ai/data-question")
async def data_question(req: DataQuestionRequest):
    if not req.groq_api_key:
        raise HTTPException(status_code=400, detail={"error": "Groq API key required"})

    file_path = await file_store.get(req.file_id)
    if file_path is None or not file_path.exists():
        raise HTTPException(status_code=404, detail={"error": "file_id not found"})

    def _load_summary(path):
        loader = DataLoader()
        df = loader.load(str(path))
        numeric = df.select_dtypes(include="number")
        desc = numeric.describe().to_string() if not numeric.empty else "No numeric columns"
        shape = f"{df.shape[0]} rows × {df.shape[1]} columns"
        cols = ", ".join(df.columns[:30].tolist())
        missing = df.isnull().sum()[df.isnull().sum() > 0].to_string() or "None"
        return shape, cols, desc, missing

    loop = asyncio.get_running_loop()
    shape, cols, desc, missing = await loop.run_in_executor(None, _load_summary, file_path)

    prompt = (
        f"You are a data analyst. A user uploaded a survey dataset with the following summary:\n\n"
        f"Shape: {shape}\nColumns: {cols}\n\nNumeric summary:\n{desc}\n\n"
        f"Missing values:\n{missing}\n\n"
        f"User question: {req.question}\n\n"
        "Answer concisely and factually based only on the data summary above. "
        "If the question requires specific data not in the summary, say so."
    )

    try:
        answer = await _groq(prompt, req.groq_api_key, req.model, temperature=0.2, max_tokens=500)
        return {"answer": answer}
    except requests.HTTPError as exc:
        raise HTTPException(status_code=502, detail={"error": f"Groq API error: {exc}"})
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"error": str(exc)})


@router.post("/ai/explain-flags")
async def explain_flags(req: ExplainFlagsRequest):
    """Generate a plain-English explanation of flagged rows for a single QC check."""
    if not req.groq_api_key:
        raise HTTPException(status_code=400, detail={"error": "Groq API key required"})

    flag_pct = round(req.flag_count / max(req.total_rows, 1) * 100, 1)
    sample_text = ""
    if req.sample_rows:
        cols = list(req.sample_rows[0].keys())[:8]
        header = " | ".join(cols)
        rows = "\n".join(
            " | ".join(str(r.get(c, ""))[:30] for c in cols)
            for r in req.sample_rows[:5]
        )
        sample_text = f"\nSample flagged rows ({min(5, len(req.sample_rows))} of {req.flag_count}):\n{header}\n{rows}"

    meta_text = ""
    if req.metadata:
        safe_meta = {k: v for k, v in req.metadata.items()
                     if not isinstance(v, (list, dict)) and k != "status"}
        if safe_meta:
            meta_text = "\nCheck metadata: " + ", ".join(f"{k}={v}" for k, v in safe_meta.items())

    prompt = (
        "You are a survey QC analyst. Explain in plain English what the following QC check found "
        "and what action a data manager should take.\n\n"
        f"Check: {req.check_name.replace('_', ' ')}\n"
        f"Severity: {req.severity}\n"
        f"Flags: {req.flag_count} out of {req.total_rows} records ({flag_pct}%)"
        f"{meta_text}"
        f"{sample_text}\n\n"
        "Write 2-3 short paragraphs:\n"
        "1. What this check detected and why it matters for data quality\n"
        "2. What the flagged data likely indicates (patterns, root causes)\n"
        "3. Recommended next steps for the data manager\n\n"
        "Be specific, practical, and concise. No bullet points. Plain paragraph form."
    )

    try:
        explanation = await _groq(prompt, req.groq_api_key, req.model, temperature=0.25, max_tokens=450)
        return {"explanation": explanation}
    except requests.HTTPError as exc:
        raise HTTPException(status_code=502, detail={"error": f"Groq API error: {exc}"})
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"error": str(exc)})


@router.post("/ai/qc-summary")
async def qc_summary(req: QCSummaryRequest):
    """Generate an executive-level QC summary narrative from full check results."""
    if not req.groq_api_key:
        raise HTTPException(status_code=400, detail={"error": "Groq API key required"})

    flag_rate = round(req.total_flags / max(req.total_rows, 1) * 100, 1)

    critical = [c for c in req.checks if c.get("severity") == "critical" and c.get("flag_count", 0) > 0]
    warnings  = [c for c in req.checks if c.get("severity") == "warning"  and c.get("flag_count", 0) > 0]
    info      = [c for c in req.checks if c.get("severity") == "info"     and c.get("flag_count", 0) > 0]

    def _fmt(checks_list):
        return ", ".join(
            f"{c['check_name'].replace('_', ' ')} ({c['flag_count']} flags)"
            for c in checks_list[:6]
        ) or "none"

    prompt = (
        "You are a senior survey quality control manager writing an executive summary of an automated QC report.\n\n"
        f"Dataset: {req.total_rows:,} records, {len(req.checks)} checks run\n"
        f"Total flags: {req.total_flags:,} ({flag_rate}% of records)\n\n"
        f"Critical issues: {_fmt(critical)}\n"
        f"Warnings: {_fmt(warnings)}\n"
        f"Info: {_fmt(info)}\n\n"
        "Write an executive QC summary in 3 paragraphs:\n"
        "1. Overall data quality verdict — is this dataset fit for analysis?\n"
        "2. The most important findings that require immediate attention\n"
        "3. Recommended remediation steps before data sign-off\n\n"
        "Write for a non-technical research director. Plain English. Decisive tone. No bullet points."
    )

    try:
        summary = await _groq(prompt, req.groq_api_key, req.model, temperature=0.25, max_tokens=500)
        return {"summary": summary}
    except requests.HTTPError as exc:
        raise HTTPException(status_code=502, detail={"error": f"Groq API error: {exc}"})
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"error": str(exc)})
