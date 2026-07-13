# Jordan Lee Demo Profile

Jordan Lee is a fictional product designer in Portland, Oregon who manages a
shared household budget. Every person, merchant, account number, amount, and
transaction in this profile is synthetic.

The profile is intended for recordings, regression testing, and workbook review.
It includes:

- personal checking, household savings, and a credit card
- personal and household owner buckets for shared-budget review
- payroll and interest income
- internal savings transfers and credit-card payments
- matched and unmatched Venmo activity
- a refund that offsets spending
- savings, investing, giving, and uncategorized review items

Run:

```sh
PYTHONPATH=src python3 -m accounting_pipeline ingest --profile demo-jordan-lee
```
