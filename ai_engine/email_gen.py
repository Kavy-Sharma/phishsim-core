# ai_engine/email_gen.py
# ─────────────────────────────────────────────────────────────────────────────
# PhishSim AI — phishing email generator via OpenRouter.
#
# KEY DESIGN: Instead of a hard-coded model list that breaks whenever OpenRouter
# changes their free tier, this module DYNAMICALLY DISCOVERS free models by
# querying the OpenRouter /models endpoint and filtering for pricing == "0".
# The free-model list is cached for 1 hour so it doesn't add latency per email.
#
# Fallback chain:
#   1. Dynamic free models (fetched from OpenRouter /models API)
#   2. Static safety-net list (last-resort if API fetch fails)
#   3. Built-in static template (if OpenRouter key is missing / all models fail)
# ─────────────────────────────────────────────────────────────────────────────

import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import json
import re
import os
import time
import requests as _requests
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()


# ─── OpenRouter client ────────────────────────────────────────────────────────

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
    timeout=float(os.getenv("OPENROUTER_TIMEOUT_SECONDS", "25")),
) if OPENROUTER_API_KEY else None


# ─── Dynamic free-model discovery ────────────────────────────────────────────
# Hard-coded lists break every time OpenRouter rotates free-tier access.
# Instead we query their /models endpoint and pick models where prompt/
# completion price is "0". The result is cached for 1 hour.

_MODELS_CACHE: list[str] = []
_MODELS_CACHE_AT: float = 0.0
_MODELS_CACHE_TTL: float = 3600.0   # seconds


# A small safety-net — only used when the API fetch itself fails.
_STATIC_SAFETY_NET = [
    "google/gemma-2-9b-it:free",
    "mistralai/mistral-7b-instruct:free",
    "meta-llama/llama-3.2-3b-instruct:free",
    "nousresearch/hermes-3-llama-3.1-405b:free",
    "huggingfaceh4/zephyr-7b-beta:free",
]

# Preferred models — if any of these appear in the live free list we sort them
# to the front because they follow structured-output prompts most reliably.
_PREFERRED_ORDER = [
    "deepseek/deepseek-chat",
    "deepseek/deepseek-r1",
    "google/gemma",
    "qwen/qwen",
    "meta-llama/llama-3",
    "mistralai/mistral",
]


def _score_model(model_id: str) -> int:
    """Lower score = higher priority."""
    for idx, prefix in enumerate(_PREFERRED_ORDER):
        if prefix in model_id:
            return idx
    return len(_PREFERRED_ORDER)


def _fetch_free_models() -> list[str]:
    """
    Query OpenRouter /models and return IDs of models that are free
    (pricing.prompt == "0" and pricing.completion == "0").
    """
    try:
        headers = {}
        if OPENROUTER_API_KEY:
            headers["Authorization"] = f"Bearer {OPENROUTER_API_KEY}"

        resp = _requests.get(
            "https://openrouter.ai/api/v1/models",
            headers=headers,
            timeout=8,
        )
        resp.raise_for_status()
        all_models = resp.json().get("data", [])

        free = [
            m["id"] for m in all_models
            if (
                str(m.get("pricing", {}).get("prompt", "1"))  in ("0", "0.0")
                and str(m.get("pricing", {}).get("completion", "1")) in ("0", "0.0")
            )
        ]

        # Sort by preference
        free.sort(key=_score_model)
        print(f"[email_gen] Discovered {len(free)} free OpenRouter models "
              f"(top-3: {free[:3]})")
        return free

    except Exception as exc:
        print(f"[email_gen] Could not fetch free models from OpenRouter: {exc}")
        return []


def _get_models() -> list[str]:
    """Return the current list of free models, refreshing the cache when stale."""
    global _MODELS_CACHE, _MODELS_CACHE_AT

    if _MODELS_CACHE and (time.time() - _MODELS_CACHE_AT) < _MODELS_CACHE_TTL:
        return _MODELS_CACHE

    fresh = _fetch_free_models()
    if fresh:
        _MODELS_CACHE    = fresh
        _MODELS_CACHE_AT = time.time()
        return fresh

    # If fetch failed but we have a stale cache, keep using it
    if _MODELS_CACHE:
        print("[email_gen] Using stale model cache (API fetch failed).")
        return _MODELS_CACHE

    print("[email_gen] Using static safety-net model list.")
    return _STATIC_SAFETY_NET


# ─── Static email helpers ─────────────────────────────────────────────────────

def fallback_email(employee_profile: dict) -> dict:
    """Returns a pre-written fallback email when AI generation is unavailable."""
    return clean_email_data({
        "subject": "Action Required: Security Notice Review",
        "sender_name": "IT Security Team",
        "body_html": (
            f"<p>Dear {employee_profile.get('name', 'Employee')},</p>"
            "<p>We detected a security notice that requires your immediate review.</p>"
            "<p><a href='PHISHING_LINK'>Review Security Notice</a></p>"
            "<p>Thank you,<br>IT Security Team</p>"
        ),
        "educational_breakdown": (
            "This email used false urgency and generic authority from IT. "
            "Always verify unexpected urgent requests through an official internal channel."
        ),
    })


