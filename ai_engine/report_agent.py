import json
import os
import re
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
    timeout=float(os.getenv("OPENROUTER_TIMEOUT_SECONDS", "10")),
) if OPENROUTER_API_KEY else None


def compute_human_security_score(click_rate, open_rate, report_rate, repeat_pct=0):
    """Human Security Score™ — single 0-100 number for the organisation.

    Scoring model (designed to feel meaningful to executives):
      Start:             100 points
      Click penalty:    -40 pts max  (click_rate/100 * 40)
      Open penalty:     -10 pts max  (open_rate/100 * 10)
      Report bonus:     +20 pts max  (report_rate/100 * 20)
      Repeat penalty:   -15 pts max  (repeat_pct/100 * 15)
    Clamped to [0, 100].
    """
    score = 100
    score -= (click_rate  / 100) * 40
    score -= (open_rate   / 100) * 10
    score += (report_rate / 100) * 20
    score -= (repeat_pct  / 100) * 15
    score = max(0, min(100, round(score)))

    if score >= 70:
        tier  = "green"
        label = "Good"
    elif score >= 40:
        tier  = "amber"
        label = "At Risk"
    else:
        tier  = "red"
        label = "Critical"

    return {"score": score, "tier": tier, "label": label}


def build_campaign_report(campaign):
    """Creates an Agentic AI campaign report using LLM analysis on tracked metrics."""
    employees = int(campaign.get("employee_count") or 0)
    sent = int(campaign.get("emails_sent") or 0)
    failed = int(campaign.get("emails_failed") or 0)
    opens = int(campaign.get("opens") or 0)
    clicks = int(campaign.get("clicks") or 0)
    reports = int(campaign.get("reports") or 0)

    open_rate = round((opens / sent) * 100, 1) if sent else 0
    click_rate = round((clicks / sent) * 100, 1) if sent else 0
    report_rate = round((reports / sent) * 100, 1) if sent else 0
    delivery_rate = round((sent / employees) * 100, 1) if employees else 0

    # Repeat offender percentage (passed in from campaign dict if available)
    repeat_pct = float(campaign.get("repeat_pct") or 0)
    hss = compute_human_security_score(click_rate, open_rate, report_rate, repeat_pct)

    if click_rate >= 35 or (clicks >= reports * 3 and clicks > 0):
        risk_level = "High"
    elif click_rate >= 15:
        risk_level = "Medium"
    elif reports > clicks and reports > 0:
        risk_level = "Low"
    else:
        risk_level = "Watch"

    # --- Agentic AI Analysis ---
    prompt = f"""You are an elite Cybersecurity Analyst AI for PhishSim.
Analyze these phishing simulation results for '{campaign.get('name', 'Campaign')}':
- Scenario: {campaign.get('scenario_type', 'Unknown').replace('_', ' ')}
- Delivery Rate: {delivery_rate}% ({sent} out of {employees} delivered, {failed} failed)
- Open Rate: {open_rate}% ({opens} opened)
- Click Rate (Vulnerable): {click_rate}% ({clicks} clicked the malicious link)
- Report Rate (Secure): {report_rate}% ({reports} reported it to IT)
- Human Security Score™: {hss['score']}/100 ({hss['label']})

Write a highly professional, agentic AI threat analysis. Do not use generic filler. Be specific about the scenario and the numbers.
Provide exactly two things in JSON format:
1. "summary": A 2-3 sentence executive summary analyzing the vulnerability.
2. "recommendations": A list of 3 actionable, specific cybersecurity recommendations based on these exact metrics.

CRITICAL: Return ONLY valid JSON: {{"summary": "...", "recommendations": ["...", "..."]}}""" 

    # --- Scenario-Specific Fallback Definitions ---
    fallback_recos_by_scenario = {
        "sso_credential_harvest": [
            "Mandate Password Managers: Restrict password auto-fill to official domain names only to block credential clones.",
            "Deploy FIDO2/WebAuthn MFA: Hardware keys or device-based MFA block credential replays even if employees click.",
            "SSO Location Anomaly Policies: Enforce automated alerts and verification prompts for login attempts from anomalous regions."
        ],
        "cfo_wire_transfer": [
            "Establish Out-of-Band Approvals: Mandate a secondary verification channel (verbal call or secure chat) for transfers over $5k.",
            "Display Name Spoofing Banners: Implement external sender tags to visually flag external emails masquerading as executives.",
            "Establish CFO Proxy Rules: Define a strict process for wire sign-offs during executive travel or unavailability."
        ],
        "urgent_it_patch": [
            "Verify IT Communication Channels: Educate users that critical patches are never deployed via direct links in emails.",
            "Automate System Updates: Configure MDM / central policy management to apply updates without requiring user action.",
            "Require Admin Credentials: Block standard users from installing software/extensions to neutralize executable downloads."
        ],
        "package_delivery": [
            "Redirect Personal Deliveries: Enforce policy prohibiting personal package delivery tracking to corporate email addresses.",
            "Verify Shipping Origin: Train operations/front-desk staff to verify tracking numbers directly via the carrier's portal.",
            "Block Malicious Redirects: Implement secure DNS resolution (e.g. Quad9) to block connection to simulated delivery domains."
        ],
        "authority_impersonation": [
            "Implement DMARC/DKIM/SPF Policies: Enforce strict quarantine/reject policies to block domain spoofing attempts.",
            "Execute Spoofing Drills: Run targeted awareness sessions on executive writing style, urgency indicators, and protocol bypasses.",
            "Define Executive Contact Protocol: Establish official channels for emergency requests to prevent bypass of standard approvals."
        ]
    }

    fallback_summaries_by_scenario = {
        "sso_credential_harvest": "The campaign detected critical vulnerabilities in credential hygiene. Targeted employees entered single sign-on details on a simulated login clone, exposing the organization to full account compromise.",
        "cfo_wire_transfer": "The CFO impersonation simulation exposed a high susceptibility to urgency-based compliance pressure. High-risk departments bypass standard controls when pressured by executive authority.",
        "urgent_it_patch": "The urgent patch scenario revealed significant gaps in endpoint security compliance. Employees clicked direct installation links, bypassing official software deployment channels.",
        "package_delivery": "The package delivery lure successfully exploited curiosity and personal interest. This threat vector bypasses standard corporate filters by mimicking routine courier tracking updates.",
        "authority_impersonation": "The authority impersonation exercise highlights critical vulnerabilities to organizational hierarchy pressure. Attackers successfully leveraged urgency cues to bypass standard verification protocols."
    }

    scenario_key = campaign.get("scenario_type") or "authority_impersonation"
    if scenario_key not in fallback_recos_by_scenario:
        scenario_key = "authority_impersonation"

    summary = fallback_summaries_by_scenario[scenario_key]
    recommendations = fallback_recos_by_scenario[scenario_key]

    try:
        if client is None:
            raise RuntimeError("OPENROUTER_API_KEY is not configured.")
        
        # Try primary model first, then fallback model
        response = None
        for model_name in ["google/gemini-2.5-flash", "openrouter/free"]:
            try:
                response = client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": "You are an AI Threat Analyst. Output ONLY raw JSON. No markdown, no <think> tags."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.3,
                    max_tokens=400
                )
                if response and response.choices and response.choices[0].message.content:
                    break
            except Exception as model_err:
                print(f"Failed model call for {model_name}: {model_err}")
                continue

        if not response:
            raise RuntimeError("All models failed or returned empty response.")

        raw = response.choices[0].message.content
        raw = re.sub(r'<think>.*?</think>', '', raw, flags=re.DOTALL).strip()
        
        # Extract markdown json block if present
        code_block = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', raw, re.DOTALL)
        if code_block:
            json_str = code_block.group(1)
        else:
            json_str = raw

        # Parse robustly
        start_idx = json_str.find('{')
        while start_idx != -1:
            end_idx = json_str.rfind('}')
            if end_idx > start_idx:
                try:
                    candidate = json.loads(json_str[start_idx:end_idx+1])
                    if "summary" in candidate and "recommendations" in candidate:
                        summary = candidate["summary"]
                        recommendations = candidate["recommendations"]
                        break
                except json.JSONDecodeError:
                    pass
            start_idx = json_str.find('{', start_idx + 1)
            
    except Exception as e:
        print(f"AI Report Generation Failed, falling back to scenario defaults: {e}")

    return {
        "risk_level": risk_level,
        "summary": summary,
        "delivery_rate": delivery_rate,
        "open_rate": open_rate,
        "click_rate": click_rate,
        "report_rate": report_rate,
        "recommendations": recommendations,
        "hss": hss,
    }
