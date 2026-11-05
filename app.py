"""Streamlit Legend Panel for deterministic SEC EDGAR investor screens."""
from __future__ import annotations
import re
from pathlib import Path
import pandas as pd
import streamlit as st
from edgar_financials import DISPLAY, NOT_KNOWN, build_report, graham_checks, number

ROOT = Path(__file__).parent
MEMOS = ROOT / "memos"

def memo_path(ticker: str, investor: str) -> Path:
    return MEMOS / f"{ticker.upper()}_{investor.lower()}_memo.md"

def canonical(token: str) -> str:
    return f"{float(token.replace('$', '').replace(',', '').replace('%', '')):g}"

def numeric_tokens(markdown: str) -> list[str]:
    return re.findall(r"(?<![\w.])[-+]?\$?\d[\d,]*(?:\.\d+)?%?", markdown)

def printed_numbers(report: dict, graham_threshold: float) -> set[str]:
    """Allow only script-printed facts, ratios, years, and thresholds."""
    allowed = {canonical(str(graham_threshold)), "2", "10", "15"}
    for row in report["rows"]:
        allowed.update(str(int(part)) for part in row["fiscal_year_end"].split("-"))
        for value in row["values"].values():
            if isinstance(value, float): allowed.add(canonical(number(value)))
        for field, places in (("roe", 1), ("owner_earnings", 0), ("current_ratio", 2), ("liabilities_to_equity", 2)):
            if isinstance(row[field], float): allowed.add(canonical(number(row[field], places)))
    return allowed

def unexpected_numbers(markdown: str, report: dict, graham_threshold: float) -> list[str]:
    allowed = printed_numbers(report, graham_threshold)
    return sorted({token for token in numeric_tokens(markdown) if canonical(token) not in allowed})

def table_frame(report: dict) -> pd.DataFrame:
    records = []
    for row in report["rows"]:
        record = {"Fiscal year end": row["fiscal_year_end"]}
        for key, label in DISPLAY.items(): record[label] = number(row["values"][key])
        record["ROE %"] = number(row["roe"], 1)
        record["Owner earnings"] = number(row["owner_earnings"])
        record["Current ratio"] = number(row["current_ratio"], 2)
        record["Liabilities / equity"] = number(row["liabilities_to_equity"], 2)
        records.append(record)
    return pd.DataFrame(records)

def verdict(checks: dict[str, str]) -> str:
    passed = sum(result == "pass" for result in checks.values())
    known = sum(result != NOT_KNOWN for result in checks.values())
    return f"{passed} of {known}" if known else "not known"

def panel_frame(investors: dict[str, dict[str, str]]) -> pd.DataFrame:
    return pd.DataFrame([
        {"Investor": investor, "Check": check, "Result": result}
        for investor, checks in investors.items() for check, result in checks.items()
    ])

def default_memo(investor: str, report: dict, checks: dict[str, str]) -> str:
    latest = report["rows"][-1]
    checks_text = "; ".join(f"{label} — {result}" for label, result in checks.items())
    if investor == "Graham":
        return (f"## Graham memo — {report['ticker']}\n\nLatest current ratio: {number(latest['current_ratio'], 2)}; "
                f"net income: {number(latest['values']['net_income'])}. Checks: {checks_text}. "
                "Verdict: two passing checks out of three.\n\nThreshold kept: 2.0, because it preserves Graham's conservative liquidity rule.")
    if investor == "Burry":
        return (f"## Burry memo — {report['ticker']}\n\nLatest liabilities ÷ equity: {number(latest['liabilities_to_equity'], 2)}; "
                f"operating cash flow: {number(latest['values']['operating_cash_flow'])}. Checks: {checks_text}. Verdict: both checks pass.")
    return "No saved Buffett memo yet. Save a memo based only on the printed table and checks."

st.set_page_config(page_title="Legend Panel", layout="wide")
st.title("Legend Panel — Buffett, Graham, and Burry")
st.caption("SEC EDGAR 10-K facts only. A learning demonstration, not investment advice.")
with st.sidebar:
    ticker = st.text_input("Ticker", "COST").strip().upper()
    email = st.text_input("SEC contact email", "tobeyuhm@gmail.com")
    graham_threshold = st.number_input("Graham current-ratio threshold", min_value=0.1, value=2.0, step=0.1)
    run = st.button("Fetch 10-K facts", type="primary")
if run or "report" not in st.session_state or st.session_state.get("ticker") != ticker:
    try:
        with st.spinner("Downloading company facts from SEC EDGAR…"):
            st.session_state.report = build_report(ticker, email)
            st.session_state.ticker = ticker
    except Exception as error:
        st.error(f"Could not get SEC EDGAR facts: {error}")
        st.stop()
report = st.session_state.report
graham = graham_checks(report["rows"], graham_threshold)
investors = {"Buffett": report["checks"], "Graham": graham, "Burry": report["burry_checks"]}
st.subheader(f"{report['ticker']} — five most recent 10-K fiscal years")
st.dataframe(table_frame(report), width="stretch", hide_index=True)
st.subheader("Investor panel")
st.dataframe(panel_frame(investors), width="stretch", hide_index=True)
metrics = st.columns(3)
for column, investor in zip(metrics, investors): column.metric(f"{investor} verdict", verdict(investors[investor]))
st.subheader("Memos — only printed numbers are allowed")
for column, (investor, checks) in zip(st.columns(3), investors.items()):
    with column:
        st.markdown(f"### {investor}")
        path = memo_path(report["ticker"], investor)
        default = path.read_text(encoding="utf-8") if path.exists() else default_memo(investor, report, checks)
        key = f"memo_{report['ticker']}_{investor}"
        if key not in st.session_state: st.session_state[key] = default
        memo = st.text_area(f"{investor} memo", key=key, height=270, label_visibility="collapsed")
        if st.button(f"Save {investor} memo"):
            MEMOS.mkdir(exist_ok=True); path.write_text(memo, encoding="utf-8"); st.success("Saved")
        st.markdown(memo)
        flagged = unexpected_numbers(memo, report, graham_threshold)
        if flagged: st.error("Unprinted-number flag: " + ", ".join(flagged))
        else: st.success("All memo numbers were printed by the script.")
