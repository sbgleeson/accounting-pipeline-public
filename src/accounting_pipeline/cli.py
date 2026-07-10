from __future__ import annotations

import argparse
import logging

from accounting_pipeline.account_setup import init_accounts
from accounting_pipeline.config import get_pipeline_paths
from accounting_pipeline.main import run_pipeline
from accounting_pipeline.profile_setup import init_profile


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line interface for the accounting pipeline."""
    parser = argparse.ArgumentParser(prog="accounting-pipeline")
    log_level_kwargs = {
        "default": "INFO",
        "choices": ["DEBUG", "INFO", "WARNING", "ERROR"],
        "help": "Set the logging verbosity.",
    }
    parser.add_argument("--log-level", **log_level_kwargs)

    subparsers = parser.add_subparsers(dest="command")
    ingest_parser = subparsers.add_parser("ingest", help="Read inputs and regenerate the normalized outputs.")
    ingest_parser.add_argument(
        "--profile",
        help="Use isolated files under profiles/<name>/ instead of the legacy input/ and output/ paths.",
    )
    ingest_parser.add_argument("--log-level", **log_level_kwargs)
    init_accounts_parser = subparsers.add_parser(
        "init-accounts",
        help="Generate a starter local accounts.csv from raw input filenames.",
    )
    init_accounts_parser.add_argument("--force", action="store_true", help="Overwrite an existing accounts.csv.")
    init_accounts_parser.add_argument(
        "--profile",
        help="Use isolated files under profiles/<name>/ instead of the legacy input/ path.",
    )
    init_accounts_parser.add_argument("--log-level", **log_level_kwargs)
    init_profile_parser = subparsers.add_parser(
        "init-profile",
        help="Create isolated raw, config, and output directories for a new profile.",
    )
    init_profile_parser.add_argument("profile", help="Lowercase profile name, such as demo-alex-morgan.")
    init_profile_parser.add_argument("--log-level", **log_level_kwargs)
    return parser


def configure_logging(log_level: str) -> None:
    """Configure process-wide logging for the CLI."""
    logging.basicConfig(
        level=getattr(logging, log_level),
        format="%(levelname)s %(name)s: %(message)s",
    )


def main(argv: list[str] | None = None) -> None:
    """Run the CLI."""
    parser = build_parser()
    args = parser.parse_args(argv)
    configure_logging(args.log_level)

    command = args.command or "ingest"
    try:
        paths = get_pipeline_paths(getattr(args, "profile", None))
    except ValueError as exc:
        parser.error(str(exc))
    if command == "ingest":
        run_pipeline(paths)
        return
    if command == "init-accounts":
        try:
            accounts = init_accounts(force=args.force, paths=paths)
        except FileExistsError as exc:
            parser.error(str(exc))
        print(f"Wrote {paths.account_file} with {len(accounts)} discovered accounts.")
        print("Review and edit account_name, account_type, schema, default_bucket, and file_match before ingesting.")
        return
    if command == "init-profile":
        created_files = init_profile(paths)
        print(f"Initialized profile at {paths.root}")
        if created_files:
            print(f"Copied {len(created_files)} reusable config files.")
        print(f"Add source files under {paths.raw_dir}, then run init-accounts with --profile {paths.profile_name}.")
        return

    parser.error(f"Unsupported command: {command}")
