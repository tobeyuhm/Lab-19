"""Deterministic five-year 10-K facts extraction for the Buffett EDGAR skill."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import urllib.request
from pathlib import Path
from typing import Any

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
FLOW_TAGS = {
    "revenue": ["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues"],
    "net_income": ["NetIncomeLoss"],
    "operating_cash_flow": ["NetCashProvidedByUsedInOperatingActivities"],
    "capital_spending": ["PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets"],
}
INSTANT_TAGS = {
    "equity": ["StockholdersEquity"],
    "assets_current": ["AssetsCurrent"],
    "liabilities_current": ["LiabilitiesCurrent"],
    "liabilities": ["Liabilities"],
}
DISPLAY = {
    "revenue": "Revenue",
    "net_income": "Net income",
    "operating_cash_flow": "Operating cash flow",
    "capital_spending": "Capital spending",
    "equity": "Equity",
    "assets_current": "Current assets",
    "liabilities_current": "Current liabilities",
    "liabilities": "Liabilities",
}
NOT_FOUND = "not found"
NOT_KNOWN = "not known"


def get_json(url: str, user_agent: str) -> dict[str, Any]:
    """Download SEC JSON with the required identifying User-Agent."""
    # Do not request compressed content: urllib does not transparently decode it.
    request = urllib.request.Request(url, headers={"User-Agent": user_agent})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def cik_for_ticker(ticker: str, user_agent: str) -> int:
    listings = get_json(TICKERS_URL, user_agent)
    ticker = ticker.upper()
    for record in listings.values():
        if record["ticker"].upper() == ticker:
            return int(record["cik_str"])
    raise ValueError(f"Ticker {ticker!r} was not found in SEC company_tickers.json")


def annual_flow_entries(facts: dict[str, Any], tag: str) -> list[dict[str, Any]]:
    """Return only one-year USD facts from 10-K filings for a given XBRL tag."""
    entries = facts.get("facts", {}).get("us-gaap", {}).get(tag, {}).get("units", {}).get("USD", [])
    result = []
    for entry in entries:
        if entry.get("form") != "10-K" or not entry.get("start") or not entry.get("end"):
            continue
        try:
            days = (dt.date.fromisoformat(entry["end"]) - dt.date.fromisoformat(entry["start"])).days
        except ValueError:
            continue
        if 300 <= days <= 380:  # one fiscal year; excludes quarterly and YTD flows
            result.append(entry)
    return result


def instant_entries(facts: dict[str, Any], tag: str) -> list[dict[str, Any]]:
    """Return year-end USD instant facts from 10-K filings for a given XBRL tag."""
    entries = facts.get("facts", {}).get("us-gaap", {}).get(tag, {}).get("units", {}).get("USD", [])
    return [entry for entry in entries if entry.get("form") == "10-K" and entry.get("end") and not entry.get("start")]


def latest_for_end(entries: list[dict[str, Any]], fiscal_end: str) -> dict[str, Any] | None:
    """Implement 'same period in several filings: the latest filing wins'."""
    matches = [entry for entry in entries if entry.get("end") == fiscal_end]
    if not matches:
        return None
    return max(matches, key=lambda entry: (entry.get("filed", ""), entry.get("accn", "")))


def value_for_end(facts: dict[str, Any], tags: list[str], fiscal_end: str, is_flow: bool) -> tuple[float | str, str]:
    """Choose tags in stated priority order and never manufacture a value."""
    getter = annual_flow_entries if is_flow else instant_entries
    for tag in tags:
        entry = latest_for_end(getter(facts, tag), fiscal_end)
        if entry is not None:
            return float(entry["val"]) / 1_000_000, tag
    return NOT_FOUND, NOT_FOUND


def fiscal_year_ends(facts: dict[str, Any]) -> list[str]:
    """Use annual revenue periods as the five fiscal-year labels, primary tag first."""
    ends: set[str] = set()
    for tag in FLOW_TAGS["revenue"]:
        ends.update(entry["end"] for entry in annual_flow_entries(facts, tag))
        if len(ends) >= 5:
            break
    return sorted(ends)[-5:]


def number(value: float | str, places: int = 0) -> str:
    if isinstance(value, str):
        return value
    return f"{value:,.{places}f}"


def check_rows(rows: list[dict[str, Any]]) -> dict[str, str]:
    roes = [row["roe"] for row in rows]
    owners = [row["owner_earnings"] for row in rows]
    return {
        "ROE of 15% or more every year": (
            "pass" if all(isinstance(value, float) and value >= 15 for value in roes)
            else NOT_KNOWN if any(not isinstance(value, float) for value in roes) else "fail"
        ),
        "Owner earnings positive every year": (
            "pass" if all(isinstance(value, float) and value > 0 for value in owners)
            else NOT_KNOWN if any(not isinstance(value, float) for value in owners) else "fail"
        ),
        "Owner earnings grew, first year to last": (
            "pass" if isinstance(owners[0], float) and isinstance(owners[-1], float) and owners[-1] > owners[0]
            else NOT_KNOWN if not isinstance(owners[0], float) or not isinstance(owners[-1], float) else "fail"
        ),
    }


def result_for_all(values: list[float | str], predicate: Any) -> str:
    """Return pass/fail/not known without filling a missing EDGAR fact."""
    if any(not isinstance(value, float) for value in values):
        return NOT_KNOWN
    return "pass" if all(predicate(value) for value in values) else "fail"


def graham_checks(rows: list[dict[str, Any]], current_ratio_threshold: float = 2.0) -> dict[str, str]:
    """Benjamin Graham's simple balance-sheet and earnings checks."""
    ratios = [row["current_ratio"] for row in rows]
    incomes = [row["values"]["net_income"] for row in rows]
    latest = ratios[-1]
    return {
        f"Current ratio of {current_ratio_threshold:g} or more, latest year": (
            "pass" if isinstance(latest, float) and latest >= current_ratio_threshold
            else NOT_KNOWN if not isinstance(latest, float) else "fail"
        ),
        "Net income positive every year": result_for_all(incomes, lambda value: value > 0),
        "Net income grew, first year to last": (
            "pass" if isinstance(incomes[0], float) and isinstance(incomes[-1], float) and incomes[-1] > incomes[0]
            else NOT_KNOWN if not isinstance(incomes[0], float) or not isinstance(incomes[-1], float) else "fail"
        ),
    }


