#!/usr/bin/env python3
# scripts/run_warehouse.py
"""Orchestrator for Layer 2: load Parquet files into PostgreSQL."""

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.utils.logger import configure_logging, get_logger
from src.warehouse.loader import run_warehouse_load
from src.warehouse.session import health_check

load_dotenv()


def main():
    parser = argparse.ArgumentParser(description="Load Parquet files into PostgreSQL.")
    parser.add_argument(
        "--parquet-dir",
        default=os.getenv("PROCESSED_DATA_DIR", "data/processed"),
    )
    parser.add_argument("--log-level", default=os.getenv("LOG_LEVEL", "INFO"))
    args = parser.parse_args()

    configure_logging(args.log_level)
    log = get_logger("warehouse")

    if not health_check():
        log.error("database_unreachable", hint="Is docker-compose up?")
        sys.exit(1)

    log.info("warehouse_load_start", parquet_dir=args.parquet_dir)
    summary = run_warehouse_load(Path(args.parquet_dir))
    log.info("warehouse_load_done", **summary)


if __name__ == "__main__":
    main()
