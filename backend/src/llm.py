import json
import os
import urllib.error
import urllib.request
from pathlib import Path

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
OLLAMA_PRESET = os.getenv("OLLAMA_PRESET", "fast")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "").strip()
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "3600"))

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
INGREDIENT TO SUBSTITUTE: {substitute}
Key roles: gelling, binding, texturizing, stabilizing.

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
