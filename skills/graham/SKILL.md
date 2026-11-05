---
name: graham-edgar
description: Screen a US public company from SEC EDGAR 10-K facts using Benjamin Graham-style liquidity and earnings checks.
---

# Graham EDGAR analysis

Use the shared `edgar_financials.py` script. Its facts are the only source.

## Rules

- Current ratio is current assets divided by current liabilities.
- Pass the latest-year liquidity check at a ratio of 2.0 or more unless the user explicitly changes the threshold.
- Pass if net income is positive in every displayed fiscal year.
- Pass if net income grew from the first displayed year to the last.
- Missing fact: `not found`; calculation requiring a missing fact: `not known`. Never estimate.

## Memo

Write a concise Graham memo using only values printed by the script. State the verdict and the kept liquidity threshold with one reason.
