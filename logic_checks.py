"""
logic_checks.py - Conditional / skip-logic consistency checks
"""

import pandas as pd
from core.validator import BaseCheck, CheckResult
from core.utils import setup_logger

logger = setup_logger("logic_checks")


class LogicCheck(BaseCheck):
    """
    Validates conditional logic rules (skip patterns).
    Example: If Q5 == "No", then Q6 must be null.
    """
    name = "logic_check"
    issue_type = "logic_violation"
    severity = "critical"

    def __init__(self, rules: list):
        """
        rules: list of dicts:
        {
            "description": "If Q5=No, Q6 must be null",
            "if_column": "Q5",
            "if_value": "No",
            "then_column": "Q6",
            "then_condition": "must_be_null"   # or "must_not_be_null"
        }
        """
        self.rules = rules

    def run(self, df: pd.DataFrame) -> CheckResult:
        all_flagged = []

        for rule in self.rules:
            if_col = rule.get("if_column")
            if_val = rule.get("if_value")
            then_col = rule.get("then_column")
            condition = rule.get("then_condition")
            description = rule.get("description", f"{if_col}={if_val} → {then_col} {condition}")

            if if_col not in df.columns or then_col not in df.columns:
                logger.warning(f"Logic rule skipped (column not found): {description}")
                continue

            trigger_mask = df[if_col] == if_val

            if condition == "must_be_null":
                violation_mask = trigger_mask & df[then_col].notna()
            elif condition == "must_not_be_null":
                violation_mask = trigger_mask & df[then_col].isna()
            else:
                logger.warning(f"Unknown condition '{condition}' in rule: {description}")
                continue

            flagged = df[violation_mask].copy()
            flagged["_logic_rule"] = description
            flagged["_logic_violation"] = f"{then_col} should be {condition}"

            logger.info(f"[{self.name}] Rule '{description}': {len(flagged)} violations.")
            all_flagged.append(flagged)

        combined = pd.concat(all_flagged, ignore_index=True) if all_flagged else df.iloc[0:0]
        return self._make_result(combined, {"rules_applied": len(self.rules)})


class DuplicateCheck(BaseCheck):
    """
    Flags duplicate records based on specified key columns.
    """
    name = "duplicate_check"
    issue_type = "duplicate_record"
    severity = "critical"

    def __init__(self, subset: list = None):
        """subset: columns to use for duplicate detection (None = all columns)"""
        self.subset = subset

    def run(self, df: pd.DataFrame) -> CheckResult:
        subset = [c for c in self.subset if c in df.columns] if self.subset else None
        dupes = df[df.duplicated(subset=subset, keep=False)].copy()
        dupes["_dupe_key"] = str(subset)

        metadata = {
            "subset": subset,
            "duplicate_count": len(dupes),
            "unique_duplicate_groups": df.duplicated(subset=subset, keep="first").sum(),
        }
        logger.info(f"[{self.name}] {len(dupes)} duplicate rows found.")
        return self._make_result(dupes, metadata)
