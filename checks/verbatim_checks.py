"""
verbatim_checks.py — Verbatim response quality checks via Groq API

Key resolution order:
  1. GROQ_API_KEY environment variable  (server / built-in key)
  2. st.session_state.ds_groq_api_key   (user's personal key)

If the server key hits the rate limit (HTTP 429), the check automatically
retries each batch with the user's personal key before giving up.

Responses are batched: batch_size responses scored per API call.
"""

import json
import os
import requests
import pandas as pd
from core.validator import BaseCheck, CheckResult
from core.utils import setup_logger

logger = setup_logger("verbatim_checks")

GROQ_API_URL  = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = "llama-3.1-8b-instant"
DEFAULT_BATCH = 10

AVAILABLE_MODELS = [
    "llama-3.1-8b-instant",
    "llama-3.3-70b-versatile",
    "mixtral-8x7b-32768",
    "gemma2-9b-it",
]


# ── Key helpers ───────────────────────────────────────────────────────────────

def _server_key() -> str:
    return os.environ.get("GROQ_API_KEY", "").strip()


def _user_key() -> str:
    try:
        import streamlit as st
        return st.session_state.get("ds_groq_api_key", "").strip()
    except Exception:
        return ""


def _get_api_key() -> str:
    """Returns server key if set, otherwise user's personal key."""
    return _server_key() or _user_key()


# ── API helpers ───────────────────────────────────────────────────────────────

class _RateLimited(Exception):
    pass


def _validate_api_key(api_key: str, model: str) -> bool:
    """Single cheap call to confirm the key is valid before running batches."""
    try:
        r = requests.post(
            GROQ_API_URL,
            json={"model": model,
                  "messages": [{"role": "user", "content": "hi"}],
                  "max_tokens": 1},
            headers={"Authorization": f"Bearer {api_key}",
                     "Content-Type": "application/json"},
            timeout=10,
        )
        if r.status_code == 401:
            logger.warning("[verbatim_checks] API key invalid (401).")
            return False
        return True
    except Exception as e:
        logger.warning(f"[verbatim_checks] Key validation failed: {e}")
        return False


