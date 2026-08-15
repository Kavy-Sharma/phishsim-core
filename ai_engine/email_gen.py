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

def fallback_email(employee_profile: dict, scenario: str | None = None) -> dict:
    """Returns a pre-written fallback email when AI generation is unavailable."""
    if scenario:
        s_mapped = scenario.lower().strip()
        if s_mapped == "ceo": s_mapped = "ceo_fraud"
        if s_mapped == "it": s_mapped = "it_alert"
        if s_mapped == "hr": s_mapped = "hr_update"
        
        try:
            static_pair = get_static_game_fallback(employee_profile, s_mapped)
            if static_pair and "phish" in static_pair:
                phish = static_pair["phish"]
                body_text = phish.get("body_text", "")
                body_html = _text_to_html(body_text) if body_text else ""
                return clean_email_data({
                    "subject": phish.get("subject", "Action Required"),
                    "sender_name": phish.get("sender_name", "IT Support"),
                    "sender_display": phish.get("sender_display") or phish.get("sender_name"),
                    "body_html": body_html,
                    "body_text": body_text,
                    "phishing_tactic": phish.get("phishing_tactic", ""),
                    "educational_breakdown": phish.get("phishing_tactic", "Always verify unexpected links."),
                    "bait_score": phish.get("bait_score")
                })
        except Exception as e:
            print(f"[email_gen] Error loading static scenario fallback: {e}")

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



def validate_bait_score(bait_score) -> dict | None:
    """
    Validates the bait_score dictionary structure and values.
    Returns a cleaned dict if valid, otherwise None.
    """
    if not isinstance(bait_score, dict):
        return None
    required_keys = {"urgency", "authority", "believability", "obfuscation", "personalization"}
    if not required_keys.issubset(bait_score.keys()):
        return None
    validated = {}
    for key in required_keys:
        val = bait_score[key]
        if isinstance(val, (int, float)):
            val_int = int(val)
        elif isinstance(val, str) and val.strip().isdigit():
            val_int = int(val)
        else:
            return None
        if not (0 <= val_int <= 100):
            return None
        validated[key] = val_int
    return validated


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
        fb = fallback_email(employee_profile, scenario)
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
        "Write a realistic phishing simulation email and self-rate it on 5 axes (0-100 each): "
        "urgency, authority, believability, obfuscation, personalization.\n"
        f"Recipient: {recipient_name} | Department: {recipient_dept} | "
        f"Domain: {t_domain} | Urgency: {u_level}\n"
        f"Scenario: {scenario}\n\n"
        "You must respond with ONLY a single JSON object. No markdown formatting (like ```json), "
        "no explanation, and no HTML tags inside the JSON string values. "
        "The JSON response schema must be exactly:\n"
        "{\n"
        '  "subject": "email subject",\n'
        '  "sender_display": "Sender Display Name",\n'
        '  "body_text": "Body text. 3-4 short paragraphs. Reference recipient name and department. '
        'Include one action sentence ending with: visit PHISHING_LINK",\n'
        '  "phishing_tactic": "one-sentence explanation of tactic",\n'
        '  "bait_score": {\n'
        '    "urgency": 85,\n'
        '    "authority": 70,\n'
        '    "believability": 80,\n'
        '    "obfuscation": 55,\n'
        '    "personalization": 75\n'
        "  }\n"
        "}\n\n"
        "FEW-SHOT EXAMPLES:\n"
        "Example 1 (HR Payroll):\n"
        "{\n"
        '  "subject": "Urgent: Direct deposit details change",\n'
        '  "sender_display": "HR Services",\n'
        '  "body_text": "Hi Jane,\\n\\nWe noticed an error in your payroll file for the Marketing department. '
        'Please visit PHISHING_LINK to update your direct deposit details immediately to ensure your next payment is processed on time.\\n\\nThanks,\\nHR Operations Team",\n'
        '  "phishing_tactic": "The email uses false urgency and direct financial incentives to coerce compliance.",\n'
        '  "bait_score": {\n'
        '    "urgency": 85,\n'
        '    "authority": 70,\n'
        '    "believability": 80,\n'
        '    "obfuscation": 55,\n'
        '    "personalization": 75\n'
        "  }\n"
        "}\n\n"
        "Example 2 (IT Support):\n"
        "{\n"
        '  "subject": "Action Required: Password Expiry Notice",\n'
        '  "sender_display": "IT Security Office",\n'
        '  "body_text": "Dear John,\\n\\nYour password is scheduled to expire soon. To maintain access to MBM University systems for the Finance department, you must verify your identity immediately: visit PHISHING_LINK.\\n\\nBest regards,\\nIT Support Desk",\n'
        '  "phishing_tactic": "Impersonates internal IT authority and imposes a strict deadline.",\n'
        '  "bait_score": {\n'
        '    "urgency": 95,\n'
        '    "authority": 90,\n'
        '    "believability": 85,\n'
        '    "obfuscation": 60,\n'
        '    "personalization": 65\n'
        '  }\n'
        "}"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": "Generate the phishing simulation email JSON now."},
    ]

    t0 = time.time()
    raw = _call_with_fallback(messages)
    duration_ms = int((time.time() - t0) * 1000)

    if not raw:
        fb = fallback_email(employee_profile, scenario)
        fb["duration_ms"] = duration_ms
        return fb

    parsed = _parse_json_response(raw)
    if parsed:
        # Convert body_text → body_html (preferred path — no escaping issues)
        if "body_text" in parsed and "body_html" not in parsed:
            parsed["body_html"] = _text_to_html(parsed["body_text"])
        elif "body_html" not in parsed:
            parsed["body_html"] = fallback_email(employee_profile, scenario)["body_html"]

        parsed.setdefault("sender_name", parsed.get("sender_display", "IT Security Team"))
        parsed.setdefault("educational_breakdown", parsed.get("phishing_tactic", "Always verify unexpected requests."))
        
        # Validate bait score
        raw_bait_score = parsed.get("bait_score")
        validated_bait = validate_bait_score(raw_bait_score)
        if validated_bait:
            parsed["bait_score"] = validated_bait
        else:
            parsed.pop("bait_score", None) # remove invalid or missing bait score

        cleaned = clean_email_data(parsed)
        cleaned["duration_ms"] = duration_ms
        return cleaned

    print(f"[email_gen] JSON parse failed. Raw snippet:\n{raw[:400]}")
    fb = fallback_email(employee_profile, scenario)
    fb["duration_ms"] = duration_ms
    return fb


