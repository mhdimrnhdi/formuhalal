"""Run the full ETL pipeline."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from crawler import crawl_suppliers
from fda_processor import clean_food_substances
from load_db import load_database

LOGGER = logging.getLogger("etl")


def data_dir() -> Path:
    return Path(os.getenv("DATA_DIR", "/data"))


def run_pipeline(
    *,
    skip_crawl: bool = False,
    skip_download: bool = False,
) -> None:
    root = data_dir()
    raw_dir = root / "raw"
    raw_csv = raw_dir / "FoodSubstances.csv"
    clean_csv = root / "FoodSubstances_clean.csv"
    suppliers_json = raw_dir / "suppliers.json"
    database_path = root / "database.sqlite"

    if skip_download:
        if not clean_csv.exists():
            raise FileNotFoundError(f"Clean substances CSV not found at {clean_csv}")
    else:
        if not raw_csv.exists():
            raise FileNotFoundError(f"Raw FDA CSV not found at {raw_csv}")
        LOGGER.info("Cleaning FDA substances from %s", raw_csv)
        row_count = clean_food_substances(raw_csv, clean_csv)
        LOGGER.info("Wrote %s substance rows to %s", row_count, clean_csv)

    if skip_crawl and not suppliers_json.exists():
        LOGGER.warning("Skipping supplier crawl and no existing %s found", suppliers_json)
    else:
        if not skip_crawl:
            LOGGER.info("Crawling supplier listings")
            supplier_rows = crawl_suppliers(suppliers_json)
            LOGGER.info("Saved %s suppliers to %s", supplier_rows, suppliers_json)

    if not suppliers_json.exists():
        raise FileNotFoundError(f"Supplier data not found at {suppliers_json}")

    LOGGER.info("Loading SQLite database at %s", database_path)
    substances_loaded, suppliers_loaded = load_database(database_path, clean_csv, suppliers_json)
    LOGGER.info(
        "Database refreshed with %s substances and %s suppliers",
        substances_loaded,
        suppliers_loaded,
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="Reuse the existing raw FDA CSV in DATA_DIR/raw",
    )
    parser.add_argument(
        "--skip-crawl",
        action="store_true",
        help="Reuse the existing suppliers JSON in DATA_DIR/raw",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    args = parse_args(argv)
    try:
        run_pipeline(skip_crawl=args.skip_crawl, skip_download=args.skip_download)
    except Exception:
        LOGGER.exception("ETL pipeline failed")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
