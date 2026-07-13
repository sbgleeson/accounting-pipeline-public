# Decisions Log

> Append only for meaningful product or architecture decisions. Do not log routine implementation details.

## 2026-06-15 - Keep active docs at the project level

**Decided:** Use root-level `docs/` for active project documentation and a root `AGENTS.md` for AI working rules.

**Rejected:** Keep active project truth inside `pm-toolkit/`.

**Why:** The toolkit was useful as a starter, but the accounting project should not require navigating into a template folder to understand the actual product.

## 2026-06-15 - Define the MVP as a local accounting pipeline

**Decided:** Document the current MVP as a local Python workflow that reads bank, card, payment-app, template, and statement files from the repo, then generates normalized CSV and Excel review outputs.

**Rejected:** Reframe the project as a web app, cloud service, or direct bank-integration product.

**Why:** The existing implementation and user goal point to a repeatable local monthly workflow. Direct integrations and hosting would add security, privacy, and scope complexity before the current review workflow is confirmed.

## 2026-06-15 - Preserve uncertainty in review output

**Decided:** The pipeline should expose uncertain rows through category source labels, unmatched Venmo statuses, review buckets, and workbook highlighting.

**Rejected:** Silently force every row into a confident category or hide unmatched enrichment failures.

**Why:** Financial review needs auditability. A useful first version should make uncertain cases easy to find and correct rather than pretending the automation is perfect.

## 2026-06-15 - Simplify workbook review surfaces

**Decided:** Keep `transactions` as the first visible tab for now, keep the full canonical transaction schema in both CSV and Excel, hide detailed Venmo trace columns in the Excel `transactions` tab, keep full Venmo traceability visible in `venmo_activity`, replace separate per-month summary tabs with one `Monthly Summary` tab, add reconciliation `status`, and hide `categories` and `accounts` reference tabs.

**Rejected:** Add a new simplified `Review` tab immediately, rename `transactions`, keep one summary tab per month, or add an exceptions-only tab now.

**Why:** The immediate pain is workbook clutter, especially mostly blank Venmo columns and dense monthly tabs. Hiding columns simplifies review without creating a second transaction schema or removing audit data from the workbook.

## 2026-06-15 - Prefer hide-and-format over removing workbook data

**Decided:** Keep audit fields present in generated workbook tabs, but hide low-review-value columns and use category color-coding to make the visible workbook easier to scan. Add main-category total rows to `Monthly Summary` above the subcategory rows.

**Rejected:** Remove technical columns from Excel outputs or create a separate reduced transaction schema.

**Why:** Hidden columns keep the workbook reversible and auditable while reducing review clutter. Category total rows answer higher-level spending questions without requiring a separate query or pivot table.

## 2026-06-16 - Use reusable raw input and account config

**Decided:** Use `input/raw/` as the local recursive source-file folder and move account definitions into `input/template/accounts.csv` with a `file_match` field.

**Rejected:** Keep source files in `input/test_month/` or keep account setup hard-coded in Python.

**Why:** The workbook should include all months loaded so far and should be reusable by people with different accounts. Recursive raw input folders allow month-based organization without changing the ingest command, and account CSV config lets users add/remove accounts without editing code.

## 2026-06-16 - Keep real account config private

**Decided:** Track `input/template/accounts.example.csv` as a safe template and ignore the real local `input/template/accounts.csv`.

**Rejected:** Track real account IDs and account labels in git.

**Why:** Account config contains personal financial metadata. Keeping an example file preserves reusability without exposing real account identifiers.

## 2026-06-17 - Split cash flow from spending summaries

**Decided:** Add `Cash Flow Summary` for cash-account inflows, outflows, net external cash flow, and excluded transfer/payment activity. Rename the monthly category rollup to `Spending Summary` and keep it focused on spending categories and personal/family owner buckets.

**Rejected:** Treat internal transfers, Venmo cashouts, and credit-card payments as ordinary personal/family spending.

**Why:** Moving money between a user's own accounts is real activity but not spending. Separating cash flow from spending keeps transactions auditable while preventing transfers and credit-card payments from overstating household outflows.

## 2026-06-17 - Keep budgeting as a planned next layer

**Decided:** Capture budgeting as a future workbook layer, including planned income, spending categories, savings, charitable giving, and investing targets. Budget targets should live in a separate budget sheet rather than in the category reference sheet.

**Rejected:** Put editable budget amounts directly into the `categories` reference sheet or treat savings, charitable giving, and investing as ordinary expense-only categories without a planning view.

**Why:** Categories define transaction labels, while budgets define financial intent. Keeping those separate makes the workbook easier to maintain and leaves room for budget-versus-actual, expected-versus-actual income, and cash-flow-positive reporting later.

## 2026-06-17 - Treat Venmo as both cash movement and underlying activity

**Decided:** Venmo rows need a two-layer model. Bank/payment-app transfer mechanics should remain visible for cash-flow traceability, but Venmo payment notes and counterparties should also be able to classify the underlying spending, reimbursement, or shared-expense activity.

**Rejected:** Treat every Venmo bank row as only a generic transfer, or treat Venmo cashouts as new income/spending that duplicates the original Venmo activity.

**Why:** Venmo is often the best record of what actually happened. A payment to a plumber or a friend for dinner is spending even if the bank description says Venmo, while a Venmo cashout to the linked bank account is only movement of money already represented by Venmo activity. Reimbursements should offset shared costs or receivables rather than inflate ordinary income.

**Refined:** Mark bank cashouts as `transfer_supported` when a same-amount Venmo Standard Transfer to the linked bank account appears within the posting window, even if no single same-amount incoming Venmo payment exists. This keeps supported balance transfers out of `Needs Review` while avoiding a false claim about the underlying source of Venmo balance.

