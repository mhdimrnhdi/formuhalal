import hashlib
import json
import os
import re
import sqlite3
import urllib.error
from datetime import datetime, UTC
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS

from .llm import generate_substitutes, save_substitutes_text

load_dotenv()

app = Flask(__name__)
cors_origins = {
    origin.strip() for origin in os.getenv("FRONTEND_URL", "http://localhost:8000").split(",") if origin.strip()
}
cors_origins.update({"http://localhost:8000", "http://127.0.0.1:8000"})
CORS(app, origins=sorted(cors_origins))

DB_PATH = Path(os.getenv("DB_URL", "/data/database.sqlite"))
RESULTS_DIR = Path(os.getenv("FORMULATION_RESULTS_DIR", "/data/formulation_results"))
FORMULATION_RESULT_CLEAN_KEYS = {"id", "other_names", "matched_used_for"}


def _get_required_text(data: dict, *keys: str) -> str:
    for key in keys:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _get_bearer_key() -> str:
    auth_header = request.headers.get("Authorization", "")
    match = re.fullmatch(r"Bearer\s+(.+)", auth_header.strip(), flags=re.IGNORECASE)
    return match.group(1).strip() if match else ""


def _hash_key(bearer_key: str) -> str:
    digest = hashlib.sha256(bearer_key.encode("utf-8")).hexdigest()
    return str(int(digest[:16], 16))


def _connect_db() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def _split_list(value: str) -> list[str]:
    return [part.strip() for part in value.split(";") if part.strip()]


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()


def _row_to_substance(row: sqlite3.Row, matched_used_for: list[str] | None = None) -> dict:
    return {
        "id": row["id"],
        "substance": row["substance"],
        "other_names": _split_list(row["other_names"]),
        "used_for": _split_list(row["used_for"]),
        "matched_used_for": matched_used_for or [],
    }


def _find_target_substance(
    connection: sqlite3.Connection, ingredient_name: str
) -> tuple[sqlite3.Row | None, str | None]:
    normalized_ingredient = _normalize(ingredient_name)
    rows = connection.execute(
        "SELECT id, substance, other_names, used_for FROM substances ORDER BY substance"
    ).fetchall()

    for row in rows:
        if _normalize(row["substance"]) == normalized_ingredient:
            return row, "substance"

    for row in rows:
        other_names = [_normalize(name) for name in _split_list(row["other_names"])]
        if normalized_ingredient in other_names:
            return row, "other_names"

    return None, None


def _find_substances_by_used_for(
    connection: sqlite3.Connection,
    used_for_values: list[str],
    exclude_id: str | None,
) -> list[dict]:
    wanted = {_normalize(value): value for value in used_for_values}
    matches: list[dict] = []

    rows = connection.execute(
        "SELECT id, substance, other_names, used_for FROM substances ORDER BY substance"
    ).fetchall()
    for row in rows:
        if exclude_id and row["id"] == exclude_id:
            continue

        row_used_for = _split_list(row["used_for"])
        matched = [effect for effect in row_used_for if _normalize(effect) in wanted]
        if matched:
            matches.append(_row_to_substance(row, matched))

    return matches


def _group_substances_by_used_for(used_for_values: list[str], substances: list[dict]) -> dict[str, list[dict]]:
    grouped = {used_for: [] for used_for in used_for_values}
    for substance in substances:
        for used_for in substance["matched_used_for"]:
            grouped.setdefault(used_for, []).append(substance)

    return grouped


def _clean_formulation_result(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _clean_formulation_result(item)
            for key, item in value.items()
            if key not in FORMULATION_RESULT_CLEAN_KEYS
        }

    if isinstance(value, list):
        return [_clean_formulation_result(item) for item in value]

    return value


def _dedupe_substance_names(substances: list[dict]) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for item in substances:
        name = item.get("substance") if isinstance(item, dict) else None
        if name and name not in seen:
            seen.add(name)
            names.append(name)
    return names


def _prepare_formulation_result(payload: dict) -> dict:
    prepared = _clean_formulation_result(payload)
    database_result = prepared.get("database_result")
    if isinstance(database_result, dict):
        grouped = database_result.get("substances_by_used_for")
        if isinstance(grouped, dict):
            database_result["substances_by_used_for"] = {
                used_for: _dedupe_substance_names(substances) for used_for, substances in grouped.items()
            }
        database_result.pop("substances_with_same_used_for", None)
        database_result.pop("substances_with_same_used_for_count", None)
    return prepared


def _save_result(payload: dict, key_hash: str, suffix: str = "") -> Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = RESULTS_DIR / f"{key_hash}{suffix}.json"
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return output_path


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


@app.post("/api/formulation")
def formulation():
    data = request.get_json(silent=True) or {}
    product_name = _get_required_text(data, "product_name", "Product Name")
    ingredients = _get_required_text(data, "ingredients", "full_ingredients_list", "Full Ingredients List")
    substitute_for = _get_required_text(data, "substitute_for", "ingredient_to_substitute", "Ingredient to Substitute")
    bearer_key = _get_bearer_key()

    if not product_name or not ingredients or not substitute_for:
        return jsonify({"error": "product_name, ingredients, and substitute_for are required"}), 400

    if not bearer_key:
        return jsonify({"error": "Authorization header must be in the format: Bearer <key>"}), 401

    if not DB_PATH.exists():
        return jsonify({"error": f"Database not found at {DB_PATH}"}), 503

    key_hash_number = _hash_key(bearer_key)

    try:
        with _connect_db() as connection:
            target_row, matched_on = _find_target_substance(connection, substitute_for)
            target = _row_to_substance(target_row) if target_row else None
            used_for_values = target["used_for"] if target else []
            alternatives = _find_substances_by_used_for(connection, used_for_values, target["id"] if target else None)
    except sqlite3.Error as error:
        return jsonify({"error": f"Database lookup failed: {error}"}), 503

    output_path = RESULTS_DIR / f"{key_hash_number}.json"
    prepared_output_path = RESULTS_DIR / f"{key_hash_number}_prepared.json"

    payload = {
        "request_hash_number": key_hash_number,
        "stored_json": str(output_path),
        "prepared_json": str(prepared_output_path),
        "created_at": datetime.now(UTC).isoformat(),
        "input": {
            "product_name": product_name,
            "full_ingredients_list": ingredients,
            "ingredient_to_substitute": substitute_for,
        },
        "database_result": {
            "matched": target is not None,
            "matched_on": matched_on,
            "target_substance": target,
            "substances_by_used_for": _group_substances_by_used_for(used_for_values, alternatives),
            "substances_with_same_used_for": alternatives,
            "substances_with_same_used_for_count": len(alternatives),
        },
    }

    _save_result(payload, key_hash_number)
    prepared_payload = _prepare_formulation_result(payload)

    substitutes_txt_path = RESULTS_DIR / f"{key_hash_number}_substitutes.txt"
    try:
        substitutes_text, model_name = generate_substitutes(prepared_payload)
        save_substitutes_text(substitutes_text, substitutes_txt_path)
        prepared_payload["llm_substitutes"] = {
            "model": model_name,
            "substitutes_txt": str(substitutes_txt_path),
            "text": substitutes_text,
        }
    except (urllib.error.URLError, TimeoutError, RuntimeError, json.JSONDecodeError) as error:
        prepared_payload["llm_substitutes"] = {
            "error": str(error),
            "substitutes_txt": str(substitutes_txt_path),
        }

    _save_result(prepared_payload, key_hash_number, "_prepared")

    return jsonify(prepared_payload)
