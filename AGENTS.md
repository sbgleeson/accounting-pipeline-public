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

## Public Repo PR Workflow

When committing and publishing public-repo changes:

1. Check current state: `git status --short --branch`.
2. Fetch latest public main: `git fetch public-clean main`.
3. Confirm the current branch is not behind: `git rev-list --left-right --count public-clean/main...HEAD`.
4. Run tests before commit: `python3 -m unittest discover -s tests`.
5. Commit only approved files with a focused message.
6. Push to a feature branch, not directly to `main`.
7. Open a PR against `public-clean/main`.
8. Confirm required checks pass.
9. Merge only after user approval.
10. Fetch public main and fast-forward local `main`.
11. Confirm clean final state.

Do not push directly to protected `main`. If a direct push is rejected, create a feature branch and PR instead.

When the user says "commit", commit locally after running the checklist through tests.
When the user says "push", create and push a feature branch and open a PR; do not attempt direct push to `main`.
When the user says "merge", confirm checks are passing, merge the PR, and sync local `main`.
