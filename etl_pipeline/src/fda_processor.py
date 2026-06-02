"""Clean FDA Food Substances CSV into a normalized file."""

from __future__ import annotations

import csv
import html
import re
from pathlib import Path

HEADER_MARKER = "CAS Reg No (or other ID)"
SOURCE_COLUMNS = (
    "CAS Reg No (or other ID)",
    "Substance",
    "Other Names",
    "Used for (Technical Effect)",
)
OUTPUT_COLUMNS = ("id", "substance", "other_names", "used_for")

BR_TAG_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)
HTML_TAG_RE = re.compile(r"<[^>]+>")
WHITESPACE_RE = re.compile(r"\s+")


def normalize_scalar(value: str) -> str:
    if not value:
        return ""

    text = html.unescape(value)
    text = BR_TAG_RE.sub(" ", text)
    text = HTML_TAG_RE.sub("", text)
    text = text.replace("\u2666", "").replace("&diams;", "")
    return WHITESPACE_RE.sub(" ", text).strip()


def split_list_field(value: str) -> list[str]:
    if not value:
        return []

    text = html.unescape(value)
    parts = BR_TAG_RE.split(text)
    cleaned: list[str] = []
    seen: set[str] = set()

    for part in parts:
        item = HTML_TAG_RE.sub("", part)
        item = item.replace("\u2666", "").replace("&diams;", "")
        item = WHITESPACE_RE.sub(" ", item).strip(" -,")
        if not item:
            continue
        key = item.casefold()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(item)

    return cleaned


def join_list(items: list[str]) -> str:
    return "; ".join(items)


def clean_row(row: dict[str, str]) -> dict[str, str] | None:
    substance_id = normalize_scalar(row.get(SOURCE_COLUMNS[0], ""))
    substance = normalize_scalar(row.get(SOURCE_COLUMNS[1], ""))

    if not substance_id and not substance:
        return None

    return {
        "id": substance_id,
        "substance": substance,
        "other_names": join_list(split_list_field(row.get(SOURCE_COLUMNS[2], ""))),
        "used_for": join_list(split_list_field(row.get(SOURCE_COLUMNS[3], ""))),
    }


def find_header_row(lines: list[str]) -> int:
    for index, line in enumerate(lines):
        if line.startswith(HEADER_MARKER):
            return index
    raise ValueError(f"Could not find CSV header row starting with {HEADER_MARKER!r}")


def clean_food_substances(input_path: Path, output_path: Path) -> int:
    raw_text = input_path.read_text(encoding="utf-8", errors="replace")
    header_index = find_header_row(raw_text.splitlines())
    reader = csv.DictReader(raw_text.splitlines()[header_index:])

    missing = [column for column in SOURCE_COLUMNS if column not in (reader.fieldnames or [])]
    if missing:
        raise ValueError(f"Missing expected columns: {', '.join(missing)}")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    rows_written = 0
    with output_path.open("w", encoding="utf-8", newline="") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()

        for source_row in reader:
            cleaned = clean_row(source_row)
            if cleaned is None:
                continue
            writer.writerow(cleaned)
            rows_written += 1

    return rows_written
