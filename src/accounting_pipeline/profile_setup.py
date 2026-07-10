from __future__ import annotations

import shutil
from pathlib import Path

from accounting_pipeline.config import PipelinePaths, ROOT_DIR


SHARED_TEMPLATE_DIR = ROOT_DIR / "input" / "template"


def init_profile(paths: PipelinePaths) -> list[Path]:
    """Create an isolated profile and copy reusable configuration templates."""
    if paths.profile_name is None:
        raise ValueError("A named profile is required.")

    paths.raw_dir.mkdir(parents=True, exist_ok=True)
    paths.config_dir.mkdir(parents=True, exist_ok=True)
    paths.output_dir.mkdir(parents=True, exist_ok=True)

    created_files: list[Path] = []
    for filename in (
        "categories.csv",
        "merchant_mappings.csv",
        "income_sources.csv",
        "reviewed_transactions.csv",
        "profile_settings.csv",
        "budget_targets.csv",
    ):
        destination = paths.config_dir / filename
        if not destination.exists():
            shutil.copyfile(SHARED_TEMPLATE_DIR / filename, destination)
            created_files.append(destination)

    account_example = paths.config_dir / "accounts.example.csv"
    if not account_example.exists():
        shutil.copyfile(SHARED_TEMPLATE_DIR / "accounts.example.csv", account_example)
        created_files.append(account_example)

    return created_files
