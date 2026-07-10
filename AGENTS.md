# Accounting Pipeline Working Rules

- Read `docs/prd.md` before changing product behavior.
- Keep `README.md` focused on setup, commands, and project layout.
- Keep `docs/prd.md` focused on product scope and constraints.
- Keep `docs/checklist.md` focused on current state and next decisions.
- Keep `docs/decisions.md` for meaningful product or architecture decisions only.
- Prefer small, testable changes to broad rewrites.
- Do not add direct bank or payment-service integrations unless `docs/prd.md` is updated first.
- Do not hide unmatched, uncategorized, or uncertain financial rows.
- Before meaningful pipeline changes are complete, run `python3 -m unittest discover -s tests`.
