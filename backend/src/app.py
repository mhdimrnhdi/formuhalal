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

from .llm import (
    generate_substitutes,
    generate_suppliers,
    parse_substitute_entries,
    parse_substitute_substances,
    parse_supplier_entries,
    save_substitutes_text,
)

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

HARAM_KEYWORDS = {
    "pork",
    "lard",
    "bacon",
    "ham",
    "wine",
    "alcohol",
    "beer",
    "rum",
    "liquor",
    "vodka",
    "whiskey",
    "blood",
    "carrion",
    "dog",
    "pig",
    "swine",
}

JAILBREAK_KEYWORDS = {
    "ignore previous",
    "ignore all",
    "system prompt",
    "forget previous",
    "override",
    "bypass",
    "jailbreak",
    "do not follow",
    "disregard",
    "act as",
    "you are now",
    "developer mode",
}


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


def _hash_key(bearer_key: str, product_name: str, ingredients: str, substitute_for: str) -> str:
    combined = (
        f"{bearer_key}:{product_name.strip().lower()}:{ingredients.strip().lower()}:{substitute_for.strip().lower()}"
    )
    digest = hashlib.sha256(combined.encode("utf-8")).hexdigest()
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


SUPPLIER_KEYWORDS = (
    "INGREDIENT",
    "CHEMICAL",
    "ADDITIVE",
    "FOOD SUPPLY",
    "FOODSTUFF",
    "FOOD SUPPLIES",
    "GELLING",
    "THICKEN",
)


def _find_supplier_candidates(
    connection: sqlite3.Connection,
    substances: list[str],
    *,
    limit: int = 150,
) -> list[dict]:
    keywords = list(SUPPLIER_KEYWORDS)
    for substance in substances:
        keywords.extend(part for part in re.split(r"[\s(,]+", substance) if len(part) >= 4)

    candidates: list[dict] = []
    seen_names: set[str] = set()

    rows = connection.execute(
        """
        SELECT company_id, name, location, certifications
        FROM suppliers
        ORDER BY name
        """
    ).fetchall()

    for row in rows:
        name = row["name"]
        if name in seen_names:
            continue

        seen_names.add(name)
        candidates.append(
            {
                "company_id": row["company_id"],
                "name": name,
                "location": row["location"],
                "certifications": row["certifications"],
            }
        )
        if len(candidates) >= limit:
            break

    return candidates


def _lookup_supplier_by_name(connection: sqlite3.Connection, company_name: str) -> dict | None:
    normalized_name = _normalize(company_name)
    if not normalized_name:
        return None

    row = connection.execute(
        """
        SELECT company_id, name, location, certifications, source_url
        FROM suppliers
        WHERE lower(trim(name)) = lower(trim(?))
        ORDER BY id
        LIMIT 1
        """,
        (company_name,),
    ).fetchone()

    if row:
        return {
            "company_id": row["company_id"],
            "name": row["name"],
            "location": row["location"],
            "certifications": row["certifications"],
            "source_url": row["source_url"],
        }

    rows = connection.execute(
        """
        SELECT company_id, name, location, certifications, source_url
        FROM suppliers
        ORDER BY name
        """
    ).fetchall()
    for candidate in rows:
        if _normalize(candidate["name"]) == normalized_name:
            return {
                "company_id": candidate["company_id"],
                "name": candidate["name"],
                "location": candidate["location"],
                "certifications": candidate["certifications"],
                "source_url": candidate["source_url"],
            }

    return None


