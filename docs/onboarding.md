# New User Onboarding

> First-run guide for setting up an isolated accounting profile.

## What This Pipeline Does

The accounting pipeline reads local export files, normalizes transactions, applies configurable categorization rules, and generates a review workbook.

It is built for local files only. It does not connect to banks, credit cards, Venmo, payment services, or cloud accounts.

## Before You Start

You need:

- Python 3.9 or newer.
- Checking or savings CSV exports, if available.
- Credit-card CSV exports, if available.
- Statement PDFs, if available.
- Venmo statement CSV exports, if available.

The pipeline can run with partial source files, but the workbook can only report on the accounts and periods you load.

## 1. Create A Profile

Choose a short lowercase profile name using letters, numbers, hyphens, or underscores:

```sh
PYTHONPATH=src python3 -m accounting_pipeline init-profile my-family
```

This creates:

```text
profiles/my-family/raw/
profiles/my-family/config/
profiles/my-family/output/
```

The profile keeps one user's files, rules, and outputs isolated from every other profile.

## 2. Add Raw Files

Put source files under the profile's `raw/` folder:

```text
profiles/my-family/raw/
```

Month folders are optional but recommended:

```text
profiles/my-family/raw/2026-06/
profiles/my-family/raw/2026-07/
```

Use the month you are reviewing or closing, not the month when you downloaded the files. Statement PDFs can overlap month boundaries; the pipeline reads statement dates from the PDFs when possible.

Supported source files:

- Bank CSV exports for checking and savings.
- Credit-card CSV exports.
- Statement PDFs for configured accounts.
- Venmo statement CSV exports named like `VenmoStatement_June_2026.csv`.

Do not edit raw exports. If something needs correction, add a rule or review decision in `config/`.

## 3. Initialize Accounts

After adding raw files, generate a starter account registry:

```sh
PYTHONPATH=src python3 -m accounting_pipeline init-accounts --profile my-family
```

Then review:

```text
profiles/my-family/config/accounts.csv
```

Check these columns:

- `account_id`: account identifier used in filenames or statements.
- `account_name`: readable workbook label.
- `account_type`: usually `checking`, `savings`, or `credit_card`.
- `default_bucket`: reporting owner bucket, such as `Personal`, `Family`, `Household`, or `Credit`.
- `schema`: `bank` for checking/savings exports, `card` for credit-card exports.
- `file_match`: filename tokens that identify this account. Use `|` for alternate tokens, such as `3003|CardExport`.

If the generated account config is wrong, edit `accounts.csv` before running ingest.

## 4. Run Ingest

Generate outputs:

```sh
PYTHONPATH=src python3 -m accounting_pipeline ingest --profile my-family
```

Expected outputs:

```text
profiles/my-family/output/normalized_transactions.csv
profiles/my-family/output/normalized_transactions.xlsx
```

The command prints how many raw bank rows were loaded, how many duplicates were removed, and how many normalized rows were kept.

## 5. Review The Workbook

Open:

```text
profiles/my-family/output/normalized_transactions.xlsx
```

Start with:

- `Overview`: loaded period, account counts, transaction counts, headline metrics, and review counts.
- `Needs Review`: uncategorized rows, unmatched Venmo rows, owner-bucket issues, and statement coverage warnings.
- `Categories & Budget`: editable budget reality, targets, target types, review status, and notes.
- `Spending Summary`: spending by category and month.
- `Income Summary`: true income by source.
- `Cash Flow Summary`: cash in, cash out, net external cash flow, YTD cash flow, annual cash-flow totals, transfer diagnostics, and needs-review cash out.
- `transactions`: normalized transaction detail, newest first.
- `venmo_activity`: raw Venmo export activity with bank link status.
- `reconciliation`: statement metadata and transaction coverage checks.

Older month columns and subcategory rows may be grouped or collapsed. Expand them when you need history.

## 6. Feed Back Corrections

Generated output files are safe to regenerate. Durable decisions belong in profile config files:

- `config/merchant_mappings.csv`: recurring merchant/category rules.
- `config/reviewed_transactions.csv`: exact one-off category decisions.
- `config/categories.csv`: allowed category list.
- `config/income_sources.csv`: income source matching rules.
- `config/budget_targets.csv`: budget reality, goals, target behavior, owner bucket, and notes.
- `config/profile_settings.csv`: optional profile-level reporting settings.

Do not hide uncertain rows. If a row is unmatched, uncategorized, or unclear, keep it visible until a person decides how to handle it.

## 7. Budget Targets

Budget targets are optional. If present, they populate `Categories & Budget` and drive target comparisons in the summary sheets.

Use:

```text
profiles/my-family/config/budget_targets.csv
```

Columns:

- `budget_label`: main category or combined category label.
- `reality_monthly`: optional manual baseline; the workbook fills `Reality` from loaded monthly averages when available.
- `monthly_target`: goal used by workbook budget comparisons; may be a number or an Excel formula beginning with `=`.
- `target_type`: `max`, `min`, `exact`, or `review`.
- `owner_bucket`: optional owner bucket.
- `notes`: rationale for the target.

The pipeline calculates actual spending from transactions. In the generated workbook, `Reality` is a formula-driven monthly average from the loaded spending and income summary sheets when the label appears there.

Expected income also belongs in `budget_targets.csv`. Use the specific income-source label from the workbook or `categories.csv`, such as `Income – Paycheck: Demo Employer`, set `monthly_target` to the expected monthly amount, and use `target_type` of `min`. The `Income Summary` rolls those income-source targets up to parent rows such as `Income – Paycheck`, and surfaces the parent rollups as expected monthly income.

Savings and investing targets can reference expected income instead of being hard-coded. For example, an investing target can use a workbook formula based on `Income – Paycheck`, with a note such as `Target is 10% of expected income; adjust percentage as desired`. Emergency fund savings can use the same pattern while the fund is being built, with a note to set the target to `0` once the fund is filled.

## 8. Repeat Monthly

For the next monthly close:

1. Add new source files under a month folder in `raw/`.
2. Run `ingest`.
3. Review `Overview` and `Needs Review`.
4. Add recurring corrections to config files.
5. Regenerate if needed.

See `docs/monthly-workflow.md` for the recurring monthly workflow.

## Try The Demo Profile

The fictional demo profile is safe to run without private data:

```sh
PYTHONPATH=src python3 -m accounting_pipeline ingest --profile demo-jordan-lee
```

Open:

```text
profiles/demo-jordan-lee/output/normalized_transactions.xlsx
```

Use it to understand the workbook structure before setting up a real profile.
