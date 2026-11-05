---
name: buffett-edgar
description: Analyze a US public company as a Buffett-style business-quality screen from SEC EDGAR 10-K company facts; use when a user requests reproducible five-year revenue, earnings, cash-flow, equity, ROE, or owner-earnings analysis without market-price data.
---

# Buffett EDGAR analysis

Use this skill for the five-year business-quality workflow. The bundled
`edgar_financials.py` is the source of truth for all numbers: do not substitute
financial websites, paid services, estimates, prices, quarterly data, or values
invented by the model.

## Run

From this folder, run:

```powershell
python edgar_financials.py COST --email "your-email@example.com"
```

The script obtains the ticker/CIK map and company facts only from SEC EDGAR,
using an identifying User-Agent. It selects 10-K annual facts for the five most
recent fiscal-year-end dates and lets the latest filed 10-K win when the same
period appears in multiple filings. Output is in USD millions and includes the
XBRL tag for each reported value.

## Required rules

- Revenue: `RevenueFromContractWithCustomerExcludingAssessedTax`, then
  `Revenues`.
- Net income: `NetIncomeLoss`.
- Operating cash flow:
  `NetCashProvidedByUsedInOperatingActivities`.
- Capital spending: `PaymentsToAcquirePropertyPlantAndEquipment`, then
  `PaymentsToAcquireProductiveAssets`.
- Equity: `StockholdersEquity`.
- ROE is net income divided by year-end equity. Owner earnings are operating
  cash flow minus capital spending.
- Do not estimate. A missing value is `not found`. A calculation missing an
  input is `not known`. If equity is zero or negative, ROE is `not known`.

## Memo

After running the script, write a short Markdown memo in the requested output
location. Adopt a Buffett-like, plainspoken business-owner lens and conclude
`own the business`, `watch it`, or `pass`. Judge the business only, not its
price. Cite only values and check outcomes printed by the script. If owner
earnings cannot be calculated, explicitly say that they cannot be judged.

The three code-produced checks are: ROE at least 15% in every year, owner
earnings positive in every year, and owner earnings higher in the final year
than the first. Do not change their result in the memo.
