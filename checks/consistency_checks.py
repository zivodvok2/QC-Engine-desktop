"""
consistency_checks.py — Near-duplicate and response consistency detection

1. NearDuplicateCheck — same identifier value across different respondent IDs,
                        or suspicious demographic combo repetition
"""

import pandas as pd
import numpy as np
from core.validator import BaseCheck, CheckResult
from core.utils import setup_logger

logger = setup_logger("consistency_checks")


class NearDuplicateCheck(BaseCheck):
    """
    Detects near-duplicate records that exact-match duplicate checks miss.

    A) Shared unique identifier — same phone / email / ID value appearing under
       multiple respondent IDs (fabrication where the interviewer reused a contact)

    B) Repeated demographic combination — same age + gender + location combo
       appearing more than max_combo_count times (suspiciously cloned interviews)

    Config:
    {
        "id_column": "respondent_id",
        "unique_columns": ["phone", "email"],
        "combo_columns": ["age", "gender", "location"],
        "max_combo_count": 3
    }
    """
    name = "near_duplicate_check"
    issue_type = "near_duplicate"
    severity = "warning"

    def __init__(
        self,
        id_column: str = None,
        unique_columns: list = None,
        combo_columns: list = None,
        max_combo_count: int = 3,
    ):
        self.id_column = id_column
        self.unique_columns = unique_columns or []
        self.combo_columns = combo_columns or []
        self.max_combo_count = max_combo_count

    def run(self, df: pd.DataFrame) -> CheckResult:
        all_flagged = []
        metadata = {}

        # ── A) Shared unique identifier ───────────────────────────────────────
        for col in self.unique_columns:
            if col not in df.columns:
                logger.warning(f"[{self.name}] Column '{col}' not found.")
                continue

            valid = df[df[col].notna() & (df[col].astype(str).str.strip() != "")]

            if self.id_column and self.id_column in df.columns:
                id_counts = valid.groupby(col)[self.id_column].nunique()
                shared = id_counts[id_counts > 1]
                if not shared.empty:
                    flagged = df[df[col].isin(shared.index)].copy()
                    flagged["_near_dup_type"] = f"shared_{col}"
                    flagged["_near_dup_col"] = col
                    flagged["_shared_across_n_ids"] = (
                        df[col].map(shared).astype("Int64")
                    )
                    all_flagged.append(flagged)
                    metadata[f"shared_{col}_values"] = int(len(shared))
                    logger.info(
                        f"[{self.name}] {len(shared)} '{col}' values shared "
                        f"across different respondent IDs."
                    )
            else:
                dupes = df[df[col].duplicated(keep=False) & df[col].notna()].copy()
                if not dupes.empty:
                    dupes["_near_dup_type"] = f"duplicate_{col}"
                    dupes["_near_dup_col"] = col
                    all_flagged.append(dupes)
                    metadata[f"duplicate_{col}"] = len(dupes)

        # ── B) Repeated demographic combination ───────────────────────────────
        if len(self.combo_columns) >= 2:
            cols = [c for c in self.combo_columns if c in df.columns]
            if len(cols) >= 2:
                try:
                    combo_key = (
                        df[cols].fillna("__NA__").astype(str).apply("|".join, axis=1)
                    )
                    combo_counts = combo_key.value_counts()
                    suspicious_keys = combo_counts[
                        combo_counts > self.max_combo_count
                    ].index
                    if len(suspicious_keys):
                        flagged = df[combo_key.isin(suspicious_keys)].copy()
                        flagged["_near_dup_type"] = "repeated_demographic_combo"
                        flagged["_combo_count"] = (
                            combo_key.map(combo_counts).astype(int)
                        )
                        flagged["_combo_columns"] = ", ".join(cols)
                        all_flagged.append(flagged)
                        metadata["repeated_combos"] = int(len(suspicious_keys))
                        metadata["combo_columns"] = cols
                        metadata["max_allowed"] = self.max_combo_count
                        logger.info(
                            f"[{self.name}] {len(suspicious_keys)} demographic combos "
                            f"exceed {self.max_combo_count}x threshold."
                        )
                except Exception as e:
                    logger.warning(f"[{self.name}] Combo check failed: {e}")

        if all_flagged:
            combined = pd.concat(all_flagged, ignore_index=True).drop_duplicates()
        else:
            combined = df.iloc[0:0]

        return self._make_result(combined, metadata)
