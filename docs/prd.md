# Product Requirements - Accounting Pipeline

> Source of truth for what we are building. Keep this practical and current.

## Problem

Personal accounting review currently depends on Chase exports, Venmo activity, statement PDFs, category templates, and manual spreadsheet cleanup. The painful part is combining several account formats into one trustworthy review workbook, preserving traceability back to source files, identifying internal transfers, and surfacing transactions that need human review without redoing the same cleanup every month.

## Users

**Product owner** - The primary local user who wants a repeatable workflow for turning monthly account exports into a reviewable accounting workbook.

**Local accounting user** - A person who wants to run the same pipeline with their own isolated source files, account configuration, rules, and output.

**Fictional demo user** - A synthetic persona whose realistic but invented financial history can be recorded, shared, and tested without exposing private financial information.

**AI engineer** - The implementation partner who maintains the pipeline, tests, and documentation against this PRD.

## User Stories

- As the product owner, I want to drop monthly Chase CSV exports, Chase statement PDFs, and Venmo statement CSVs into a known input folder so that I can regenerate the accounting workbook without manual spreadsheet assembly.
- As the product owner, I want transactions from checking, savings, credit card, and Venmo-related activity normalized into one schema so that I can review spending across accounts consistently.
- As the product owner, I want internal transfers and credit-card payments identified separately from spending so that summaries do not overstate expenses.
- As the product owner, I want Venmo memos and counterparties to help classify the underlying spending, reimbursement, or transfer activity so that Venmo does not appear only as a generic transfer.
- As the product owner, I want cash inflow/outflow summarized separately from spending so that moving money between my own accounts does not distort cash flow.
- As the product owner, I want refunds and reimbursements to offset the spending categories they relate to, rather than appear as income, so category totals reflect net spending.
- As the product owner, I want true income summarized by source, including paycheck sources by person/employer and unemployment income, so I can see what money came in and from where.
- As the product owner, I want a check that payment income landing in personal accounts appears to be moved into family accounts, while still flagging that not every personal-to-family transfer is necessarily income-related.
- As the product owner, I want category suggestions with source labels and editable dropdowns so that I can quickly review and correct uncertain transactions.
- As the product owner, I want a workbook with transaction detail, Venmo match detail, reconciliation, cash-flow summaries, and spending summaries so that I can audit and understand the month from one file.
- As the product owner, I want a future budget view that compares actual income, spending, saving, charitable giving, and investing against monthly targets so that I can see whether I am meeting my financial plan.
- As a local accounting user, I want my raw files, configuration, and outputs isolated under one named profile so that they cannot be mixed with another user's data.
- As the product owner, I want a committed fictional demo profile so that I can record and test the complete workflow without exposing sensitive information.

## MVP Scope

### Local Ingestion

Read source files recursively from a selected `profiles/<name>/raw/` directory, including Chase bank CSVs, Chase credit card CSVs, Venmo statement CSVs, and statement PDFs for configured accounts. The legacy `input/raw/` location remains supported for backward compatibility.

### Profile Isolation

Support named local profiles with separate `raw/`, `config/`, and `output/` directories. A run selected with `--profile <name>` must read configuration and source files only from that profile and write generated artifacts only to that profile. Running without a profile remains backward compatible with the original project-level paths.

Profile configuration may define accounts, categories, merchant mappings, income sources, exact reviewed-transaction decisions, and reporting bucket labels. User names, account IDs, and one-off reviewed financial decisions should not be required in shared Python rules.

### Transaction Normalization

Convert source rows into a canonical transaction schema with account metadata, dates, descriptions, amounts, balances, source file names, and review fields.

### Dedupe and Stable Ordering

Remove exact duplicate transaction rows and emit rows in a stable order so regenerated output is reviewable and testable.

### Venmo Enrichment

Match Chase Venmo payment, charge, and cashout rows against Venmo activity exports when possible. Populate match status, match type, Venmo IDs, counterparties, notes, dates, and source files. Mark likely Venmo rows as unmatched when no support is found. Chase cashout deposits may be marked `transfer_supported` when a matching Venmo Standard Transfer to Chase exists, even if no single incoming Venmo payment explains the source balance.

Venmo data should support two separate interpretations:

