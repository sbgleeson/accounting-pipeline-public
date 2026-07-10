## Accounting Pipeline

Normalize Chase exports, enrich Venmo-linked Chase rows, extract statement metadata, and generate a review workbook.

### Project Docs

Active project documentation lives in `docs/`:

- `docs/prd.md`: product requirements and scope
- `docs/onboarding.md`: first-run setup for a new local profile
- `docs/checklist.md`: current state and next decisions
- `docs/decisions.md`: decision log
- `docs/monthly-workflow.md`: draft monthly operating workflow
- `AGENTS.md`: collaboration rules for AI-assisted work

### Run

The recording-safe fictional workspace uses:

```sh
PYTHONPATH=src python3 -m accounting_pipeline ingest --profile demo-jordan-lee
```

Legacy wrapper:

```sh
python3 scripts/ingest.py --profile demo-jordan-lee
```

After installing in editable mode, the console script is:

```sh
accounting-pipeline ingest
```

### Isolated Profiles

Named profiles keep each user's raw files, configuration, and generated output separate:

```sh
PYTHONPATH=src python3 -m accounting_pipeline init-profile demo-alex-morgan
# Add source files under profiles/demo-alex-morgan/raw/
PYTHONPATH=src python3 -m accounting_pipeline init-accounts --profile demo-alex-morgan
PYTHONPATH=src python3 -m accounting_pipeline ingest --profile demo-alex-morgan
```

Profile files live under:

- `profiles/<name>/raw/`
- `profiles/<name>/config/`
- `profiles/<name>/output/`

Running `ingest` without `--profile` remains supported for backward compatibility,
but named profiles are the standard workflow.

If you are setting up the project for the first time, start with `docs/onboarding.md`.

Its fictional source files and configuration live under `profiles/demo-jordan-lee/`.

### What It Produces

- `profiles/<name>/output/normalized_transactions.csv`
- `profiles/<name>/output/normalized_transactions.xlsx`

The workbook begins with `Overview` and `Needs Review`. Profiles can optionally
enable a family-specific `Income Routing Review` in `config/profile_settings.csv`.
Profile-level starting targets can be stored in `config/budget_targets.csv`; the
synthetic Jordan profile includes a complete fictional monthly plan.

### Project Layout

- `src/accounting_pipeline/`: package code
- `tests/`: automated tests
- `input/template/`: reusable starter configuration copied by `init-profile`
- `profiles/`: isolated real-user or fictional-demo workspaces
- `docs/`: product docs and workflow notes
