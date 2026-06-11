import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
OLLAMA_PRESET = os.getenv("OLLAMA_PRESET", "fast")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "").strip()
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "3600"))

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.4-mini").strip()
OPENAI_TIMEOUT = int(os.getenv("OPENAI_TIMEOUT", "120"))
OPENAI_URL = os.getenv("OPENAI_URL", "https://api.openai.com/v1/chat/completions").strip()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash").strip()
GEMINI_TIMEOUT = int(os.getenv("GEMINI_TIMEOUT", "120"))
GEMINI_URL = os.getenv(
    "GEMINI_URL",
    "https://generativelanguage.googleapis.com/v1beta/models",
).strip()

RELEVANT_FUNCTIONS = [
    "STABILIZER OR THICKENER",
    "TEXTURIZER",
    "FORMULATION AID",
    "HUMECTANT",
]

MODEL_PRESETS = {
    "fast": {
        "model": "phi3:latest",
        "cap": 20,
        "num_ctx": 2048,
        "num_predict": 350,
    },
    "balanced": {
        "model": "phi3:latest",
        "cap": 30,
        "num_ctx": 3072,
        "num_predict": 450,
    },
    "quality": {
        "model": "llama3.1:latest",
        "cap": 40,
        "num_ctx": 4096,
        "num_predict": 600,
    },
}


def _preset_config() -> dict:
    preset = MODEL_PRESETS.get(OLLAMA_PRESET, MODEL_PRESETS["fast"])
    if OLLAMA_MODEL:
        return {**preset, "model": OLLAMA_MODEL}
    return preset


def build_substitute_prompt(prepared_payload: dict, cap: int) -> str:
    inp = prepared_payload["input"]
    groups = prepared_payload["database_result"]["substances_by_used_for"]
    substitute = inp["ingredient_to_substitute"]

    lines = []
    for func in RELEVANT_FUNCTIONS:
        subs = groups.get(func, [])[:cap]
        if not subs:
            continue
        lines.append(f"## Function: {func}")
        lines.append(", ".join(subs))
        lines.append("")

    candidates_block = "\n".join(lines)
    return f"""You are a food formulation scientist helping a Halal SME manufacturer.

PRODUCT: {inp["product_name"]}
FULL INGREDIENTS LIST: {inp["full_ingredients_list"]}
INGREDIENT TO SUBSTITUTE: {substitute}
Key roles: gelling, binding, texturizing, stabilizing.

Use the full ingredients list to understand the food matrix, but ONLY recommend substitutes for the exact INGREDIENT TO SUBSTITUTE.

Candidates (ONLY pick from this list):
{candidates_block}

Pick the 3 BEST substitutes for "{substitute}" in {inp["product_name"]}.
Format: numbered list, exact ingredient name + one short reason each. No intro or outro."""


def _call_ollama(model: str, prompt: str, *, num_ctx: int, num_predict: int) -> str:
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "keep_alive": "30m",
        "options": {
            "num_ctx": num_ctx,
            "num_predict": num_predict,
            "temperature": 0.2,
        },
    }

    req = urllib.request.Request(
        OLLAMA_URL,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )

    with urllib.request.urlopen(req, timeout=OLLAMA_TIMEOUT) as resp:
        out = json.load(resp)

    return out.get("response", "").strip()


def generate_substitutes(prepared_payload: dict) -> tuple[str, str]:
    config = _preset_config()
    prompt = build_substitute_prompt(prepared_payload, config["cap"])

    if GEMINI_API_KEY:
        return _call_gemini(prompt), GEMINI_MODEL

    text = _call_ollama(
        config["model"],
        prompt,
        num_ctx=config["num_ctx"],
        num_predict=config["num_predict"],
    )
    if not text:
        raise RuntimeError("Ollama returned an empty response")
    return text, config["model"]


def save_substitutes_text(text: str, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text, encoding="utf-8")
    return output_path


_LINE_SEP = r"(?:\s+-\s+|\s*:\s+)"
NUMBERED_LINE = re.compile(rf"^(?:\d+\.|-|\*)\s*(.+?){_LINE_SEP}(.+)$")
NUMBERED_SUPPLIER_LINE = re.compile(rf"^(?:\d+\.|-|\*)\s*(.+?){_LINE_SEP}(.+?){_LINE_SEP}(.+)$")

MALAYSIA_STATE_SUFFIX = re.compile(
    r"\s*\([^)]+\)\s*$",
    flags=re.IGNORECASE,
)


def parse_substitute_substances(substitutes_text: str) -> list[str]:
    return [entry["substance"] for entry in parse_substitute_entries(substitutes_text)]