- **Cash movement:** money moving between Chase, Venmo balance, and counterparties.
- **Underlying activity:** the real-world spending, reimbursement, income, gift, shared expense, or transfer described by the Venmo memo and counterparty.

Outgoing Venmo payments may be spending when the memo/counterparty indicates a purchase or service. Incoming Venmo payments may be reimbursement, income, or another inflow type depending on context. Venmo cashouts from Venmo balance to Chase should remain transfer activity and should not double-count the underlying Venmo payments. A cashout may represent a bundle of prior payments or money held in Venmo balance, so matching should not require one same-amount incoming payment when the Standard Transfer to Chase supports the bank deposit.

Refunds and reimbursements should be categorized back to the related spending category when the category can be inferred. If the related category is unclear, they should remain visible as review items rather than being treated as income.

### Transfer and Category Logic

Detect known internal transfers, assign categories from merchant mappings and deterministic rules, preserve the category source, and route ambiguous rows to `Uncategorized - Needs Review` or another review bucket.

### Review Workbook

Generate `profiles/<name>/output/normalized_transactions.xlsx` with a presentation-oriented `Overview`, a consolidated `Needs Review` list, transaction detail, categories and budget targets, Venmo activity with Chase link status, reconciliation, spending summaries, income summaries, and cash-flow summaries. The workbook should include validation dropdowns, formatting, warning highlights, and formulas that support review.

The `Overview` sheet should lead with the loaded period, account and transaction counts, observed income, net spending, net external cash flow, savings/investing activity, and review counts. It must state that totals reflect only loaded accounts and files.

`Needs Review` should consolidate uncategorized rows, unresolved owner buckets, unmatched Venmo activity, and missing statement coverage without hiding the underlying transaction detail.

The default visible tab order should be `Overview`, `Needs Review`, `Categories & Budget`, `Spending Summary`, `Income Summary`, and `Cash Flow Summary`, followed by detailed audit sheets.

Summary sheets should emphasize the latest month and budget decisions with large headline metrics. Older months and subcategory rows may be collapsed or hidden by default as long as they remain available for audit and expansion.

Profiles may provide starting monthly targets through `config/budget_targets.csv`. These targets populate the editable workbook budget sheet; they are planning inputs, not hard-coded pipeline rules.

Spending summaries should show net spending by category, allowing positive refunds or reimbursements in a spending category to reduce that category's total. Income summaries should focus on true income sources, such as paycheck source by person/employer, unemployment, interest, and other income. Paycheck money may arrive indirectly through Venmo cashouts or transfers before it reaches the account used for family spending; those rows should still be categorized to the underlying income source when the source is clear.

The workbook should include a visible `Categories & Budget` sheet that mirrors both main categories and combined categories. Monthly budget targets should be editable there, with target behavior set to `max`, `min`, `exact`, or `review`. Expected income should be entered as budget targets on specific income-source labels, usually with target behavior set to `min`; `Income Summary` should roll those source targets up to parent income rows and surface expected monthly income clearly. Spending and income summaries should show monthly target, target type, latest-month variance, year-to-date actual/target/variance, monthly average, and average variance next to actual totals. Variance values should be color-coded so missed targets are red and met targets remain black. Cash-flow summaries should stay focused on actual cash-account movement: cash in, cash out, net external cash flow, excluded transfers/payments, and needs-review cash out. Cash-flow summaries should include latest-month, year-to-date, and annual total columns for each year present in the loaded files.

Budget planning should support an initial priority order: build an emergency fund first, then general savings and specific savings goals such as travel and car funds, then brokerage contributions. A useful draft planning heuristic is to work toward roughly 10% of income for investing and 10% of income for savings, then distribute the remaining income across spending and giving categories based on typical historical spending. These percentages are planning guidance for setting editable targets, not hard-coded rules.

Profiles may enable an optional `Income Routing Review` diagnostic. It should show observed income deposits and observed internal transfers into the configured destination bucket as separate evidence. It must not claim that a transfer covers or belongs to a specific paycheck, and it must state that the workbook may not contain the family's complete income picture.

### Machine-Readable Output

Generate `profiles/<name>/output/normalized_transactions.csv` with the same normalized transaction fields for downstream inspection or reuse.

## Done Definition

