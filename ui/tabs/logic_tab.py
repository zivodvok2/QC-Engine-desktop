"""
ui/tabs/logic_tab.py — Logic Checks tab

Interactive rule builder: IF column meets condition → THEN column must meet condition.
AI-powered: describe a rule in plain English and Groq converts it automatically.
"""

import json
import streamlit as st
import pandas as pd
import requests
from ui.components.drag_drop import drop_zone

OPERATORS = [">", "<", ">=", "<=", "==", "!=", "is_null", "not_null",
             "is_numeric", "is_string", "in_list", "not_in_list"]


def _nl_to_rule(description: str, columns: list) -> dict | None:
    """Convert a natural-language rule description to a logic rule dict via Groq."""
    try:
        from checks.verbatim_checks import _get_api_key
        api_key = _get_api_key()
    except Exception:
        return None
    if not api_key:
        return None

    cols_sample = columns[:40]
    prompt = (
        f"Convert this survey QC rule to JSON.\n\n"
        f"Rule: \"{description}\"\n\n"
        f"Available columns: {cols_sample}\n\n"
        f"Return ONLY a JSON object — no explanation, no markdown:\n"
        f'{{"description": "...", '
        f'"if_conditions": [{{"column": "col_name", "operator": "op", "value": "val"}}], '
        f'"then_conditions": [{{"column": "col_name", "operator": "op", "value": "val"}}]}}\n\n'
        f"Operators: >, <, >=, <=, ==, !=, is_null, not_null, in_list, not_in_list\n"
        f"Omit 'value' for is_null / not_null. Use column names from the list above."
    )
    try:
        r = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            json={
                "model": "llama-3.1-8b-instant",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
                "max_tokens": 500,
            },
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            timeout=15,
        )
        r.raise_for_status()
        raw = r.json()["choices"][0]["message"]["content"].strip()
        start = raw.find("{")
        end   = raw.rfind("}") + 1
        if start == -1 or end == 0:
            return None
        return json.loads(raw[start:end])
    except Exception:
        return None

OPERATOR_HELP = {
    ">": "Greater than",       "<": "Less than",
    ">=": "Greater or equal",  "<=": "Less or equal",
    "==": "Equals",            "!=": "Not equals",
    "is_null":     "Is empty / missing",
    "not_null":    "Is not empty",
    "is_numeric":  "Is a number",
    "is_string":   "Is text",
    "in_list":     "Value is in list (comma-sep)",
    "not_in_list": "Value not in list",
}


