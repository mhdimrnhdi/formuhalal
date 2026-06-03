"""Load cleaned CSV and supplier JSON into SQLite."""

from __future__ import annotations

import csv
import json
import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS substances (
    id TEXT PRIMARY KEY,
    substance TEXT NOT NULL,
    other_names TEXT NOT NULL DEFAULT '',
    used_for TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS suppliers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id TEXT NOT NULL DEFAULT '',
    name TEXT NOT NULL,
    location TEXT NOT NULL DEFAULT '',
    certifications TEXT NOT NULL DEFAULT '',
    source_url TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    scraped_at TEXT NOT NULL DEFAULT ''
);
"""


def load_database(
    db_path: Path,
    substances_csv: Path,
    suppliers_json: Path,
) -> tuple[int, int]:
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(db_path) as connection:
        connection.executescript(SCHEMA)
        _ensure_supplier_columns(connection)
        substance_count = _load_substances(connection, substances_csv)
        supplier_count = _load_suppliers(connection, suppliers_json)
        connection.commit()

    return substance_count, supplier_count


def _ensure_supplier_columns(connection: sqlite3.Connection) -> None:
    columns = {row[1] for row in connection.execute("PRAGMA table_info(suppliers)").fetchall()}
    if "company_id" not in columns:
        connection.execute("ALTER TABLE suppliers ADD COLUMN company_id TEXT NOT NULL DEFAULT ''")


def _load_substances(connection: sqlite3.Connection, substances_csv: Path) -> int:
    connection.execute("DELETE FROM substances")

    with substances_csv.open(encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        rows_by_id: dict[str, tuple[str, str, str, str]] = {}
        for row in reader:
            rows_by_id[row["id"]] = (
                row["id"],
                row["substance"],
                row.get("other_names", ""),
                row.get("used_for", ""),
            )

    rows = list(rows_by_id.values())
    connection.executemany(
        "INSERT INTO substances (id, substance, other_names, used_for) VALUES (?, ?, ?, ?)",
        rows,
    )
    return len(rows)


def _load_suppliers(connection: sqlite3.Connection, suppliers_json: Path) -> int:
    connection.execute("DELETE FROM suppliers")

    payload = json.loads(suppliers_json.read_text(encoding="utf-8"))
    scraped_at = payload.get("scraped_at", "")
    rows = [
        (
            supplier.get("id", supplier.get("company_id", "")),
            supplier["name"],
            supplier.get("location", ""),
            supplier.get("certifications", ""),
            supplier.get("source_url", payload.get("source_url", "")),
            supplier.get("notes", ""),
            scraped_at,
        )
        for supplier in payload.get("suppliers", [])
    ]

    connection.executemany(
        """
        INSERT INTO suppliers (
            company_id, name, location, certifications, source_url, notes, scraped_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    return len(rows)