- [ ] The product owner can run `accounting-pipeline ingest` or `PYTHONPATH=src python3 -m accounting_pipeline ingest` and regenerate both normalized outputs.
- [ ] A named profile can regenerate its outputs without reading or writing another profile's directories.
- [ ] The workbook opens with populated `transactions`, `venmo_activity`, `reconciliation`, spending summary, income summary, and cash-flow summary sheets.
- [ ] Transactions include account metadata, canonical merchant, category, category source, owner bucket, source file, and Venmo traceability fields where relevant.
- [ ] Internal transfers are marked and excluded from normal spending review where appropriate.
- [ ] Uncategorized or owner-bucket review items are visibly highlighted in the workbook.
- [ ] Statement metadata from PDFs feeds the reconciliation sheet when `pdfplumber` is available.
- [ ] The automated test suite passes locally.

## Open Questions

- [x] Should `input/test_month/` remain the canonical working input folder, or should the CLI accept a month-specific input path? Decision: use recursive `input/raw/` scanning.
- [ ] Should generated output stay committed for sample/reference purposes, or should `output/` be treated as local generated artifacts?
- [ ] What is the intended monthly close workflow after workbook review: manual edits only, or should corrections feed back into templates/rules?
- [ ] Which accounts should be configurable by non-code files instead of hard-coded in `src/accounting_pipeline/config.py`?
- [ ] Should category names use plain ASCII hyphens in code/output, or preserve typographic separators from the current templates?

## Future Iterations

- Preserve and improve the editable budget target workflow once reviewed workbook corrections can feed back into source templates.
- Budget-versus-actual summary refinements, including stronger highlighting for over-budget or under-target results.
- Use prior spending history, income percentages, and savings priority goals to suggest draft budget targets.
- Add expected income versus actual income reporting.
- Add monthly, quarterly, and yearly spending summaries beyond the current loaded-month total column.
- Add visual summaries such as a selected-month category pie chart, quarterly/yearly trend views, and cash-flow-positive/cash-flow-negative indicators.
- Improve Venmo activity modeling so payment notes can categorize underlying spending or reimbursements while cashouts remain transfer activity.
- Add reimbursement handling for shared expenses, including parent reimbursements for housing utilities/repairs and friend reimbursements for meals or other shared purchases.
- Add review fields or templates for marking reimbursements as received, already settled, not shared, or split with an override percentage.
- Optional advanced CLI flags for direct input, output, account config, and target month overrides beyond named profiles.
- Config-driven account registry instead of hard-coded account definitions.
- Rule-learning workflow that turns reviewed workbook corrections into merchant mappings.
- Import support for additional institutions beyond the current Chase and Venmo formats.
- Packaging and dependency setup that installs optional PDF parsing dependencies cleanly.

## Out Of Scope

- Direct bank, credit-card, or Venmo API connections.
- Cloud hosting or multi-user web app behavior.
- Tax filing, legal, or accounting advice.
- Investment performance tracking, brokerage position tracking, or financial advice.
- Automatic movement of money or modification of source financial accounts.
- Support for arbitrary statement formats without an explicit parser.

## Tech And Constraints

- **Stack:** Python 3.9+, setuptools package under `src/accounting_pipeline`, `openpyxl` for workbook output, optional `pdfplumber` for PDF statement extraction.
- **Data:** Local files only. Named profiles use `profiles/<name>/raw/`, `profiles/<name>/config/`, and `profiles/<name>/output/`. Real-user profiles should remain ignored and local; reusable starter templates live in `input/template/`. Legacy project-level paths remain supported but are not the standard workflow.
- **CLI:** `accounting-pipeline ingest`, with `PYTHONPATH=src python3 -m accounting_pipeline ingest` as the developer-native command. `--profile <name>` selects an isolated profile. `accounting-pipeline init-profile <name>` scaffolds one, and `accounting-pipeline init-accounts --profile <name>` creates its starter account config from raw files.
- **Testing:** Unit tests live in `tests/` and cover parsers, transforms, reports, and enrichment behavior.
- **Must not do:** Connect to financial institutions, mutate source exports, hide unmatched or uncategorized transactions, or overwrite user-reviewed workbook changes without the user intentionally regenerating output.
