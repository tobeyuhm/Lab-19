---
name: burry-edgar
description: Screen a US public company from SEC EDGAR 10-K facts using cash conversion and leverage checks.
---

# Burry EDGAR analysis

Use the shared `edgar_financials.py` script. Its facts are the only source.

## Rules

- Pass if operating cash flow is at least net income in every displayed fiscal year.
- Pass if latest-year liabilities are no more than twice equity.
- Missing fact: `not found`; calculation requiring a missing fact: `not known`. Never estimate.

## Memo

Write a concise Burry memo from printed numbers only. State the checks and verdict.