def _parse_game_json_response(raw: str) -> dict | None:
    """Robustly extract JSON with both 'phish' and 'legit' email objects."""
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
                if isinstance(candidate, dict) and "phish" in candidate and "legit" in candidate:
                    ph = candidate["phish"]
                    lg = candidate["legit"]
                    if isinstance(ph, dict) and isinstance(lg, dict):
                        if "subject" in ph and "body_text" in ph and "subject" in lg and "body_text" in lg:
                            return candidate
            except json.JSONDecodeError:
                pass
        start = json_str.find("{", start + 1)

    return None


def get_static_game_fallback(employee_profile: dict, scenario: str) -> dict:
    """Returns high-quality matched static email pairs for fallback scenarios."""
    recipient_name = employee_profile.get("name", "Jordan Ellis")
    
    fallbacks = {
        "ceo_fraud": {
            "phish": {
                "subject": "Urgent: Authorization needed for vendor payment",
                "sender_name": "Executive Office",
                "sender_display": "Office of the CEO",
                "body_text": f"Hi {recipient_name},\n\nI am currently in executive meetings and need you to authorize an urgent wire payment of $45,000 for our incoming vendor today. Please visit PHISHING_LINK to sign off on the disbursement immediately so we avoid contractual penalties.\n\nBest regards,\nExecutive Office",
                "phishing_tactic": "Impersonates executive authority and fabricates high-urgency financial pressure to bypass standard dual-control accounting checks.",
                "bait_score": {"urgency": 92, "authority": 95, "believability": 85, "obfuscation": 55, "personalization": 80}
            },
            "legit": {
                "subject": "Vendor payment authorization notice - Q3 Schedule",
                "sender_name": "Executive Office",
                "sender_display": "Office of the CEO",
                "body_text": f"Hi {recipient_name},\n\nFollowing our budget review, the executive sign-offs for Q3 vendor disbursements have been uploaded to the internal ERP ledger. Please review the scheduled batches through your standard accounting workstation portal before Friday's close.\n\nWarm regards,\nExecutive Office"
            }
        },
        "it_alert": {
            "phish": {
                "subject": "Security Alert: SSO Re-Authentication Required Within 2 Hours",
                "sender_name": "IT Security Helpdesk",
                "sender_display": "IT Security Helpdesk",
                "body_text": f"Dear {recipient_name},\n\nOur identity provider logged an anomalous sign-in attempt from an unrecognized location. To prevent your corporate account from being locked, you must visit PHISHING_LINK to verify your credentials within 2 hours.\n\nRegards,\nIT Security & Identity Team",
                "phishing_tactic": "Uses artificial time pressure and security scare tactics to harvest corporate Single Sign-On credentials.",
                "bait_score": {"urgency": 95, "authority": 90, "believability": 88, "obfuscation": 60, "personalization": 75}
            },
            "legit": {
                "subject": "Scheduled SSO Security Upgrade Notification",
                "sender_name": "IT Security Helpdesk",
                "sender_display": "IT Security Helpdesk",
                "body_text": f"Dear {recipient_name},\n\nIT is upgrading our Single Sign-On certificate this Saturday between 02:00 and 04:00 AM EST. No user action is required. If you experience session timeouts after the maintenance, simply log in as usual via our standard intranet portal.\n\nThank you,\nIT Security & Identity Team"
            }
        },
        "hr_update": {
            "phish": {
                "subject": "Urgent: Direct Deposit Discrepancy – Payroll Confirmation Required",
                "sender_name": "HR Benefits & Payroll",
                "sender_display": "HR Benefits & Payroll",
                "body_text": f"Dear {recipient_name},\n\nA routing number discrepancy was flagged during pre-payroll validation. To prevent delays in your upcoming salary direct deposit, please visit PHISHING_LINK immediately to confirm your banking details.\n\nSincerely,\nHR Payroll Services",
                "phishing_tactic": "Leverages fear of missing payroll to pressure the victim into disclosing sensitive banking credentials.",
                "bait_score": {"urgency": 90, "authority": 85, "believability": 90, "obfuscation": 55, "personalization": 80}
            },
            "legit": {
                "subject": "Annual Direct Deposit & Tax Withholding Verification Notice",
                "sender_name": "HR Benefits & Payroll",
                "sender_display": "HR Benefits & Payroll",
                "body_text": f"Dear {recipient_name},\n\nThe annual verification window for payroll tax forms and direct deposit routing is now open through the 25th. You can review your existing preferences anytime by logging into the corporate HR portal from your work device.\n\nSincerely,\nHR Payroll Services"
            }
        },
        "invoice": {
            "phish": {
                "subject": "Final Notice: Overdue Statement for Invoice #88492",
                "sender_name": "Accounts Payable Services",
                "sender_display": "Accounts Payable Services",
                "body_text": f"Attention: Accounts Team,\n\nInvoice #88492 for $4,280.00 remains unpaid past the 30-day net terms. To prevent immediate suspension of enterprise services and legal collection fees, review the statement and settle payment now: visit PHISHING_LINK.\n\nRegards,\nBilling Operations",
                "phishing_tactic": "Simulates vendor collection urgency and penalties to trick employees into expediting fraudulent invoice payments.",
                "bait_score": {"urgency": 88, "authority": 78, "believability": 85, "obfuscation": 50, "personalization": 65}
            },
            "legit": {
                "subject": "Remittance Confirmation: Invoice #88492 Processed",
                "sender_name": "Accounts Payable Services",
                "sender_display": "Accounts Payable Services",
                "body_text": f"Hello {recipient_name},\n\nWe have received and approved the remittance for Invoice #88492. Payment has been scheduled in accordance with our standard 30-day net disbursement cycle. No further action is required from your department.\n\nThank you,\nBilling Operations"
            }
        }
    }
    
    selected = fallbacks.get(scenario, fallbacks["ceo_fraud"])
    ph = selected["phish"].copy()
    lg = selected["legit"].copy()
    
    ph["body_html"] = _text_to_html(ph["body_text"])
    lg["body_html"] = _text_to_html(lg["body_text"])
    
    return {
        "success": True,
        "phish": ph,
        "legit": lg,
        "duration_ms": 0
    }