def clean_email_data(email_data: dict) -> dict:
    """Remove AI filler phrases and any simulation disclosure words."""
    replacements = {
        "Thank you for your prompt attention.": "Thank you.",
        "Thank you for your prompt attention":  "Thank you",
        "Thank you for your immediate attention.": "Thank you.",
        "Thank you for your immediate attention":  "Thank you",
    }

    disclosure_pattern = re.compile(
        r"\b(phishing simulation|phishing test|simulated security alert|simulated phishing|"
        r"authorized test|authorized simulation|simulated|simulation|fake|phishing)\b",
        re.IGNORECASE,
    )

    for key in ("subject", "sender_name", "body_html"):
        value = email_data.get(key)
        if isinstance(value, str):
            for old, new in replacements.items():
                value = value.replace(old, new)
            value = disclosure_pattern.sub("", value)
            value = re.sub(r"\s+", " ", value)
            value = re.sub(r"\s+([.,!?;])", r"\1", value)
            email_data[key] = value.strip()

    return email_data


def _parse_json_response(raw: str) -> dict | None:
    """Robustly extract the first valid JSON object containing 'subject' + 'body_html'."""
    # Strip <think>…</think> blocks from reasoning models (DeepSeek-R1 etc.)
    raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()

    # Unwrap markdown code fences
    json_str = raw
    code_block = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    if code_block:
        json_str = code_block.group(1)

    start = json_str.find("{")
    while start != -1:
        end = json_str.rfind("}")
        if end > start:
            try:
                candidate = json.loads(json_str[start : end + 1])
                if isinstance(candidate, dict) and "subject" in candidate and "body_html" in candidate:
                    return candidate
            except json.JSONDecodeError:
                pass
        start = json_str.find("{", start + 1)

    return None


# ─── Core generation with dynamic model fallback ──────────────────────────────

def _call_with_fallback(messages: list) -> str | None:
    """
    Try each currently-free OpenRouter model in priority order.
    Returns raw content string on success, None if all models fail.
    """
    if client is None:
        return None

    models = _get_models()
    if not models:
        print("[email_gen] No models available.")
        return None

    for model in models:
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.7,
                max_tokens=1200,   # 600 was cutting off body_html mid-sentence → JSON parse failure
            )
            content = response.choices[0].message.content
            if content and content.strip():
                print(f"[email_gen] Success with model: {model}")
                return content
            print(f"[email_gen] {model} returned empty — trying next...")

        except Exception as exc:
            err = str(exc)
            if "404" in err or "429" in err or "unavailable" in err.lower():
                print(f"[email_gen] {model} unavailable — trying next...")
                continue
            print(f"[email_gen] {model} error: {exc} — trying next...")
            continue

    print("[email_gen] All free models exhausted — using static fallback.")
    return None


# ─── Public API ───────────────────────────────────────────────────────────────

def generate_phishing_email(
    employee_profile: dict,
    scenario: str,
    target_domain: str | None = None,
    urgency_level: str | None = None,
) -> dict:
    """
    Generate a realistic phishing email for security awareness training.

    Args:
        employee_profile: dict with keys name, email, department, title, company_name…
        scenario:         scenario descriptor (e.g. 'it_alert', 'hr_update')
        target_domain:    override for the target company domain
        urgency_level:    'low' | 'medium' | 'high'

    Returns:
        dict: {subject, sender_name, body_html, educational_breakdown}
    """
    if client is None:
        print("[email_gen] OPENROUTER_API_KEY not configured — using static fallback.")
        return fallback_email(employee_profile)

    recipient_name  = employee_profile.get("name", "Employee")
    recipient_email = employee_profile.get("email", "employee@company.com")
    recipient_dept  = (
        employee_profile.get("department")
        or employee_profile.get("title")
        or "General Staff"
    )
    t_domain = target_domain or employee_profile.get("company_name") or "company.com"
    u_level  = urgency_level or "high"

    system_prompt = f"""You are an AI generating a phishing simulation email for authorized security training.

RECIPIENT: {recipient_name} ({recipient_email})
DEPARTMENT: {recipient_dept}
SCENARIO: {scenario}
COMPANY DOMAIN: {t_domain}
URGENCY: {u_level}

Generate a realistic phishing email. Respond with ONLY a JSON object — no markdown, no explanation, no extra text:
{{
  "subject": "email subject here",
  "sender_display": "Sender Name Here",
  "body_html": "HTML email body — use the recipient's actual name, reference their department/role, 150-200 words, include exactly one action link: <a href='PHISHING_LINK'>action text</a>",
  "phishing_tactic": "one sentence describing the social engineering tactic used"
}}

Rules:
- Use the recipient's first name in the salutation
- Make the body relevant to their department and the scenario
- Do NOT reveal this is a test or simulation inside the JSON values
- Pure JSON output only — the parser will break if you add anything outside the object"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": "Generate the phishing simulation email JSON now."},
    ]

    raw = _call_with_fallback(messages)
    if not raw:
        return fallback_email(employee_profile)

    parsed = _parse_json_response(raw)
    if parsed:
        # Normalise field aliases
        parsed.setdefault("sender_name", parsed.get("sender_display", "IT Security Team"))
        parsed.setdefault("educational_breakdown", parsed.get("phishing_tactic", "This is a simulated phishing email."))
        return clean_email_data(parsed)

    print(f"[email_gen] JSON parse failed. Raw:\n{raw[:300]}")
    return fallback_email(employee_profile)


# ─── CLI smoke-test ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Fetching current free models from OpenRouter…")
    models = _get_models()
    print(f"Found {len(models)} free models. Top 5: {models[:5]}\n")

    test_employee = {
        "name":        "Raj Kumar",
        "title":       "Accounts Manager",
        "company_name": "MBM University",
        "department":  "Finance",
    }
    scenario = "CEO urgently needs approval for a wire transfer before end of business day."
    result = generate_phishing_email(test_employee, scenario)
    print(json.dumps(result, indent=4, ensure_ascii=False))