def burry_checks(rows: list[dict[str, Any]]) -> dict[str, str]:
    """Michael Burry's cash conversion and balance-sheet checks."""
    cash_vs_income: list[float | str] = []
    for row in rows:
        cash, income = row["values"]["operating_cash_flow"], row["values"]["net_income"]
        cash_vs_income.append(cash - income if isinstance(cash, float) and isinstance(income, float) else NOT_KNOWN)
    latest = rows[-1]["liabilities_to_equity"]
    return {
        "Operating cash flow at least net income every year": result_for_all(cash_vs_income, lambda value: value >= 0),
        "Liabilities no more than twice equity, latest year": (
            "pass" if isinstance(latest, float) and latest <= 2
            else NOT_KNOWN if not isinstance(latest, float) else "fail"
        ),
    }


def build_report(ticker: str, email: str) -> dict[str, Any]:
    user_agent = f"Tobey Buffett EDGAR learning lab {email}"
    cik = cik_for_ticker(ticker, user_agent)
    facts = get_json(FACTS_URL.format(cik=cik), user_agent)
    ends = fiscal_year_ends(facts)
    if len(ends) < 5:
        raise ValueError(f"SEC EDGAR has only {len(ends)} usable annual revenue periods for {ticker.upper()}")

    rows: list[dict[str, Any]] = []
    for end in ends:
        row: dict[str, Any] = {"fiscal_year_end": end, "values": {}, "tags": {}}
        for key, tags in FLOW_TAGS.items():
            value, tag = value_for_end(facts, tags, end, is_flow=True)
            row["values"][key], row["tags"][key] = value, tag
        for key, tags in INSTANT_TAGS.items():
            value, tag = value_for_end(facts, tags, end, is_flow=False)
            row["values"][key], row["tags"][key] = value, tag

        income, equity = row["values"]["net_income"], row["values"]["equity"]
        if isinstance(income, float) and isinstance(equity, float) and equity > 0:
            row["roe"] = income / equity * 100
        else:
            row["roe"] = NOT_KNOWN
        cash, capex = row["values"]["operating_cash_flow"], row["values"]["capital_spending"]
        row["owner_earnings"] = cash - capex if isinstance(cash, float) and isinstance(capex, float) else NOT_KNOWN
        assets_current, liabilities_current = row["values"]["assets_current"], row["values"]["liabilities_current"]
        row["current_ratio"] = (
            assets_current / liabilities_current
            if isinstance(assets_current, float) and isinstance(liabilities_current, float) and liabilities_current != 0
            else NOT_KNOWN
        )
        liabilities = row["values"]["liabilities"]
        row["liabilities_to_equity"] = (
            liabilities / equity
            if isinstance(liabilities, float) and isinstance(equity, float) and equity > 0
            else NOT_KNOWN
        )
        rows.append(row)

    flat_rows = [{"roe": row["roe"], "owner_earnings": row["owner_earnings"]} for row in rows]
    return {
        "ticker": ticker.upper(), "cik": f"{cik:010d}", "units": "USD millions", "rows": rows,
        "checks": check_rows(flat_rows), "graham_checks": graham_checks(rows), "burry_checks": burry_checks(rows),
    }


