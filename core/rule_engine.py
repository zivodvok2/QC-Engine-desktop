"""
rule_engine.py - Config-driven orchestrator for all validation checks
"""

import pandas as pd
from typing import List
from core.validator import BaseCheck, CheckResult
from core.utils import setup_logger, load_json_config

from checks.missing_checks import MissingValueCheck, HighMissingColumnCheck
from checks.range_checks import RangeCheck, DurationCheck
from checks.logic_checks import LogicCheck, DuplicateCheck
from checks.pattern_checks import PatternCheck, AnomalyCheck

logger = setup_logger("rule_engine")


class RuleEngine:
    """
    Loads rules from config and executes the appropriate checks.
    Collects all CheckResult objects and exposes them for reporting.
    """

    def __init__(self, config_path: str = "config/rules.json", config: dict = None):
        if config is not None:
            self.config = config
        else:
            self.config = load_json_config(config_path)
        self.checks: List[BaseCheck] = []
        self.results: List[CheckResult] = []
        self._build_checks()

    def _build_checks(self):
        """Instantiate checks from config."""
        cfg = self.config

        # Missing value checks
        threshold = cfg.get("missing_threshold")
        if threshold is not None:
            self.checks.append(MissingValueCheck(threshold=threshold))
            self.checks.append(HighMissingColumnCheck(threshold=threshold))

        # Range checks
        range_rules = cfg.get("range_rules", [])
        if range_rules:
            self.checks.append(RangeCheck(rules=range_rules))

        # Logic / skip-pattern checks
        logic_rules = cfg.get("logic_rules", [])
        if logic_rules:
            self.checks.append(LogicCheck(rules=logic_rules))

        # Pattern / regex checks
        pattern_rules = cfg.get("pattern_rules", [])
        if pattern_rules:
            self.checks.append(PatternCheck(rules=pattern_rules))

        # Duplicate check
        dup_cfg = cfg.get("duplicate_check", {})
        if dup_cfg.get("enabled", False):
            subset = dup_cfg.get("subset_columns") or None
            self.checks.append(DuplicateCheck(subset=subset))

        # Duration check
        dur_cfg = cfg.get("interview_duration", {})
        if dur_cfg.get("enabled", False):
            self.checks.append(DurationCheck(
                column=dur_cfg["column"],
                min_minutes=dur_cfg.get("min_expected", 5),
                max_minutes=dur_cfg.get("max_expected", 120),
            ))

        logger.info(f"Rule engine initialized with {len(self.checks)} checks.")

    def add_check(self, check: BaseCheck):
        """Register a custom check at runtime."""
        self.checks.append(check)
        logger.info(f"Custom check registered: {check.name}")

    def run(self, df: pd.DataFrame) -> List[CheckResult]:
        """
        Execute all registered checks against the DataFrame.
        Returns list of CheckResult objects.
        """
        self.results = []
        logger.info(f"Running {len(self.checks)} checks on {len(df)} rows...")

        for check in self.checks:
            try:
                result = check.run(df)
                self.results.append(result)
                logger.info(f"✔ {check.name}: {result.flag_count} issues flagged.")
            except Exception as e:
                logger.error(f"✘ {check.name} failed: {e}", exc_info=True)

        total_flags = sum(r.flag_count for r in self.results)
        logger.info(f"QC complete. Total flags: {total_flags}")
        return self.results

    def get_summary(self) -> pd.DataFrame:
        """Return a summary DataFrame of all check results."""
        return pd.DataFrame([r.summary() for r in self.results])
