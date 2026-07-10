from __future__ import annotations

import csv
import logging

from accounting_pipeline.config import (
    PipelinePaths,
    get_pipeline_paths,
    load_budget_targets,
    load_accounts,
    load_profile_settings,
)
from accounting_pipeline.output.csv_writer import write_output
from accounting_pipeline.output.workbook_writer import write_excel_output
from accounting_pipeline.parsers.csv_parser import load_rows_with_summary
from accounting_pipeline.parsers.pdf_parser import extract_statement_metadata_with_summary
from accounting_pipeline.parsers.venmo_parser import load_venmo_activities
from accounting_pipeline.transforms.categorization import assign_categories
from accounting_pipeline.transforms.transfers import match_internal_transfers
from accounting_pipeline.transforms.venmo_enrichment import enrich_with_venmo

logger = logging.getLogger(__name__)


def load_category_rows(paths: PipelinePaths | None = None) -> list[dict[str, str]]:
    """Load the canonical category list that will feed Excel dropdowns."""
    active_paths = paths or get_pipeline_paths()
    with active_paths.category_file.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def run_pipeline(paths: PipelinePaths | None = None) -> None:
    """Run the full normalization flow from input files to output file."""
    active_paths = paths or get_pipeline_paths()
    accounts = load_accounts(active_paths)
    profile_settings = load_profile_settings(active_paths)
    budget_targets = load_budget_targets(active_paths)
    logger.info("Loading transaction rows from input CSV files")
    dedupe_result = load_rows_with_summary(active_paths)
    rows = dedupe_result.rows
    logger.info(
        "Loaded %s raw Chase transaction rows, removed %s duplicates, kept %s normalized rows",
        dedupe_result.raw_count,
        dedupe_result.duplicate_count,
        len(rows),
    )
    if dedupe_result.duplicate_counts_by_source_file:
        duplicate_summary = ", ".join(
            f"{source_file}: {count}"
            for source_file, count in sorted(dedupe_result.duplicate_counts_by_source_file.items())
        )
        logger.info("Duplicate rows removed by source file: %s", duplicate_summary)

    logger.info("Loading Venmo activity exports")
    venmo_activities = load_venmo_activities(active_paths)
    logger.info("Loaded %s Venmo activity rows", len(venmo_activities))

    category_rows = load_category_rows(active_paths)
    logger.info("Loaded %s category rows", len(category_rows))

    logger.info("Extracting statement metadata from PDFs")
    statement_result = extract_statement_metadata_with_summary(active_paths)
    statement_metadata = statement_result.statement_metadata
    statement_period_count = statement_result.parsed_count
    logger.info(
        "Statement PDF summary: found %s PDFs, parsed %s statement periods, skipped %s PDFs",
        statement_result.pdf_count,
        statement_period_count,
        len(statement_result.skipped_pdfs),
    )
    for skipped_pdf in statement_result.skipped_pdfs:
        logger.warning("Skipped statement PDF: %s", skipped_pdf)

    logger.info("Matching internal transfers")
    match_internal_transfers(rows)
    logger.info("Enriching Chase rows with Venmo activity")
    enrich_with_venmo(rows, venmo_activities)
    logger.info("Assigning categories")
    assign_categories(
        rows,
        active_paths.merchant_mapping_file,
        active_paths.income_source_file,
        active_paths.reviewed_transaction_file,
    )

    logger.info("Writing normalized CSV output")
    write_output(rows, active_paths.output_file)
    logger.info("Writing workbook output")
    write_excel_output(
        rows,
        category_rows,
        statement_metadata,
        accounts=accounts,
        profile_settings=profile_settings,
        budget_targets=budget_targets,
        venmo_activities=venmo_activities,
        output_file=active_paths.output_xlsx_file,
    )
    print(f"Wrote {len(rows)} rows to {active_paths.output_file}")
    print(f"Wrote workbook to {active_paths.output_xlsx_file}")
    print(
        "Duplicate summary: "
        f"loaded {dedupe_result.raw_count} raw rows, "
        f"removed {dedupe_result.duplicate_count} duplicates, "
        f"kept {len(rows)} rows"
    )


def main() -> None:
    """Backward-compatible wrapper for legacy entrypoints."""
    run_pipeline()