def _score_batch(texts: list, model: str, api_key: str) -> list:
    """
    Score a batch of verbatim texts in a single Groq API call.
    Raises _RateLimited on HTTP 429.
    Returns a list of score dicts the same length as texts on success,
    or empty dicts on other failures.
    """
    numbered = "\n".join(f'{i + 1}. "{t[:400]}"' for i, t in enumerate(texts))
    prompt = (
        f"You are a survey data quality checker. "
        f"Evaluate these {len(texts)} verbatim survey responses.\n\n"
        f"For each, score 1–5 (5=excellent, 1=poor):\n"
        f"  grammar, coherence, relevance, length_quality\n\n"
        f"Also flag (true/false):\n"
        f"  gibberish, copy_paste, too_short\n\n"
        f"Return ONLY a valid JSON array of exactly {len(texts)} objects in order. "
        f"No explanation, no markdown.\n"
        f'Format: [{{"grammar":4,"coherence":3,"relevance":5,"length_quality":2,'
        f'"gibberish":false,"copy_paste":false,"too_short":false}}, ...]\n\n'
        f"Responses:\n{numbered}\n\nJSON array:"
    )
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type":  "application/json",
    }
    payload = {
        "model":       model,
        "messages":    [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "max_tokens":  150 * len(texts),
    }
    try:
        r = requests.post(GROQ_API_URL, json=payload, headers=headers, timeout=60)
        if r.status_code == 429:
            raise _RateLimited()
        r.raise_for_status()
        raw   = r.json()["choices"][0]["message"]["content"].strip()
        start = raw.find("[")
        end   = raw.rfind("]") + 1
        if start == -1 or end == 0:
            logger.warning("Groq response missing JSON array.")
            return [{} for _ in texts]
        parsed = json.loads(raw[start:end])
        while len(parsed) < len(texts):
            parsed.append({})
        return parsed[: len(texts)]
    except _RateLimited:
        raise
    except Exception as e:
        logger.warning(f"Groq batch call failed: {e}")
        return [{} for _ in texts]


# ── Check class ───────────────────────────────────────────────────────────────

class VerbatimQualityCheck(BaseCheck):
    """
    Evaluates open-ended verbatim responses using Groq API.

    Uses the server key (GROQ_API_KEY env var) if available.
    Falls back to the user's personal key on rate limit (HTTP 429).

    Responses are processed in configurable batches — e.g. batch_size=10
    means 100 responses requires only 10 API calls instead of 100.
    """
    name       = "verbatim_quality_check"
    issue_type = "verbatim_quality"
    severity   = "warning"

    def __init__(
        self,
        verbatim_columns:   list,
        model:              str = DEFAULT_MODEL,
        min_score:          int = 2,
        sample_size:        int = 100,
        batch_size:         int = DEFAULT_BATCH,
        interviewer_column: str = None,
    ):
        self.verbatim_columns   = verbatim_columns
        self.model              = model
        self.min_score          = min_score
        self.sample_size        = sample_size
        self.batch_size         = max(1, batch_size)
        self.interviewer_column = interviewer_column

    def run(self, df: pd.DataFrame) -> CheckResult:
        srv_key  = _server_key()
        usr_key  = _user_key()
        api_key  = srv_key or usr_key

        if not api_key:
            logger.warning(f"[{self.name}] No API key configured.")
            return self._make_result(df.iloc[0:0], {
                "status": "skipped",
                "reason": (
                    "Groq API key not configured. "
                    "Set GROQ_API_KEY env var or enter a personal key in ⚙️ Settings."
                ),
            })

        cols = [c for c in self.verbatim_columns if c in df.columns]
        if not cols:
            return self._make_result(df.iloc[0:0], {
                "status": "skipped",
                "reason": "No verbatim columns found in dataset",
            })

        # Quick validation before running all batches
        if not _validate_api_key(api_key, self.model):
            return self._make_result(df.iloc[0:0], {
                "status": "skipped",
                "reason": "API key is invalid (401). Check your key in ⚙️ Settings.",
            })

        sample = (
            df.sample(min(self.sample_size, len(df)), random_state=42)
            if len(df) > self.sample_size
            else df.copy()
        )

        all_flagged:        list = []
        scores_accumulator: list = []
        used_fallback:      bool = False

        for col in cols:
            rows_to_score = [
                (idx, str(row[col]))
                for idx, row in sample.iterrows()
                if pd.notna(row[col])
                and str(row[col]).strip() not in ("", "nan", "None")
            ]
            if not rows_to_score:
                continue

            n_batches = (len(rows_to_score) + self.batch_size - 1) // self.batch_size
            logger.info(
                f"[{self.name}] Scoring '{col}': "
                f"{len(rows_to_score)} responses in {n_batches} batch(es) "
                f"(key={'server' if api_key == srv_key else 'personal'}, model={self.model})"
            )

            idx_to_score: dict = {}
            for i in range(0, len(rows_to_score), self.batch_size):
                batch = rows_to_score[i : i + self.batch_size]
                idxs  = [r[0] for r in batch]
                texts = [r[1] for r in batch]

                try:
                    scores = _score_batch(texts, self.model, api_key)
                except _RateLimited:
                    # Server key hit the rate limit — try user's personal key
                    if api_key == srv_key and usr_key and usr_key != srv_key:
                        logger.info(
                            f"[{self.name}] Server key rate-limited. "
                            "Falling back to personal key."
                        )
                        api_key     = usr_key
                        used_fallback = True
                        try:
                            scores = _score_batch(texts, self.model, api_key)
                        except _RateLimited:
                            logger.warning(
                                f"[{self.name}] Personal key also rate-limited. "
                                "Stopping batch."
                            )
                            break
                    else:
                        logger.warning(
                            f"[{self.name}] Rate-limited and no fallback key available."
                        )
                        break

                for idx, score in zip(idxs, scores):
                    idx_to_score[idx] = score

            scores_accumulator.extend(idx_to_score.values())

            for idx, scores in idx_to_score.items():
                if not scores:
                    continue
                is_flagged = (
                    any(
                        scores.get(k, 5) < self.min_score
                        for k in ["grammar", "coherence", "relevance", "length_quality"]
                    )
                    or scores.get("gibberish",  False)
                    or scores.get("copy_paste", False)
                    or scores.get("too_short",  False)
                )
                if is_flagged:
                    row_copy = df.loc[[idx]].copy()
                    row_copy["_verbatim_column"]  = col
                    row_copy["_verbatim_text"]    = str(sample.at[idx, col])[:200]
                    row_copy["_grammar_score"]    = scores.get("grammar")
                    row_copy["_coherence_score"]  = scores.get("coherence")
                    row_copy["_relevance_score"]  = scores.get("relevance")
                    row_copy["_length_quality"]   = scores.get("length_quality")
                    row_copy["_gibberish"]        = scores.get("gibberish",  False)
                    row_copy["_copy_paste"]       = scores.get("copy_paste", False)
                    row_copy["_too_short"]        = scores.get("too_short",  False)
                    all_flagged.append(row_copy)

        combined = (
            pd.concat(all_flagged, ignore_index=True) if all_flagged else df.iloc[0:0]
        )

        meta: dict = {
            "model":               self.model,
            "columns_checked":     cols,
            "responses_evaluated": len(scores_accumulator),
            "flagged":             len(combined),
            "status":              "completed",
            "used_fallback_key":   used_fallback,
        }
        if scores_accumulator:
            for dim in ["grammar", "coherence", "relevance", "length_quality"]:
                vals = [s[dim] for s in scores_accumulator if dim in s]
                if vals:
                    meta[f"avg_{dim}"] = round(sum(vals) / len(vals), 2)

        if (
            self.interviewer_column
            and self.interviewer_column in df.columns
            and not combined.empty
        ):
            meta["interviewer_summary"] = (
                combined.groupby(self.interviewer_column)
                .size()
                .reset_index(name="flagged_verbatim_count")
                .to_dict(orient="records")
            )

        logger.info(
            f"[{self.name}] {len(combined)} low-quality responses flagged "
            f"({'used fallback key' if used_fallback else 'server key'})."
        )
        return self._make_result(combined, meta)
