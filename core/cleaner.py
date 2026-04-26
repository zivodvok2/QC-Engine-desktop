"""
cleaner.py - Data normalization and type coercion
"""

import pandas as pd
from core.utils import setup_logger

logger = setup_logger("cleaner")


class DataCleaner:
    """
    Standardizes raw survey data before validation.
    Does NOT drop data — flags issues instead where possible.
    """

    def clean(self, df: pd.DataFrame) -> pd.DataFrame:
        """Run all cleaning steps and return cleaned DataFrame."""
        logger.info("Starting data cleaning...")
        df = df.copy()
        df = self._normalize_nulls(df)
        df = self._strip_whitespace(df)
        df = self._normalize_booleans(df)
        df = self._normalize_categories(df)
        logger.info("Data cleaning complete.")
        return df

    def _normalize_nulls(self, df: pd.DataFrame) -> pd.DataFrame:
        """Replace common null placeholders with NaN."""
        null_values = ["", "N/A", "n/a", "NA", "na", "None", "none", "NULL", "null", "-", "--", "999", "9999"]
        df.replace(null_values, pd.NA, inplace=True)
        logger.debug("Null normalization complete.")
        return df

    def _strip_whitespace(self, df: pd.DataFrame) -> pd.DataFrame:
        """Strip leading/trailing whitespace from string columns."""
        for col in df.select_dtypes(include="object").columns:
            try:
                df[col] = df[col].apply(lambda x: x.strip() if isinstance(x, str) else x)
            except Exception:
                pass
        return df

    def _normalize_booleans(self, df: pd.DataFrame) -> pd.DataFrame:
        """Convert common boolean strings to Python booleans."""
        bool_map = {
            "yes": True, "no": False,
            "true": True, "false": False,
            "1": True, "0": False,
            "y": True, "n": False,
        }
        for col in df.select_dtypes(include="object").columns:
            try:
                non_null = df[col].dropna()
                # Only process columns where every non-null value is a plain string
                if not all(isinstance(v, str) for v in non_null):
                    continue
                sample = non_null.str.lower().unique()
                if all(v in bool_map for v in sample):
                    df[col] = df[col].apply(
                        lambda x: bool_map[x.lower()] if isinstance(x, str) else x
                    )
                    logger.debug(f"Converted column '{col}' to boolean.")
            except Exception:
                pass
        return df

    def _normalize_categories(self, df: pd.DataFrame) -> pd.DataFrame:
        """Title-case string columns with low cardinality (likely categories)."""
        for col in df.select_dtypes(include="object").columns:
            try:
                if df[col].nunique() <= 30:
                    df[col] = df[col].apply(lambda x: x.title() if isinstance(x, str) else x)
            except Exception:
                pass
        return df

    def coerce_types(self, df: pd.DataFrame, type_map: dict) -> pd.DataFrame:
        """
        Coerce specified columns to given types.
        type_map: {"column_name": "int" | "float" | "str" | "datetime"}
        """
        for col, dtype in type_map.items():
            if col not in df.columns:
                logger.warning(f"Column '{col}' not found for type coercion.")
                continue
            try:
                if dtype == "datetime":
                    df[col] = pd.to_datetime(df[col], errors="coerce")
                elif dtype == "int":
                    df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
                elif dtype == "float":
                    df[col] = pd.to_numeric(df[col], errors="coerce")
                elif dtype == "str":
                    df[col] = df[col].astype(str)
            except Exception as e:
                logger.error(f"Failed to coerce '{col}' to {dtype}: {e}")
        return df
