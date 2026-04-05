"""
ui/components/drag_drop.py — Column selector widgets

drop_zone() is the primary API. When `options` are provided it renders a
st.multiselect (multi=True) or st.selectbox (multi=False) so users can
pick columns from a proper dropdown. This replaces the previous HTML5
drag-and-drop approach which couldn't trigger Streamlit's React state.
"""

import streamlit as st
from typing import Optional


def drop_zone(
    label: str,
    key: str,
    options: list = None,
    default=None,
    help_text: str = "",
    multi: bool = True,
) -> list:
    """
    Column selector widget. Returns a list of selected column names.

    Args:
        label:     Widget label
        key:       Unique Streamlit widget key
        options:   List of available column names. When provided, renders a
                   multiselect/selectbox. When None, falls back to text input.
        default:   Default selection (list for multi, str for single)
        help_text: Tooltip help text
        multi:     If True, allow multiple selections (multiselect).
                   If False, single selection (selectbox).
    """
    if options is not None:
        if multi:
            default_list = [d for d in (default or []) if d in options]
            selected = st.multiselect(
                label,
                options=options,
                default=default_list,
                key=key,
                help=help_text or "Select one or more columns",
            )
            return selected
        else:
            choices = ["— select —"] + list(options)
            default_idx = 0
            if default and default in options:
                default_idx = options.index(default) + 1
            val = st.selectbox(
                label,
                options=choices,
                index=default_idx,
                key=key,
                help=help_text or "Select a column",
            )
            return [val] if val and val != "— select —" else []
    else:
        # Fallback: plain text input for backward compatibility
        placeholder = "e.g. Q1, Q2, Q3" if multi else "e.g. column_name"
        default_str = (
            ", ".join(default) if isinstance(default, list)
            else (str(default) if default else "")
        )
        raw = st.text_input(
            label,
            value=default_str,
            key=key,
            placeholder=placeholder,
            help=help_text or (
                "Comma-separated column names" if multi else "Column name"
            ),
        )
        cols = [c.strip() for c in raw.split(",") if c.strip()]
        return cols[:1] if not multi else cols


def inject_drag_drop_js() -> None:
    """No-op — kept for backward compatibility."""
    pass


def column_panel(df_columns: list, key_prefix: str = "col_panel") -> None:
    """No-op — kept for backward compatibility."""
    pass


def column_multiselect(
    label: str,
    df_columns: list,
    key: str,
    default: Optional[list] = None,
    help_text: str = "",
) -> list:
    """Styled multiselect for all available columns."""
    return st.multiselect(
        label,
        options=df_columns,
        default=default or [],
        key=key,
        help=help_text,
    )