def _build_recommendations(
    connection: sqlite3.Connection,
    substitutes_text: str,
    suppliers_text: str,
) -> list[dict]:
    substitute_by_substance = {
        _normalize(entry["substance"]): entry for entry in parse_substitute_entries(substitutes_text)
    }
    recommendations: list[dict] = []

    for supplier_entry in parse_supplier_entries(suppliers_text):
        substance = supplier_entry["substance"]
        normalized_substance = _normalize(substance)
        substitute_entry = substitute_by_substance.get(normalized_substance)
        if not substitute_entry:
            continue

        explanation = substitute_entry["explanation"]

        company_name = supplier_entry["company_name"]
        supplier_record = _lookup_supplier_by_name(connection, company_name)

        # STRICT VERIFICATION: drop if not matched in DB
        if not supplier_record:
            continue

        recommendations.append(
            {
                "substance": substance,
                "explanation": explanation,
                "supplier_reason": supplier_entry["reason"],
                "supplier": {
                    "name": company_name,
                    "location": supplier_record["location"],
                    "certifications": supplier_record["certifications"],
                    "source_url": supplier_record["source_url"],
                    "matched_in_database": True,
                    "company_id": supplier_record["company_id"],
                },
            }
        )

    return recommendations


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

    context_text = f"{product_name} {ingredients} {substitute_for}".lower()

    if any(keyword in context_text for keyword in HARAM_KEYWORDS):
        return jsonify({"error": "Error: Haram ingredients or products are strictly prohibited."}), 400

    if any(keyword in context_text for keyword in JAILBREAK_KEYWORDS):
        return jsonify({"error": "Error: Invalid input format. Prompt injection detected."}), 400

    if not bearer_key:
        return jsonify({"error": "Authorization header must be in the format: Bearer <key>"}), 401

    if not DB_PATH.exists():
        return jsonify({"error": f"Database not found at {DB_PATH}"}), 503

    key_hash_number = _hash_key(bearer_key, product_name, ingredients, substitute_for)

    try:
        with _connect_db() as connection:
            target_row, matched_on = _find_target_substance(connection, substitute_for)
            if not target_row:
                return jsonify({"error": "Ingredient not recognized as a valid food substance in the database."}), 400

            target = _row_to_substance(target_row)
            used_for_values = target["used_for"]
            alternatives = _find_substances_by_used_for(connection, used_for_values, target["id"])
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
    if substitutes_txt_path.exists():
        substitutes_text = substitutes_txt_path.read_text(encoding="utf-8")
        prepared_payload["llm_substitutes"] = {
            "model": "cached",
            "substitutes_txt": str(substitutes_txt_path),
            "text": substitutes_text,
        }
    else:
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

    supplier_txt_path = RESULTS_DIR / f"{key_hash_number}_supplier.txt"
    substitutes_for_suppliers = prepared_payload.get("llm_substitutes", {}).get("text", "")
    if not substitutes_for_suppliers and substitutes_txt_path.exists():
        substitutes_for_suppliers = substitutes_txt_path.read_text(encoding="utf-8")

    if substitutes_for_suppliers.strip():
        if supplier_txt_path.exists():
            suppliers_text = supplier_txt_path.read_text(encoding="utf-8")
            prepared_payload["llm_suppliers"] = {
                "model": "cached",
                "supplier_txt": str(supplier_txt_path),
                "text": suppliers_text,
            }
        else:
            try:
                with _connect_db() as connection:
                    substances = parse_substitute_substances(substitutes_for_suppliers)
                    limit = int(os.getenv("SUPPLIER_LIMIT", "150"))
                    supplier_candidates = _find_supplier_candidates(connection, substances, limit=limit)

                suppliers_text, model_name = generate_suppliers(
                    prepared_payload,
                    substitutes_for_suppliers,
                    supplier_candidates,
                )
                save_substitutes_text(suppliers_text, supplier_txt_path)
                prepared_payload["llm_suppliers"] = {
                    "model": model_name,
                    "supplier_txt": str(supplier_txt_path),
                    "text": suppliers_text,
                }
            except (urllib.error.URLError, TimeoutError, RuntimeError, json.JSONDecodeError) as error:
                prepared_payload["llm_suppliers"] = {
                    "error": str(error),
                    "supplier_txt": str(supplier_txt_path),
                }

    suppliers_text = prepared_payload.get("llm_suppliers", {}).get("text", "")
    if not suppliers_text and supplier_txt_path.exists():
        suppliers_text = supplier_txt_path.read_text(encoding="utf-8")

    substitutes_text = prepared_payload.get("llm_substitutes", {}).get("text", "")
    if not substitutes_text and substitutes_txt_path.exists():
        substitutes_text = substitutes_txt_path.read_text(encoding="utf-8")

    if suppliers_text.strip() and substitutes_text.strip():
        try:
            with _connect_db() as connection:
                prepared_payload["recommendations"] = _build_recommendations(
                    connection,
                    substitutes_text,
                    suppliers_text,
                )
        except sqlite3.Error as error:
            prepared_payload["recommendations"] = []
            prepared_payload["recommendations_error"] = f"Supplier enrichment failed: {error}"
    else:
        prepared_payload["recommendations"] = []

    _save_result(prepared_payload, key_hash_number, "_prepared")

    return jsonify(prepared_payload)