def print_report(report: dict[str, Any]) -> None:
    print(f"{report['ticker']} — SEC EDGAR 10-K facts ({report['units']})")
    print("Fiscal year end | Revenue | Net income | Operating cash flow | Capital spending | Equity | Current assets | Current liabilities | Liabilities | ROE % | Owner earnings | Current ratio | Liabilities / equity")
    for row in report["rows"]:
        values, tags = row["values"], row["tags"]
        fields = [row["fiscal_year_end"]]
        for key in ("revenue", "net_income", "operating_cash_flow", "capital_spending", "equity", "assets_current", "liabilities_current", "liabilities"):
            fields.append(f"{number(values[key])} [{tags[key]}]")
        fields.extend([number(row["roe"], 1), number(row["owner_earnings"]), number(row["current_ratio"], 2), number(row["liabilities_to_equity"], 2)])
        print(" | ".join(fields))
    print("\nBuffett checks")
    for label, result in report["checks"].items():
        print(f"{label}: {result}")
    print("\nGraham checks")
    for label, result in report["graham_checks"].items():
        print(f"{label}: {result}")
    print("\nBurry checks")
    for label, result in report["burry_checks"].items():
        print(f"{label}: {result}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch five annual 10-K fact rows from SEC EDGAR.")
    parser.add_argument("ticker", help="US stock ticker, for example COST")
    parser.add_argument("--email", default="tobeyuhm@gmail.com", help="Contact email included in the SEC User-Agent.")
    parser.add_argument("--json", action="store_true", help="Print the report as JSON instead of the human-readable table.")
    parser.add_argument("--save-json", type=Path, help="Also save the exact report JSON to this path.")
    args = parser.parse_args()
    try:
        report = build_report(args.ticker, args.email)
    except (ValueError, OSError, json.JSONDecodeError) as error:
        print(f"EDGAR request failed: {error}", file=sys.stderr)
        return 1
    if args.save_json:
        args.save_json.write_text(json.dumps(report, indent=2), encoding="utf-8")
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print_report(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
