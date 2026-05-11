import json
import os
import re
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY")
)


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

    fallback_summary = "The campaign shows measurable risk and needs targeted follow-up training."
    fallback_recos = [
        "Review email deliverability and image blocking rules.",
        "Run short training on link checking and urgency cues.",
        "Make the reporting process easier for employees."
    ]

    summary = fallback_summary
    recommendations = fallback_recos

    try:
        response = client.chat.completions.create(
            model="openrouter/free",
            messages=[
                {"role": "system", "content": "You are an AI Threat Analyst. Output ONLY raw JSON. No markdown, no <think> tags."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=300
        )
        
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
        print(f"AI Report Generation Failed: {e}")

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
