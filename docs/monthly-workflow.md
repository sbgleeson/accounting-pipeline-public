# Monthly Workflow

> Draft operating guide for the recurring accounting run.

## 1. Gather Source Files

Place source files in `profiles/my-family/raw/`. Subfolders are optional and useful once you have many months:

```text
profiles/my-family/raw/2026-02/
profiles/my-family/raw/2026-03/
profiles/my-family/raw/2026-04/
```

The pipeline processes all source files under `profiles/my-family/raw/` recursively.

- Checking and savings CSV exports.
- Credit-card CSV exports.
- Statement PDFs for configured accounts.
- Venmo statement CSV exports.

Keep account, category, merchant, income-source, reviewed-transaction,
and reporting configuration in `profiles/my-family/config/`. To rebuild the account
registry from raw filenames:

```sh
PYTHONPATH=src python3 -m accounting_pipeline init-accounts --profile my-family
```

Then review and edit the generated account names, account types, default buckets, schemas, and file matches.
Use `|` in `file_match` for alternate filename tokens that identify the same account, for example `3003|CardExport`.

## 2. Regenerate Outputs

Run:

```sh
PYTHONPATH=src python3 -m accounting_pipeline ingest --profile my-family
```

Expected outputs:

- `profiles/my-family/output/normalized_transactions.csv`
- `profiles/my-family/output/normalized_transactions.xlsx`

The command also prints a duplicate summary showing raw bank rows loaded, duplicates removed, and normalized rows kept.

## 3. Review Workbook

Start with these tabs:

- `transactions`: main review surface for categories, owner buckets, source files, and transfer flags.
- `venmo_activity`: review raw Venmo export activity and whether each row linked to a bank transaction.
- `reconciliation`: compare statement metadata against transaction totals.
- `Cash Flow Summary`: review cash in, cash out, net external cash flow, YTD cash flow, annual cash-flow totals, and cash movements excluded from spending.
- `Spending Summary`: review spending by main category and subcategory across months, with personal/family owner bucket totals below.
- `Categories & Budget`: enter optional monthly targets next to main categories or combined categories. Summaries use these targets for budget variance columns, with missed targets shown in red.
- `Income Summary`: review true income actuals and optional expected income comparisons. Expected income targets come from income-source rows in `config/budget_targets.csv`, usually with `target_type` set to `min`.

Some technical columns are hidden in review tabs but remain in the workbook for auditability. The `categories` and `accounts` tabs are hidden reference tabs used for dropdowns and workbook formulas.

## 4. Feed Back Corrections

This part is not finalized yet. Likely feedback paths:

- Add recurring merchant corrections to `profiles/my-family/config/merchant_mappings.csv`.
- Add or revise category options in `profiles/my-family/config/categories.csv`.
- Add exact reviewed decisions to `profiles/my-family/config/reviewed_transactions.csv`.
- Add code rules only when a pattern is stable enough to automate.

## Open Workflow Questions

- Should each month have its own input directory?
- Should reviewed workbooks be archived separately from generated outputs?
- Should the pipeline ingest manual corrections from a reviewed workbook?