def generate_game_round(
    employee_profile: dict,
    scenario: str,
    target_domain: str | None = None,
) -> dict:
    """
    Generate a Spot the Phish game round: one phish email, one legit email.
    Both share the exact same sender context and specific topic context.
    """
    if client is None:
        print("[email_gen] OPENROUTER_API_KEY not configured — using static game fallback.")
        return get_static_game_fallback(employee_profile, scenario)

    recipient_name  = employee_profile.get("name", "Jordan Ellis")
    recipient_dept  = (
        employee_profile.get("department")
        or employee_profile.get("title")
        or "General Staff"
    )
    t_domain = target_domain or employee_profile.get("company_name") or "company.com"

    system_prompt = (
        "You are an expert AI cybersecurity trainer.\n"
        "Generate a game pair consisting of:\n"
        "1. A realistic phishing email ('phish')\n"
        "2. A genuine-looking legitimate email ('legit')\n\n"
        "CRITICAL REQUIREMENT: Both emails MUST share the exact same sender persona, department, and specific topic "
        "(e.g. both about an IT password/SSO maintenance issue, or both about invoice payment confirmation, or both about payroll direct deposit). "
        "They must be genuinely hard to distinguish, differing only in subtle psychological phishing triggers "
        "(e.g. artificial urgency, panic deadline, or PHISHING_LINK in the phish vs standard internal company procedures in the legit email).\n\n"
        f"Recipient: {recipient_name} | Department: {recipient_dept} | Domain: {t_domain}\n"
        f"Scenario/Topic area: {scenario}\n\n"
        "You must respond with ONLY a single JSON object. No markdown formatting (like ```json), "
        "no explanation. The JSON response schema must be exactly:\n"
        "{\n"
        '  "phish": {\n'
        '    "subject": "email subject",\n'
        '    "sender_display": "Sender Name",\n'
        '    "body_text": "Phishing body text. Reference recipient name and department. Include visit PHISHING_LINK.",\n'
        '    "phishing_tactic": "explanation of tactic",\n'
        '    "bait_score": {\n'
        '      "urgency": 85,\n'
        '      "authority": 70,\n'
        '      "believability": 80,\n'
        '      "obfuscation": 55,\n'
        '      "personalization": 75\n'
        '    }\n'
        '  },\n'
        '  "legit": {\n'
        '    "subject": "legitimate email subject",\n'
        '    "sender_display": "Sender Name",\n'
        '    "body_text": "Legitimate body text. Reference recipient name and department. NO phishing links."\n'
        '  }\n'
        "}\n\n"
        "FEW-SHOT EXAMPLE:\n"
        "{\n"
        '  "phish": {\n'
        '    "subject": "Urgent: Direct Deposit Discrepancy - Action Required",\n'
        '    "sender_display": "HR Benefits & Payroll",\n'
        '    "body_text": "Hi Jane,\\n\\nWe noticed a routing discrepancy with your bank account details for the Finance payroll cycle. To avoid a delay in salary disbursement, log in immediately: visit PHISHING_LINK.\\n\\nThanks,\\nHR Payroll Team",\n'
        '    "phishing_tactic": "Creates false payroll panic to coerce the user into clicking a credential harvesting link.",\n'
        '    "bait_score": {\n'
        '      "urgency": 90,\n'
        '      "authority": 75,\n'
        '      "believability": 85,\n'
        '      "obfuscation": 50,\n'
        '      "personalization": 80\n'
        '    }\n'
        '  },\n'
        '  "legit": {\n'
        '    "subject": "Annual Direct Deposit & Benefits Verification Period",\n'
        '    "sender_display": "HR Benefits & Payroll",\n'
        '    "body_text": "Dear Jane,\\n\\nThe annual verification window for direct deposit and benefits for the Finance department is now open. You can review your details anytime on the internal intranet portal.\\n\\nWarmly,\\nHR Payroll Team"\n'
        '  }\n'
        "}"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": "Generate the game round email pair JSON now."},
    ]

    t0 = time.time()
    raw = _call_with_fallback(messages)
    duration_ms = int((time.time() - t0) * 1000)

    if not raw:
        return get_static_game_fallback(employee_profile, scenario)

    parsed = _parse_game_json_response(raw)
    if parsed:
        ph = parsed["phish"]
        lg = parsed["legit"]

        # Ensure display names exist
        ph.setdefault("sender_name", ph.get("sender_display", "IT Support"))
        lg.setdefault("sender_name", lg.get("sender_display", ph.get("sender_display", "IT Support")))
        
        # Ensure tactic/breakdown exists
        ph.setdefault("educational_breakdown", ph.get("phishing_tactic", "Always verify unexpected links."))
        
        # Validate bait score
        raw_bait_score = ph.get("bait_score")
        validated_bait = validate_bait_score(raw_bait_score)
        if validated_bait:
            ph["bait_score"] = validated_bait
        else:
            ph.pop("bait_score", None)

        # Clean both of disclosures
        clean_ph = clean_email_data(ph.copy())
        clean_lg = clean_email_data(lg.copy())

        # Generate HTML content
        clean_ph["body_html"] = _text_to_html(clean_ph["body_text"])
        clean_lg["body_html"] = _text_to_html(clean_lg["body_text"])

        return {
            "success": True,
            "phish": clean_ph,
            "legit": clean_lg,
            "duration_ms": duration_ms
        }

    print(f"[email_gen] Game JSON parse failed. Raw snippet:\n{raw[:400]}")
    return get_static_game_fallback(employee_profile, scenario)


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
    scenario = "ceo_fraud"
    result = generate_game_round(test_employee, scenario)
    print(json.dumps(result, indent=4, ensure_ascii=False))
