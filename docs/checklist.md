# Project Checklist

> Current state and next decisions. Keep this short enough to remain useful.

## Product Baseline

- [x] Problem drafted from the existing codebase and product owner's stated goal.
- [x] Users and core stories drafted.
- [x] MVP scope documented in `docs/prd.md`.
- [ ] Product owner confirms MVP scope and out-of-scope list.
- [ ] Product owner confirms current local-file workflow is the right short-term workflow.
- [ ] Product owner confirms whether generated `input/` and `output/` examples should stay in version control.

## Current Implementation

- [x] Chase bank and credit-card CSV ingestion.
- [x] Venmo CSV ingestion.
- [x] Statement PDF metadata extraction when `pdfplumber` is available.
- [x] Duplicate transaction removal.
- [x] Internal transfer matching.
- [x] Venmo enrichment with matched and unmatched statuses.
- [x] Category assignment from merchant mappings and deterministic rules.
- [x] Normalized CSV output.
- [x] Excel review workbook output.
- [x] Workbook simplification pass: hidden technical review columns, cash-flow and spending summary tabs, category total rows, category color-coding, reconciliation status, hidden reference tabs.
- [x] Duplicate summary in CLI output for raw rows, removed duplicates, and kept normalized rows.
- [x] Unit tests for parser, transform, enrichment, and report behavior.
- [x] Named profile paths for isolated raw files, configuration, and outputs.
- [x] Committed fictional demo profile with synthetic source data.
- [x] Migrate private inputs, configuration, and outputs into ignored profile workspaces.
- [x] Add presentation-oriented `Overview` and consolidated `Needs Review` sheets.
- [x] Make `Income Routing Review` optional and remove implied paycheck-to-transfer matching.
- [x] Add fictional Jordan budget targets and presentation-first summary sheets.
- [x] Reorder the opening tabs around overview, review, budget, spending, income, and cash flow.
- [x] Add latest-month and year-to-date budget variance columns to the spending summary, with missed targets shown in red.
- [x] Add latest-month and year-to-date budget variance columns to income, with missed targets shown in red.

## Next Useful Decisions

- [x] Replace `input/test_month/` with recursive `input/raw/` scanning.
- [x] Move accounts into `input/template/accounts.csv`.
- [x] Keep real `accounts.csv` local/private and track `accounts.example.csv`.
- [x] Add `init-accounts` command to generate starter local account config from raw files.
- [x] Decide how reviewed workbook corrections should feed back into templates or rules.
- [x] Decide what belongs in generated output versus source-controlled sample data.
- [ ] Decide later whether to add a simplified `Review` tab or exceptions-only tab.
- [ ] Decide how Venmo payment notes should override generic transfer categories for underlying spending and reimbursements.
- [ ] Decide how to represent reimbursements without treating them as ordinary income.
- [ ] Decide how to mark shared expenses as owed, received, already settled, not shared, or split with an override percentage.
- [ ] Decide how to represent combined Venmo cashouts that settle multiple underlying incoming payments.
- [ ] Decide whether furniture should stay in `Shopping – Household` or become a separate household/furnishings category.
- [x] Decide the first budget/category buckets: income, spending, savings, giving, investing, and notes.
- [x] Decide the first budget target sheet columns and formulas.
- [x] Decide initial savings/investing priority: emergency fund, then general savings, travel fund, and car fund, then brokerage contributions.
- [ ] Decide monthly dollar targets for emergency fund, general savings, travel fund, car fund, investing, giving, and spending categories.
- [ ] Decide whether to add draft target suggestions based on 10% investing, 10% savings, and historical category spending.
- [ ] Decide whether budget targets should be monthly-only or support quarterly/yearly targets.
- [ ] Decide which summary visuals are most useful first: selected-month pie chart, quarterly/yearly totals, cash-flow-positive indicators, or expected-versus-actual income.
- [x] Replace user-specific account IDs, paycheck sources, reviewed transactions, and Personal/Family reporting assumptions with profile configuration.

## Done Definition

- [ ] Product owner can regenerate both normalized outputs from the CLI.
- [ ] Product owner can review the workbook and understand which rows need attention.
- [ ] Reconciliation, `Cash Flow Summary`, and `Spending Summary` support the monthly close workflow.
- [ ] Tests pass before meaningful pipeline changes are considered complete.