def parse_substitute_entries(substitutes_text: str) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    for line in substitutes_text.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        match = NUMBERED_LINE.match(line)
        if not match:
            continue
        entries.append(
            {
                "substance": match.group(1).strip(),
                "explanation": match.group(2).strip(),
            }
        )
    return entries


def parse_supplier_company_name(supplier_segment: str) -> str:
    name = supplier_segment.strip()
    without_state = MALAYSIA_STATE_SUFFIX.sub("", name)
    return without_state.strip() or name


def parse_supplier_entries(suppliers_text: str) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    for line in suppliers_text.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        match = NUMBERED_SUPPLIER_LINE.match(line)
        if not match:
            continue
        supplier_segment = match.group(2).strip()
        entries.append(
            {
                "substance": match.group(1).strip(),
                "company_name": parse_supplier_company_name(supplier_segment),
                "supplier_segment": supplier_segment,
                "reason": match.group(3).strip(),
            }
        )
    return entries


def build_supplier_prompt(
    prepared_payload: dict,
    substitutes_text: str,
    substances: list[str],
) -> str:
    inp = prepared_payload["input"]
    substance_list = ", ".join(substances) if substances else "the substitutes below"

    return f"""You are a Halal ingredient sourcing advisor for Malaysian SME food manufacturers.

PRODUCT: {inp["product_name"]}
SUBSTITUTES TO SOURCE:
{substitutes_text.strip()}

Use your knowledge and search the web to find real Malaysian companies that sell or distribute these food ingredients for B2B use.
Prioritize companies listed in the JAKIM My e-Halal directory (https://myehalal.halal.gov.my) or known Halal-certified ingredient distributors in Malaysia.
Prefer food ingredient, additive, chemical, or food supply companies — not restaurants, schools, or retail shops.

For each substitute ({substance_list}), recommend ONE Malaysian supplier most likely to sell that substance.
Return the official registered company name as precisely as possible (include SDN BHD / BHD if known).

Format: numbered list matching the substitutes, one line each:
1. SUBSTANCE NAME - COMPANY NAME - one short reason
No intro or outro."""


def _call_openai(prompt: str) -> str:
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not set")

    payload = {
        "model": OPENAI_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
        "max_completion_tokens": 600,
    }
    req = urllib.request.Request(
        OPENAI_URL,
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {OPENAI_API_KEY}",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=OPENAI_TIMEOUT) as resp:
            out = json.load(resp)
    except urllib.error.HTTPError as error:
        message = error.reason
        try:
            body = json.load(error)
            message = body.get("error", {}).get("message", message)
        except json.JSONDecodeError, AttributeError:
            pass
        raise RuntimeError(f"OpenAI API error ({error.code}): {message}") from error

    choices = out.get("choices") or []
    if not choices:
        raise RuntimeError("OpenAI returned no choices")

    text = choices[0].get("message", {}).get("content", "").strip()
    if not text:
        raise RuntimeError("OpenAI returned an empty response")
    return text


def _call_gemini(prompt: str, *, use_google_search: bool = False) -> str:
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is not set")

    payload: dict = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 600,
        },
    }
    if use_google_search:
        payload["tools"] = [{"google_search": {}}]

    url = f"{GEMINI_URL.rstrip('/')}/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(req, timeout=GEMINI_TIMEOUT) as resp:
            out = json.load(resp)
    except urllib.error.HTTPError as error:
        if use_google_search:
            return _call_gemini(prompt, use_google_search=False)

        message = error.reason
        try:
            body = json.load(error)
            message = body.get("error", {}).get("message", message)
        except json.JSONDecodeError, AttributeError:
            pass
        raise RuntimeError(f"Gemini API error ({error.code}): {message}") from error

    candidates = out.get("candidates") or []
    if not candidates:
        raise RuntimeError("Gemini returned no candidates")

    parts = candidates[0].get("content", {}).get("parts") or []
    text = "".join(part.get("text", "") for part in parts).strip()
    if not text:
        raise RuntimeError("Gemini returned an empty response")
    return text


def generate_suppliers(
    prepared_payload: dict,
    substitutes_text: str,
) -> tuple[str, str]:
    substances = parse_substitute_substances(substitutes_text)
    if not substances:
        raise RuntimeError("No substitute substances found in substitutes text")

    prompt = build_supplier_prompt(prepared_payload, substitutes_text, substances)
    if GEMINI_API_KEY:
        return _call_gemini(prompt, use_google_search=True), GEMINI_MODEL
    return _call_openai(prompt), OPENAI_MODEL
