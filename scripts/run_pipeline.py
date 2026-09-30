#!/usr/bin/env python3
# scripts/run_pipeline.py
"""Orchestrator for the Layer 1 ETL pipeline.

Usage:
    python scripts/run_pipeline.py --config config/sources.yaml --output data/processed
"""

import argparse
import os
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv

# Make ``src`` importable when running as a script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.extractors.statcan import StatCanExtractor
from src.extractors.bls import BLSExtractor
from src.extractors.census import CensusExtractor
from src.extractors.cmhc import CMHCExtractor
from src.loaders.parquet_loader import records_to_dataframe, write_parquet
from src.transformers import normalize
from src.utils.logger import configure_logging, get_logger

load_dotenv()


def load_config(path: str) -> dict:
    with open(path, "r") as fh:
        return yaml.safe_load(fh)


def run_statcan(config: dict, output_dir: Path) -> None:
    log = get_logger("pipeline.statcan")
    with StatCanExtractor(config["base_url"]) as extractor:
        raw = extractor.download_all(config["tables"])

    for logical_name, df in raw.items():
        meta = config["tables"][logical_name]
        df = extractor.filter_by_year(df, meta["start_year"])
        df = extractor.filter_by_geography(df, meta.get("geography", []))

        if logical_name == "cpi":
            records, report = normalize.normalize_statcan_cpi(df)
        elif logical_name == "labour_force":
            records, report = normalize.normalize_statcan_labour(df)
        else:
            log.info("statcan_transform_skipped", table=logical_name)
            continue

        log.info("statcan_validation", table=logical_name, **report.model_dump())
        out = records_to_dataframe(records)
        write_parquet(out, output_dir, f"statcan_{logical_name}")


def run_bls(config: dict, output_dir: Path) -> None:
    log = get_logger("pipeline.bls")
    with BLSExtractor(config["base_url"]) as extractor:
        frames = extractor.download_all(config["series"])

    all_records = []
    for logical_name, df in frames.items():
        records, report = normalize.normalize_bls(df, logical_name)
        log.info("bls_validation", series=logical_name, **report.model_dump())
        all_records.extend(records)

    out = records_to_dataframe(all_records)
    write_parquet(out, output_dir, "bls_indicators")


def run_census(config: dict, output_dir: Path) -> None:
    log = get_logger("pipeline.census")
    with CensusExtractor(config["base_url"]) as extractor:
        yearly = extractor.download_all(config)
        combined = extractor.to_dataframe(yearly)

    records, report = normalize.normalize_census(combined)
    log.info("census_validation", **report.model_dump())
    out = records_to_dataframe(records)
    write_parquet(out, output_dir, "census_indicators")


def run_cmhc(config: dict, output_dir: Path) -> None:
    log = get_logger("pipeline.cmhc")
    with CMHCExtractor(config["ckan_api"]) as extractor:
        frames = extractor.download_all(config["datasets"])

    all_records = []
    for logical_name, df in frames.items():
        records, report = normalize.normalize_cmhc(df, logical_name)
        log.info("cmhc_validation", dataset=logical_name, **report.model_dump())
        all_records.extend(records)

    out = records_to_dataframe(all_records)
    write_parquet(out, output_dir, "cmhc_rental")


def main():
    parser = argparse.ArgumentParser(description="Run the Layer 1 ETL pipeline.")
    parser.add_argument("--config", default="config/sources.yaml")
    parser.add_argument("--output", default=None)
    parser.add_argument("--log-level", default=os.getenv("LOG_LEVEL", "INFO"))
    args = parser.parse_args()

    configure_logging(args.log_level)
    log = get_logger("pipeline")

    config = load_config(args.config)
    output_dir = Path(
        args.output or os.getenv("PROCESSED_DATA_DIR", "data/processed")
    )

    log.info("pipeline_start", output_dir=str(output_dir))

    # Each stage is wrapped so one failing source doesn't kill the run
    for stage_name, runner in [
        ("statcan", run_statcan),
        ("bls", run_bls),
        ("census", run_census),
        ("cmhc", run_cmhc),
    ]:
        try:
            runner(config[stage_name], output_dir)
            log.info("pipeline_stage_complete", stage=stage_name)
        except Exception as exc:
            log.error("pipeline_stage_failed", stage=stage_name, error=str(exc))

    log.info("pipeline_complete")


if __name__ == "__main__":
    main()