def render(df: pd.DataFrame, results: list):
    st.markdown(
        "<p style='color:var(--ds-text2);font-size:13px;margin-bottom:16px;'>"
        "Build conditional rules: <em>if column A meets a condition, "
        "column B must meet another condition.</em></p>",
        unsafe_allow_html=True,
    )

    all_cols = df.columns.tolist()

    # ── AI Rule Builder ───────────────────────────────────────────────────────
    with st.expander("✨ Describe a rule in plain English (AI)", expanded=False):
        st.markdown(
            "<div style='font-size:12px;color:var(--ds-text2);margin-bottom:8px;'>"
            "Type your rule in plain English and Groq will convert it to the logic format automatically.</div>",
            unsafe_allow_html=True,
        )
        nl_input = st.text_area(
            "Rule description",
            placeholder='e.g. "If age is under 18 then marital status should be empty"\n'
                        '"If consent is No then all subsequent questions should be blank"',
            key="lc_nl_input",
            label_visibility="collapsed",
            height=80,
        )
        if st.button("✨ Convert with Groq", key="lc_nl_convert"):
            if not nl_input.strip():
                st.warning("Enter a rule description first.")
            else:
                with st.spinner("Converting…"):
                    rule = _nl_to_rule(nl_input.strip(), all_cols)
                if rule and "if_conditions" in rule and "then_conditions" in rule:
                    st.session_state.custom_logic_rules.append(rule)
                    st.success(f"Rule added: {rule.get('description', nl_input)}")
                    st.rerun()
                else:
                    st.error(
                        "Could not parse a rule from that description. "
                        "Try being more specific, or use the manual builder below. "
                        "(Groq API key required — check ⚙️ Settings)"
                    )

    # ── Rule builder ─────────────────────────────────────────────────────────
    with st.expander("➕ Add new logic rule", expanded=True):
        rule_desc = st.text_input(
            "Rule description",
            placeholder="e.g. Respondents under 18 should not be married",
            key="lc_desc",
        )

        st.markdown(
            "<div style='font-size:11px;letter-spacing:0.08em;text-transform:uppercase;"
            "color:var(--ds-text2);margin:12px 0 4px;'>IF conditions "
            "<span style='font-weight:400;text-transform:none;'>(all must be true)</span></div>",
            unsafe_allow_html=True,
        )

        ic1, ic2, ic3 = st.columns([3, 2, 2])
        with ic1:
            if_col = drop_zone("IF column", "lc_if_col",
                               options=all_cols, multi=False,
                               help_text="Column to test the IF condition on")
        with ic2:
            if_op = st.selectbox(
                "Operator", OPERATORS, key="lc_if_op",
                format_func=lambda x: f"{x}  — {OPERATOR_HELP.get(x, '')}",
                label_visibility="collapsed",
            )
        with ic3:
            if_val = st.text_input(
                "Value", key="lc_if_val",
                placeholder="e.g. 18  or  Yes, No",
                label_visibility="collapsed",
            )

        st.markdown(
            "<div style='font-size:11px;letter-spacing:0.08em;text-transform:uppercase;"
            "color:var(--ds-text2);margin:12px 0 4px;'>THEN conditions "
            "<span style='font-weight:400;text-transform:none;'>"
            "(select multiple columns to check several at once)</span></div>",
            unsafe_allow_html=True,
        )

        tc1, tc2, tc3 = st.columns([3, 2, 2])
        with tc1:
            then_col = drop_zone("THEN column(s)", "lc_then_col",
                                 options=all_cols, multi=True,
                                 help_text="Column(s) that must meet the THEN condition")
        with tc2:
            then_op = st.selectbox(
                "Then operator", OPERATORS, key="lc_then_op",
                format_func=lambda x: f"{x}  — {OPERATOR_HELP.get(x, '')}",
                label_visibility="collapsed",
            )
        with tc3:
            then_val = st.text_input(
                "Then value", key="lc_then_val",
                placeholder="optional",
                label_visibility="collapsed",
            )

        if st.button("✚ Add Rule", type="primary"):
            if_col_list   = if_col   # already a list from drop_zone
            then_col_list = then_col

            if if_col_list and then_col_list:
                rule = {
                    "description": rule_desc or (
                        f"If {', '.join(if_col_list)} {if_op} → "
                        f"{', '.join(then_col_list)} {then_op}"
                    ),
                    "if_conditions": [
                        {"column": ic, "operator": if_op,
                         "value": if_val.strip() or None}
                        for ic in if_col_list
                    ],
                    "then_conditions": [
                        {"column": tc, "operator": then_op,
                         "value": then_val.strip() or None}
                        for tc in then_col_list
                    ],
                }
                st.session_state.custom_logic_rules.append(rule)
                st.success(f"Rule added: {rule['description']}")
                st.rerun()
            else:
                st.warning("Select at least one IF column and one THEN column.")

    # ── Active rules list ─────────────────────────────────────────────────────
    if st.session_state.custom_logic_rules:
        st.markdown("#### Active logic rules")
        for i, rule in enumerate(st.session_state.custom_logic_rules):
            col_desc, col_del = st.columns([6, 1])
            with col_desc:
                if_summary   = " AND ".join(
                    f"{c['column']} {c['operator']} {c.get('value', '')}"
                    for c in rule.get("if_conditions", [])
                )
                then_summary = " · ".join(
                    f"{c['column']} {c['operator']} {c.get('value', '')}"
                    for c in rule.get("then_conditions", [])
                )
                st.markdown(
                    f"<div style='background:var(--ds-surface);border:1px solid var(--ds-border);"
                    f"border-left:3px solid var(--ds-accent);border-radius:6px;padding:10px 14px;"
                    f"margin-bottom:6px;'>"
                    f"<div style='font-size:12px;font-weight:500;color:var(--ds-text);margin-bottom:4px;'>"
                    f"{rule.get('description', '')}</div>"
                    f"<div style='font-size:11px;color:var(--ds-text2);'>"
                    f"<span style='color:var(--ds-info);'>IF</span> {if_summary} &nbsp;→&nbsp; "
                    f"<span style='color:var(--ds-warning);'>THEN</span> {then_summary}</div>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
            with col_del:
                if st.button("✕", key=f"del_lr_{i}"):
                    st.session_state.custom_logic_rules.pop(i)
                    st.rerun()
    else:
        st.info("No logic rules added yet. Use the builder above to create your first rule.")

    # ── Results ───────────────────────────────────────────────────────────────
    logic_results = [r for r in results if r.check_name == "logic_check"]
    if not logic_results:
        if st.session_state.custom_logic_rules:
            st.info("Rules are set. Click **↺ Rerun QC** in the sidebar to check them.")
        return

    r = logic_results[0]
    st.divider()
    st.markdown(f"#### Results — {r.flag_count:,} violations found")

    if r.flag_count == 0:
        st.success("No violations found for the current rules.")
        return

    show = [c for c in r.flagged_rows.columns if not c.startswith("_")]
    if "_logic_rule" in r.flagged_rows.columns:
        for rule_name, group in r.flagged_rows.groupby("_logic_rule"):
            with st.expander(f"{rule_name} — {len(group)} violations"):
                st.dataframe(group[show].head(100), width="stretch", hide_index=True)
    else:
        st.dataframe(r.flagged_rows[show].head(100), width="stretch", hide_index=True)