**Refined:** Use one raw-activity-centered `venmo_activity` workbook sheet instead of a bank-row-centered `venmo_matches` sheet. Each Venmo export row appears once with columns showing whether it linked to a bank transaction. Completed Venmo `Charge` rows can match outgoing bank Venmo debits, with the counterparty read from the Venmo `From` field.

## 2026-06-18 - Expand categories for budget planning

**Decided:** Let budget targets mirror the category tree, while keeping planned budget amounts in a separate future budget target sheet or template. Add `Savings`, `Investing`, and `Giving` as main categories. Move charitable giving and family support into `Giving`. Leave debt and reimbursement categories out for now.

**Rejected:** Store budget amounts directly in the category template, add debt categories before there are known debt-payment transactions to classify, or add reimbursement categories before the reimbursement workflow is defined.

**Why:** Categories should identify what transactions are, and budgets should describe financial intent. Adding savings, investing, and giving creates planning buckets that can be referenced by a budget view without mixing target amounts into category definitions.

## 2026-06-19 - Add workbook-level monthly budget targets

**Decided:** Add a visible `Categories & Budget` workbook sheet that mirrors main categories and combined categories, with editable monthly targets, target type, owner bucket, and notes. Keep `input/template/categories.csv` as category definitions only. Add target, variance, and average-per-month columns to `Spending Summary` and `Income Summary`, with missed variances shown in red instead of separate status columns. Keep `Cash Flow Summary` actuals-only so it stays focused on cash-account movement and transfer diagnostics.

**Refined:** Expected income is represented in `budget_targets.csv` on specific income-source labels, such as `Income – Paycheck: Employer`, usually with target type `min`. `Income Summary` rolls those child income-source targets up to parent rows such as `Income – Paycheck`, and the front card uses the parent rollups so expected income and actual income are both summarized at the same level.

**Refined:** `Cash Flow Summary` includes a visible latest-year YTD column and visible annual total columns for each year loaded, while historical month columns remain collapsible for audit.

**Rejected:** Create a separate standalone budget-vs-actual sheet for the first budgeting pass, put savings/investing budget goal rows in `Cash Flow Summary`, or use account-balance deltas to measure savings and investing in V1.

**Why:** Keeping targets next to categories makes the budget easier to review, while keeping actual comparisons on existing summaries avoids another workbook surface. Transaction-based actuals fit the current normalized transaction model and can be improved later if balance-based planning becomes necessary.

## 2026-06-19 - Use a staged savings and investing plan

**Decided:** Treat budgeting targets as editable planning inputs, with an initial priority order of emergency fund first, then general savings and specific goals such as travel and car funds, then brokerage contributions. Use 10% of income for investing and 10% of income for savings as draft planning heuristics to discuss, then allocate the remaining income across spending and giving categories based on typical spending.

**Rejected:** Hard-code percentage-based targets into the pipeline before the actual monthly targets are reviewed.

**Why:** The workbook should help a user set and compare a practical plan, but the first target values still need human judgment. Keeping the percentages as guidance avoids making premature assumptions while preserving the intended budgeting direction.

## 2026-06-24 - Isolate users with named local profiles

**Decided:** Keep one shared Python pipeline and place each user's raw files, configuration, and generated output under `profiles/<name>/`. Preserve the original project-level paths when no profile is selected.

**Rejected:** Duplicate the pipeline for the fictional demo user or switch mutable module-level paths between users.

**Why:** A shared implementation allows demo-driven improvements to benefit every user. Explicit per-run paths make data boundaries testable and reduce the risk of reading private inputs or writing output into the wrong user's directory.

## 2026-06-24 - Keep user-specific accounting decisions in profile config

**Decided:** Store income-source names, exact reviewed-transaction decisions, transfer-report bucket labels, and review start year in profile CSV files. Detect internal transfers from paired transaction data instead of hard-coded account IDs.

**Rejected:** Add each new user's account numbers, paycheck names, and one-off reviewed transactions to shared Python rules.

**Why:** These values describe one person's financial context, not universal pipeline behavior. Keeping them beside that profile's inputs makes the shared code reusable while preserving deterministic reviewed decisions.

## 2026-06-24 - Make the family workspace a named private profile

**Decided:** Move real-user private raw files, configuration, workbook, CSV, and ad hoc outputs into gitignored profile workspaces. Keep `input/template/` limited to reusable starter configuration.

**Rejected:** Continue treating the project-level `input/` and `output/` directories as one user's implicit workspace.

**Why:** The family and fictional demo users should exercise the same profile workflow. This makes user boundaries explicit and prevents private names and reviewed decisions from leaking into reusable starter templates.

## 2026-06-24 - Lead the workbook with overview and exceptions

**Decided:** Put `Overview` and `Needs Review` first, followed by transaction detail and financial summaries. Make the family-specific income diagnostic optional and present observed income and transfers separately.

**Rejected:** Keep `transactions` as the first presentation surface or imply that amount-matched transfers prove where a specific paycheck went.

**Why:** A recording and a recurring review both need a clear narrative: what was loaded, what happened, and what requires attention. Income routing is incomplete evidence because some income may land outside loaded accounts, so the workbook should describe visibility rather than assert coverage.

## 2026-06-24 - Make budgets and summaries presentation-first

**Decided:** Load optional starting targets from each profile, include a fictional monthly budget for Jordan, place `Categories & Budget` before the financial summaries, and show latest-month metric cards with collapsed historical detail.

**Rejected:** Leave demo budget fields blank or make every month and subcategory equally prominent on first open.

**Why:** The first workbook view should communicate priorities quickly during a recording, while formulas, historical months, and subcategories remain available for audit and deeper review.
