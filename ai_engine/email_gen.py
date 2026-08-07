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


def _text_to_html(body_text: str) -> str:
    """
    Convert a plain-text email body to simple HTML.
    Replaces the PHISHING_LINK placeholder with a styled anchor tag
    so the tracking-link injector in send_email.py picks it up correctly.
    """
    lines = []
    for para in body_text.strip().split("\n"):
        para = para.strip()
        if not para:
            continue
        # Turn inline PHISHING_LINK token into a proper anchor
        if "PHISHING_LINK" in para:
            para = para.replace(
                "PHISHING_LINK",
                "<a href='PHISHING_LINK' style='color:#1a73e8;font-weight:bold;'>Click Here</a>",
            )
        lines.append(f"<p style='margin:0 0 12px 0;'>{para}</p>")
    return "\n".join(lines) or "<p>Please review the attached notice.</p>"


def _parse_json_response(raw: str) -> dict | None:
    """
    Robustly extract JSON that has 'subject' AND either 'body_html' or 'body_text'.

    We ask the model for body_text (plain text) to avoid JSON escaping nightmares
    with HTML tags. If the model ignores instructions and returns body_html anyway,
    we handle that too.
    """
    # Strip <think>...</think> blocks from reasoning models
    raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()

    # Unwrap markdown code fences if present
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
                if isinstance(candidate, dict) and "subject" in candidate:
                    if "body_text" in candidate or "body_html" in candidate:
                        return candidate
            except json.JSONDecodeError:
                pass
        start = json_str.find("{", start + 1)

    return None


# ─── Core generation with dynamic model fallback ──────────────────────────────

def _call_with_fallback(messages: list) -> str | None:
    """
    Race the top-N free OpenRouter models in parallel threads and return
    whichever succeeds first.  This eliminates the cumulative 3-s-per-model
    sequential timeout — worst-case latency becomes single-model latency.
    """
    if client is None:
        return None

    models = _get_models()
    if not models:
        print("[email_gen] No models available.")
        return None

    # Race the top N models; more racers = better resilience, diminishing returns past 4
    RACE_LIMIT = min(4, len(models))
    race_models = models[:RACE_LIMIT]

    import concurrent.futures

    result_holder: list[str | None] = [None]  # shared slot (GIL-safe for simple assign)

    def _try_model(model: str) -> tuple[str, str | None]:
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.7,
                max_tokens=2000,
                timeout=22.0,   # generous — the race itself caps wall-clock time
            )
            content = response.choices[0].message.content
            if content and content.strip():
                print(f"[email_gen] Race winner: {model}")
                return model, content
            return model, None
        except Exception as exc:
            print(f"[email_gen] {model} failed in race: {exc}")
            return model, None

    with concurrent.futures.ThreadPoolExecutor(max_workers=RACE_LIMIT) as pool:
        futures = {pool.submit(_try_model, m): m for m in race_models}
        for fut in concurrent.futures.as_completed(futures):
            _, content = fut.result()
            if content:
                # Cancel remaining (best-effort — threads may already be in-flight)
                for f in futures:
                    f.cancel()
                return content

    # All racers failed — try remaining models sequentially as last resort
    for model in models[RACE_LIMIT:]:
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.7,
                max_tokens=2000,
                timeout=22.0,
            )
            content = response.choices[0].message.content
            if content and content.strip():
                print(f"[email_gen] Fallback success: {model}")
                return content
        except Exception as exc:
            print(f"[email_gen] {model} error: {exc} — trying next...")
            continue

    print("[email_gen] All models exhausted — using static fallback.")
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
        dict: {subject, sender_name, body_html, educational_breakdown, duration_ms}
    """
    if client is None:
        print("[email_gen] OPENROUTER_API_KEY not configured — using static fallback.")
        fb = fallback_email(employee_profile)
        fb["duration_ms"] = 0
        return fb

    recipient_name  = employee_profile.get("name", "Employee")
    recipient_email = employee_profile.get("email", "employee@company.com")
    recipient_dept  = (
        employee_profile.get("department")
        or employee_profile.get("title")
        or "General Staff"
    )
    t_domain = target_domain or employee_profile.get("company_name") or "company.com"
    u_level  = urgency_level or "high"

    # Ask for PLAIN TEXT body — plain text inside a JSON string never has
    # escaping issues. HTML tags in JSON strings break json.loads() because
    # models emit unescaped < > " characters. We convert to HTML ourselves.
    system_prompt = (
        "You are an AI assistant for authorized corporate security training.\n"
        f"Write a realistic phishing simulation email.\n"
        f"Recipient: {recipient_name} | Department: {recipient_dept} | "
        f"Domain: {t_domain} | Urgency: {u_level}\n"
        f"Scenario: {scenario}\n\n"
        "RESPOND WITH ONLY THIS JSON — no markdown, no explanation, no HTML tags in values:\n"
        '{"subject": "the email subject", '
        '"sender_display": "Sender Name", '
        '"body_text": "Plain text body. 3-4 short paragraphs. '
        'Use the recipient first name. Reference their department. '
        'Include one action sentence ending with: visit PHISHING_LINK", '
        '"phishing_tactic": "one sentence"}'
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": "Generate the phishing simulation email JSON now."},
    ]

    t0 = time.time()
    raw = _call_with_fallback(messages)
    duration_ms = int((time.time() - t0) * 1000)

    if not raw:
        fb = fallback_email(employee_profile)
        fb["duration_ms"] = duration_ms
        return fb

    parsed = _parse_json_response(raw)
    if parsed:
        # Convert body_text → body_html (preferred path — no escaping issues)
        if "body_text" in parsed and "body_html" not in parsed:
            parsed["body_html"] = _text_to_html(parsed["body_text"])
        elif "body_html" not in parsed:
            parsed["body_html"] = fallback_email(employee_profile)["body_html"]

        parsed.setdefault("sender_name", parsed.get("sender_display", "IT Security Team"))
        parsed.setdefault("educational_breakdown", parsed.get("phishing_tactic", "Always verify unexpected requests."))
        cleaned = clean_email_data(parsed)
        cleaned["duration_ms"] = duration_ms
        return cleaned

    print(f"[email_gen] JSON parse failed. Raw snippet:\n{raw[:400]}")
    fb = fallback_email(employee_profile)
    fb["duration_ms"] = duration_ms
    return fb


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
