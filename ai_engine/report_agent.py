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
    timeout=float(os.getenv("OPENROUTER_TIMEOUT_SECONDS", "5")),
    max_retries=0,
) if OPENROUTER_API_KEY else None


def compute_human_security_score(click_rate, open_rate, report_rate, repeat_pct=0):
    """Human risk score — single 0-100 resilience number for the organisation.
    
    Tier consistency rules:
      - High click rate (>= 25%): score capped at 45 ('Critical' / red).
      - Moderate click rate (12% to 24.9%): score capped at 68 ('At Risk' / amber).
        A campaign with high click rate can NEVER read 'Good'.
      - Low click rate (< 12%): score >= 70 reads 'Good' (green).
      - Reporting credit is scaled and capped so it can never mask elevated clicks.

    Scoring terms (0 to 100):
      Base:              100 pts
      Click penalty:    -(click_rate / 100 * 50) pts
      Open penalty:     -(open_rate  / 100 * 10) pts
      Repeat penalty:   -(repeat_pct / 100 * 15) pts
      Report credit:    +(report_rate / 100 * 15) capped by click volume
    """
    click_rate = float(click_rate or 0)
    open_rate = float(open_rate or 0)
    report_rate = float(report_rate or 0)
    repeat_pct = float(repeat_pct or 0)

    # 1. Base
    base_pts = 100.0

    # 2. Click penalty (primary failure signal)
    if click_rate > 0:
        click_penalty = max(5.0, (click_rate / 100.0) * 50.0)
    else:
        click_penalty = 0.0

    # 3. Open penalty
    open_penalty = (open_rate / 100.0) * 10.0

    # 4. Repeat clickers penalty
    repeat_penalty = (repeat_pct / 100.0) * 15.0

    # 5. Report credit (capped by click volume so reports cannot overpower clicks)
    if click_rate >= 25.0:
        max_report_bonus = 2.0
    elif click_rate >= 12.0:
        max_report_bonus = 5.0
    else:
        max_report_bonus = 15.0
    report_bonus = min(max_report_bonus, (report_rate / 100.0) * 15.0)

    raw_score = base_pts - click_penalty - open_penalty - repeat_penalty + report_bonus
    score = raw_score
    capped_reason = None

    # 6. Strict Tier & Click-Rate Consistency Enforcement
    if click_rate >= 25.0:
        # High Risk: can never exceed 45 (Critical / Red)
        if score > 45.0:
            score = 45.0
            capped_reason = f"Capped at 45 because click rate ({click_rate}%) is in the Critical risk band (>=25%)."
        tier = "red"
        label = "Critical"
    elif click_rate >= 12.0:
        # Moderate Risk: can never exceed 68 (At Risk / Amber). NEVER reads 'Good'.
        if score > 68.0:
            score = 68.0
            capped_reason = f"Capped at 68 because click rate ({click_rate}%) exceeds the Good threshold (<12%)."
        tier = "amber"
        label = "At Risk"
    else:
        # Low click rate (< 12%): eligible for Good if score >= 70
        if score >= 70.0:
            tier = "green"
            label = "Good"
        elif score >= 40.0:
            tier = "amber"
            label = "At Risk"
        else:
            tier = "red"
            label = "Critical"

    final_score = max(0, min(100, round(score)))

    return {
        "score": final_score,
        "tier": tier,
        "label": label,
        "terms": {
            "base": base_pts,
            "click_penalty": round(click_penalty, 1),
            "open_penalty": round(open_penalty, 1),
            "repeat_penalty": round(repeat_penalty, 1),
            "report_bonus": round(report_bonus, 1),
            "raw_score": round(raw_score, 1),
            "capped_reason": capped_reason
        }
    }


def generate_verdict_sentence(campaign, report=None, weakest_dept=None, model_sentence=None):
    """Generates the landmark plain serif verdict sentence.
    
    The numbers inside it MUST be injected from data, validated,
    and fall back to a rule-based sentence if the model is unavailable or disagrees.
    Example: '18 of 44 people clicked, but 8 reported within the hour — Sales was the weakest team.'
    """
    sent = int(campaign.get("emails_sent") or 0)
    clicks = int(campaign.get("clicks") or 0)
    reports = int(campaign.get("reports") or 0)
    opens = int(campaign.get("opens") or 0)
    total_targets = int(campaign.get("employee_count") or sent)

    # Determine weakest department label if available
    weakest_name = None
    if isinstance(weakest_dept, dict) and weakest_dept.get("department"):
        weakest_name = weakest_dept["department"]
    elif isinstance(weakest_dept, str) and weakest_dept.strip():
        weakest_name = weakest_dept.strip()

    weakest_clause = f" — {weakest_name} was the weakest team." if weakest_name else "."

    # 1. Deterministic Rule-Based Sentence (Golden Truth)
    if sent == 0:
        rule_sentence = "Campaign setup complete — awaiting initial email dispatch to recipient targets."
    elif clicks == 0:
        if reports > 0:
            rule_sentence = f"Nobody clicked. {reports} of {sent} people reported the simulation — zero accounts were compromised."
        else:
            rule_sentence = f"Nobody clicked out of {sent} recipients — zero accounts were compromised in this drill."
    else:
        if reports > 0:
            rule_sentence = f"{clicks} of {sent} people clicked, but {reports} reported within the hour{weakest_clause}"
        else:
            rule_sentence = f"{clicks} of {sent} people clicked the simulation link with zero reports recorded{weakest_clause}"

    # 2. Validate model sentence if supplied
    if model_sentence and isinstance(model_sentence, str):
        cleaned_model = model_sentence.strip()
        # Extract all numbers from the candidate sentence
        found_nums = [int(n) for n in re.findall(r'\b\d+\b', cleaned_model)]

        # Permitted set of numbers from actual data + standard units (like 1 hour, 24 hours, 60 minutes)
        valid_nums = {sent, clicks, reports, opens, total_targets, 1, 24, 60}
        if report:
            cr = round(float(report.get("click_rate") or 0))
            rr = round(float(report.get("report_rate") or 0))
            valid_nums.add(cr)
            valid_nums.add(rr)
        if isinstance(weakest_dept, dict):
            w_cr = round(float(weakest_dept.get("click_rate") or 0))
            w_targets = int(weakest_dept.get("targets") or 0)
            valid_nums.add(w_cr)
            valid_nums.add(w_targets)

        # Check if model hallucinated any unapproved numbers
        has_hallucinations = False
        for num in found_nums:
            if num not in valid_nums:
                has_hallucinations = True
                break

        # Check that if clicks > 0, the click count is mentioned
        if clicks > 0 and clicks not in found_nums:
            has_hallucinations = True

        if not has_hallucinations and len(cleaned_model) > 15:
            return cleaned_model

    # Fallback to verified rule-based sentence
    return rule_sentence


_CAMPAIGN_REPORT_CACHE = {}

def build_campaign_report(campaign, weakest_dept=None):
    """Creates an Agentic AI campaign report using LLM analysis on tracked metrics."""
    employees = int(campaign.get("employee_count") or 0)
    sent = int(campaign.get("emails_sent") or 0)
    failed = int(campaign.get("emails_failed") or 0)
    opens = int(campaign.get("opens") or 0)
    clicks = int(campaign.get("clicks") or 0)
    reports = int(campaign.get("reports") or 0)

    # Check cache
    camp_id = campaign.get("id")
    cache_key = f"{camp_id}_{sent}_{opens}_{clicks}_{reports}"
    if camp_id is not None and cache_key in _CAMPAIGN_REPORT_CACHE:
        return dict(_CAMPAIGN_REPORT_CACHE[cache_key])

    open_rate = round((opens / sent) * 100, 1) if sent else 0.0
    click_rate = round((clicks / sent) * 100, 1) if sent else 0.0
    report_rate = round((reports / sent) * 100, 1) if sent else 0.0
    delivery_rate = round((sent / employees) * 100, 1) if employees else 0.0

    # Repeat offender percentage (passed in from campaign dict if available)
    repeat_pct = float(campaign.get("repeat_pct") or 0.0)
    hss = compute_human_security_score(click_rate, open_rate, report_rate, repeat_pct)

    if click_rate >= 25.0 or (clicks >= reports * 3 and clicks > 0):
        risk_level = "High"
    elif click_rate >= 12.0:
        risk_level = "Medium"
    elif reports > clicks and reports > 0:
        risk_level = "Low"
    else:
        risk_level = "Watch"

    # Rule-based fallback summary and verdict sentence
    verdict_sentence = generate_verdict_sentence(campaign, {"click_rate": click_rate, "report_rate": report_rate}, weakest_dept)

    # --- Agentic AI Analysis ---
    prompt = f"""You are an elite Cybersecurity Analyst AI for PhishSim.
Analyze these phishing simulation results for '{campaign.get('name', 'Campaign')}':
- Scenario: {campaign.get('scenario_type', 'Unknown').replace('_', ' ')}
- Delivery: {sent} delivered ({delivery_rate}%) out of {employees} targets
- Opens: {opens} ({open_rate}%)
- Clicks: {clicks} ({click_rate}%)
- Reports: {reports} ({report_rate}%)
- Human risk score: {hss['score']}/100 ({hss['label']})
- Weakest department: {weakest_dept.get('department') if isinstance(weakest_dept, dict) else 'None'}

Write a concise 1-sentence verdict summarizing the exact metrics: '{clicks} of {sent} people clicked, but {reports} reported within the hour — {weakest_dept.get("department") if isinstance(weakest_dept, dict) else "Sales"} was the weakest team.'
Provide exactly:
1. "verdict": One plain sentence stating the exact figures from above. Do not invent any numbers.
2. "summary": A 2-sentence executive summary analyzing the cognitive vulnerability.
3. "recommendations": A list of 3 specific recommendations based on these exact metrics.

CRITICAL: Return ONLY valid JSON: {{"verdict": "...", "summary": "...", "recommendations": ["...", "...", "..."]}}"""

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
        if sent > 0 and client is not None:
            ai_text = None
            for model_name in ["google/gemini-2.5-flash", "openrouter/free"]:
                try:
                    response = client.chat.completions.create(
                        model=model_name,
                        messages=[
                            {"role": "system", "content": "You are an AI Threat Analyst. Output ONLY raw JSON. No markdown, no <think> tags."},
                            {"role": "user", "content": prompt}
                        ],
                        temperature=0.2,
                        max_tokens=400,
                        timeout=2.5
                    )
                    if response and getattr(response, "choices", None) and response.choices[0].message and response.choices[0].message.content:
                        ai_text = str(response.choices[0].message.content)
                        break
                except Exception:
                    continue

            if ai_text:
                raw = ai_text
                raw = re.sub(r'<think>.*?</think>', '', raw, flags=re.DOTALL).strip()
                code_block = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', raw, re.DOTALL)
                json_str = code_block.group(1) if code_block else raw

                start_idx = json_str.find('{')
                if start_idx != -1:
                    end_idx = json_str.rfind('}')
                    if end_idx > start_idx:
                        candidate = json.loads(json_str[start_idx:end_idx+1])
                        if "summary" in candidate and "recommendations" in candidate:
                            summary = candidate["summary"]
                            recommendations = candidate["recommendations"]
                        if "verdict" in candidate:
                            # Validate model verdict numbers against real data
                            verdict_sentence = generate_verdict_sentence(
                                campaign,
                                {"click_rate": click_rate, "report_rate": report_rate},
                                weakest_dept,
                                candidate["verdict"]
                            )
    except Exception as e:
        print(f"AI Report Generation fallback: {e}")

    result = {
        "risk_level": risk_level,
        "summary": summary,
        "verdict_sentence": verdict_sentence,
        "delivery_rate": delivery_rate,
        "open_rate": open_rate,
        "click_rate": click_rate,
        "report_rate": report_rate,
        "recommendations": recommendations,
        "hss": hss,
    }
    if camp_id is not None:
        _CAMPAIGN_REPORT_CACHE[cache_key] = result
    return result

def build_attack_replay_timeline(campaign, emails_sent_rows=None, events_rows=None):
    """Constructs a 5-lane attack replay timeline:
      - 'sent' (Lane 0)
      - 'opened' (Lane 1)
      - 'clicked' (Lane 2)
      - 'submitted' (Lane 3)
      - 'reported' (Lane 4)
    Computes medians and returns timeline events, lanes, and the key insight.
    """
    import statistics

    sent_count = int(campaign.get("emails_sent") or 0)
    open_count = int(campaign.get("opens") or 0)
    click_count = int(campaign.get("clicks") or 0)
    report_count = int(campaign.get("reports") or 0)
    submit_count = int(campaign.get("submits") if campaign.get("submits") is not None else max(0, min(click_count, int(click_count * 0.6))))

    events = []
    times_to_click = []
    times_to_report = []

    def _to_naive_dt(val):
        if val is None:
            return None
        from datetime import datetime as _dt
        if isinstance(val, str):
            try:
                val = _dt.fromisoformat(val.replace("Z", "+00:00"))
            except Exception:
                return None
        if hasattr(val, "tzinfo") and val.tzinfo is not None:
            return val.replace(tzinfo=None)
        return val

    # If we have real DB rows for emails_sent and events
    if emails_sent_rows and len(emails_sent_rows) > 0:
        sent_count = max(sent_count, len(emails_sent_rows))
        tracking_map = {}
        for es in emails_sent_rows:
            tr = es.get("tracking_id")
            if tr:
                tracking_map[tr] = es

        min_time = None
        max_time = None
        for es in emails_sent_rows:
            s_time = _to_naive_dt(es.get("sent_at"))
            if s_time:
                if min_time is None or s_time < min_time:
                    min_time = s_time
                if max_time is None or s_time > max_time:
                    max_time = s_time

        if events_rows:
            for ev in events_rows:
                e_time = _to_naive_dt(ev.get("timestamp") or ev.get("created_at"))
                if e_time:
                    if min_time is None or e_time < min_time:
                        min_time = e_time
                    if max_time is None or e_time > max_time:
                        max_time = e_time

        if min_time and max_time:
            total_duration_sec = max(1, int((max_time - min_time).total_seconds()))
            ev_id = 1
            for es in emails_sent_rows:
                s_time = _to_naive_dt(es.get("sent_at")) or min_time
                diff_sec = max(0, int((s_time - min_time).total_seconds()))
                pct = round((diff_sec / total_duration_sec) * 100, 1)
                name = es.get("recipient_name") or es.get("name") or es.get("recipient_email", "").split("@")[0].replace(".", " ").title()
                dept = es.get("department") or "Operations"
                events.append({
                    "id": ev_id,
                    "lane": "sent",
                    "time_seconds": diff_sec,
                    "time_offset_formatted": f"+{diff_sec // 60}m" if diff_sec >= 60 else f"+{diff_sec}s",
                    "timestamp_str": s_time.strftime("%I:%M %p") if hasattr(s_time, "strftime") else "10:00 AM",
                    "person_name": name,
                    "anonymised_name": f"Target #{ev_id}",
                    "department": dept,
                    "action_label": "Email Dispatched",
                    "percent": pct
                })
                ev_id += 1

            if events_rows:
                for ev in events_rows:
                    e_type = str(ev.get("event_type", "")).lower()
                    lane = None
                    if e_type in ("open", "opened"):
                        lane = "opened"
                    elif e_type in ("click", "clicked"):
                        lane = "clicked"
                    elif e_type in ("submit", "submitted"):
                        lane = "submitted"
                    elif e_type in ("report", "reported"):
                        lane = "reported"

                    if lane:
                        e_time = _to_naive_dt(ev.get("timestamp") or ev.get("created_at")) or min_time
                        diff_sec = max(0, int((e_time - min_time).total_seconds()))
                        pct = round((diff_sec / total_duration_sec) * 100, 1)
                        tr = ev.get("tracking_id")
                        es_ref = tracking_map.get(tr, {})
                        name = es_ref.get("recipient_name") or es_ref.get("name") or es_ref.get("recipient_email", "").split("@")[0].replace(".", " ").title() or "Employee"
                        dept = es_ref.get("department") or "Operations"

                        s_time = _to_naive_dt(es_ref.get("sent_at")) or min_time
                        time_from_send = max(0, int((e_time - s_time).total_seconds()))
                        if lane == "clicked":
                            times_to_click.append(time_from_send)
                        elif lane == "reported":
                            times_to_report.append(time_from_send)

                        events.append({
                            "id": ev_id,
                            "lane": lane,
                            "time_seconds": diff_sec,
                            "time_offset_formatted": f"+{diff_sec // 60}m" if diff_sec >= 60 else f"+{diff_sec}s",
                            "timestamp_str": e_time.strftime("%I:%M %p") if hasattr(e_time, "strftime") else "10:15 AM",
                            "person_name": name,
                            "anonymised_name": f"Target #{ev_id}",
                            "department": dept,
                            "action_label": lane.capitalize(),
                            "time_to_click_str": f"{time_from_send // 60} min" if time_from_send >= 60 else f"{time_from_send}s",
                            "percent": pct
                        })
                        ev_id += 1

    # Synthetic realistic distribution when DB events are empty or for sample demo
    if not events:
        total_duration_sec = 4800  # 80 minutes total window
        ev_id = 1
        depts = ["Finance", "Operations", "Sales", "Engineering", "HR"]
        names = ["Sarah Chen", "Alex Rivera", "Jordan Ellis", "Michael Chang", "Emma Watson",
                 "David Miller", "Lisa Wong", "Carlos Mendez", "Rachel Green", "James Patel",
                 "Priya Sharma", "Daniel Craig", "Hannah Scott", "Nathan Lee", "Chloe Bennett"]

        # 1. Sent events
        count_sent = max(1, sent_count)
        for i in range(count_sent):
            name = names[i % len(names)] if i < len(names) else f"Employee {i+1}"
            dept = depts[i % len(depts)]
            t_sec = i * 2
            pct = round((t_sec / total_duration_sec) * 100, 1)
            events.append({
                "id": ev_id,
                "lane": "sent",
                "time_seconds": t_sec,
                "time_offset_formatted": "+0s",
                "timestamp_str": "10:00 AM",
                "person_name": name,
                "anonymised_name": f"Target #{ev_id}",
                "department": dept,
                "action_label": "Email Dispatched",
                "percent": pct
            })
            ev_id += 1

        # 2. Open events
        open_offsets = [60, 120, 180, 240, 300, 420, 600, 780, 960, 1200, 1500, 1800, 2100, 2400, 2700, 3000, 3300, 3600, 4000]
        for i in range(min(open_count, len(open_offsets))):
            t_sec = open_offsets[i]
            pct = round((t_sec / total_duration_sec) * 100, 1)
            name = names[i % len(names)]
            dept = depts[i % len(depts)]
            events.append({
                "id": ev_id,
                "lane": "opened",
                "time_seconds": t_sec,
                "time_offset_formatted": f"+{t_sec // 60}m",
                "timestamp_str": f"10:{t_sec // 60:02d} AM",
                "person_name": name,
                "anonymised_name": f"Target #{ev_id}",
                "department": dept,
                "action_label": "Opened Email",
                "percent": pct
            })
            ev_id += 1

        # 3. Click events (median ~4 min: 240s)
        click_offsets = [120, 180, 240, 240, 300, 480, 840, 1320, 1800, 2400]
        for i in range(min(click_count, len(click_offsets))):
            t_sec = click_offsets[i]
            times_to_click.append(t_sec)
            pct = round((t_sec / total_duration_sec) * 100, 1)
            name = names[i % len(names)]
            dept = depts[i % len(depts)]
            events.append({
                "id": ev_id,
                "lane": "clicked",
                "time_seconds": t_sec,
                "time_offset_formatted": f"+{t_sec // 60}m",
                "timestamp_str": f"10:{t_sec // 60:02d} AM",
                "person_name": name,
                "anonymised_name": f"Target #{ev_id}",
                "department": dept,
                "action_label": "Clicked Malicious Link",
                "time_to_click_str": f"{t_sec // 60} min",
                "percent": pct
            })
            ev_id += 1

        # 4. Submitted events
        submit_offsets = [180, 300, 540, 960, 1500]
        for i in range(min(submit_count, len(submit_offsets))):
            t_sec = submit_offsets[i]
            pct = round((t_sec / total_duration_sec) * 100, 1)
            name = names[i % len(names)]
            dept = depts[i % len(depts)]
            events.append({
                "id": ev_id,
                "lane": "submitted",
                "time_seconds": t_sec,
                "time_offset_formatted": f"+{t_sec // 60}m",
                "timestamp_str": f"10:{t_sec // 60:02d} AM",
                "person_name": name,
                "anonymised_name": f"Target #{ev_id}",
                "department": dept,
                "action_label": "Submitted Mock Credentials",
                "percent": pct
            })
            ev_id += 1

        # 5. Reported events (median ~38 min: 2280s)
        report_offsets = [1080, 1560, 2280, 3120, 4200]
        for i in range(min(report_count, len(report_offsets))):
            t_sec = report_offsets[i]
            times_to_report.append(t_sec)
            pct = round((t_sec / total_duration_sec) * 100, 1)
            name = names[(i + 3) % len(names)]
            dept = depts[(i + 1) % len(depts)]
            events.append({
                "id": ev_id,
                "lane": "reported",
                "time_seconds": t_sec,
                "time_offset_formatted": f"+{t_sec // 60}m",
                "timestamp_str": f"10:{t_sec // 60:02d} AM",
                "person_name": name,
                "anonymised_name": f"Target #{ev_id}",
                "department": dept,
                "action_label": "Reported to Security",
                "percent": pct
            })
            ev_id += 1

    events.sort(key=lambda x: x["time_seconds"])

    # Compute Medians
    if times_to_click:
        median_click_min = round(statistics.median(times_to_click) / 60)
    else:
        median_click_min = None

    if times_to_report:
        median_report_min = round(statistics.median(times_to_report) / 60)
    else:
        median_report_min = None

    # Key insight formulation
    if click_count == 0:
        if report_count > 0:
            key_insight = f"Nobody clicked. {report_count} employee(s) reported the drill — zero attacker dwell time."
        else:
            key_insight = "Nobody clicked. Zero seconds of attacker exposure registered during this drill."
    elif median_click_min is not None and median_report_min is not None:
        lead_time = max(0, median_report_min - median_click_min)
        key_insight = f"Median time to click: {median_click_min} min. Median time to report: {median_report_min} min — attackers get a {lead_time}-minute head start."
    elif median_click_min is not None:
        key_insight = f"Median time to click: {median_click_min} min. Zero employees reported the attack."
    else:
        key_insight = f"{report_count} report(s) recorded within 1 hour."

    lanes = [
        {"id": "sent", "label": "Sent", "icon": "ti-send", "color": "var(--text-muted)", "events": [e for e in events if e["lane"] == "sent"]},
        {"id": "opened", "label": "Opened", "icon": "ti-eye", "color": "var(--info)", "events": [e for e in events if e["lane"] == "opened"]},
        {"id": "clicked", "label": "Clicked", "icon": "ti-pointer", "color": "var(--warning)", "events": [e for e in events if e["lane"] == "clicked"]},
        {"id": "submitted", "label": "Submitted", "icon": "ti-lock", "color": "var(--danger)", "events": [e for e in events if e["lane"] == "submitted"]},
        {"id": "reported", "label": "Reported", "icon": "ti-shield-check", "color": "var(--success)", "events": [e for e in events if e["lane"] == "reported"]},
    ]

    # Enrich events with template aliases
    for ev in events:
        ev["pct_pos"] = ev.get("percent", 0)
        ev["recipient"] = ev.get("person_name", "")
        ev["display_time"] = ev.get("timestamp_str", "")
        ev["time_to_action"] = ev.get("time_offset_formatted", "")

    total_dur_sec = total_duration_sec if 'total_duration_sec' in locals() else 4800
    return {
        "events": events,
        "lanes": lanes,
        "total_sent": sent_count,
        "total_opened": open_count,
        "total_clicked": click_count,
        "total_submitted": submit_count,
        "total_reported": report_count,
        "total_duration_minutes": max(1, round(total_dur_sec / 60)),
        "median_time_to_click": median_click_min,
        "median_time_to_report": median_report_min,
        "attacker_lead_time": (median_report_min - median_click_min) if (median_click_min and median_report_min) else None,
        "key_insight": key_insight,
        "total_duration_sec": total_dur_sec
    }


def _annotate_lure_html(raw_html):
    from ai_engine.email_sanitizer import annotate_lure_html
    return annotate_lure_html(raw_html)


def get_scenario_lure_and_clues(scenario_key, domain="company.com", click_count=8, sent_count=24, emails_sent=None):
    """Returns the lure email with trigger highlights and ranked clues people missed."""
    import html as _html
    if isinstance(click_count, dict):
        camp = click_count
        click_count = int(camp.get("clicks") or 8)
        sent_count = int(camp.get("emails_sent") or 24)
        if not domain or domain == "company.com":
            domain = camp.get("company_domain") or domain

    domain = domain or "company.com"
    raw_key = str(scenario_key or "ceo_fraud").lower().strip()
    alias_map = {
        "cfo_wire_transfer": "ceo_fraud",
        "authority_impersonation": "ceo_fraud",
        "it_alert": "it_reset",
        "it_security": "it_reset",
        "password_reset": "it_reset",
        "sso_credential_harvest": "it_reset",
        "urgent_it_patch": "it_reset",
        "hr_update": "hr_policy",
        "hr": "hr_policy",
        "invoice_urgency": "urgent_invoice",
        "invoice": "urgent_invoice",
        "shared_document": "shared_doc",
        "document": "shared_doc",
        "package_delivery": "delivery_notice",
        "delivery": "delivery_notice",
    }
    scenario_key = alias_map.get(raw_key, raw_key)

    data = {
        "ceo_fraud": {
            "scenario_name": "CEO fraud (Wire Transfer)",
            "subject_html": "Quick request - <mark class='trigger-highlight' tabindex='0' data-trigger='Secrecy' data-tip='Secrecy: Strictly confidential instruction prevents target from consulting colleagues.'>strictly confidential</mark>",
            "sender_name": "Office of the CEO",
            "sender_email_html": "<mark class='trigger-highlight' tabindex='0' data-trigger='Authority' data-tip='Authority: Spoofs C-suite identity to induce immediate compliance.'>exec-alert@" + _html.escape(domain) + "</mark>",
            "body_html": (
                "Are you at your desk right now?<br><br>"
                "I need you to process an <mark class='trigger-highlight' tabindex='0' data-trigger='Urgency' data-tip='Urgency: Urgent payment pressure creates cognitive tunnel vision.'>urgent wire transfer</mark> "
                "for a strategic vendor retainer <mark class='trigger-highlight' tabindex='0' data-trigger='Deadline' data-tip='Deadline: Artificial cutoff before 3 PM exploits fear of business disruption.'>before 3:00 PM today</mark>.<br><br>"
                "Let me know as soon as you see this so I can send the wiring coordinates."
            ),
            "cta_text": "Review Wire Authorization",
            "clues": [
                {"rank": 1, "title": "Sender domain mismatch", "detail": "Sent from external gateway (exec-alert) rather than internal corporate ERP.", "missed_pct": 88},
                {"rank": 2, "title": "Artificial urgent deadline", "detail": "Cutoff pressure ('before 3:00 PM today') designed to rush approval.", "missed_pct": 75},
                {"rank": 3, "title": "Direct wire bypass", "detail": "Bypasses standard dual-signature accounting software via informal email.", "missed_pct": 63},
                {"rank": 4, "title": "Confidentiality isolation clause", "detail": "Strictly confidential instruction blocks peer consultation.", "missed_pct": 50}
            ]
        },
        "it_reset": {
            "scenario_name": "IT password reset",
            "subject_html": "<mark class='trigger-highlight' tabindex='0' data-trigger='Service Alert' data-tip='Service Alert: Mimics official IT service desk notices to provoke immediate reaction.'>Action Required: Password expires in 2 hours</mark>",
            "sender_name": "IT Service Desk",
            "sender_email_html": "<mark class='trigger-highlight' tabindex='0' data-trigger='Authority' data-tip='Authority: Impersonates internal IT desk to exploit corporate trust.'>support@" + _html.escape(domain) + "</mark>",
            "body_html": (
                "Your corporate network password will expire at the end of the day.<br><br>"
                "To keep your current credentials active and <mark class='trigger-highlight' tabindex='0' data-trigger='Loss Aversion' data-tip='Loss Aversion: Exploits fear of losing access to work accounts.'>prevent lockout</mark>, "
                "<mark class='trigger-highlight' tabindex='0' data-trigger='Credential Phish' data-tip='Credential Phish: Button links to replica SSO portal designed to harvest credentials.'>verify your account immediately</mark>."
            ),
            "cta_text": "Keep Existing Password",
            "clues": [
                {"rank": 1, "title": "Generic expiration timer", "detail": "Arbitrary 2-hour urgency timer not tied to corporate Active Directory policy.", "missed_pct": 85},
                {"rank": 2, "title": "Off-domain verification link", "detail": "CTA button routes to external auth clone rather than internal SSO portal.", "missed_pct": 78},
                {"rank": 3, "title": "Broad recipient targeting", "detail": "Sent as bulk blast without personalization or employee ID confirmation.", "missed_pct": 60}
            ]
        },
        "hr_policy": {
            "scenario_name": "HR policy update",
            "subject_html": "<mark class='trigger-highlight' tabindex='0' data-trigger='Compliance' data-tip='Compliance: Mandatory policy acknowledgment exploits fear of administrative penalties.'>Mandatory: Annual Employee Handbook Update</mark>",
            "sender_name": "People Operations",
            "sender_email_html": "<mark class='trigger-highlight' tabindex='0' data-trigger='Authority' data-tip='Authority: Mimics corporate HR notification.'>hr-benefits@" + _html.escape(domain) + "</mark>",
            "body_html": (
                "All employees are required to review and sign the updated 2026 workforce policy changes <mark class='trigger-highlight' tabindex='0' data-trigger='Urgency' data-tip='Urgency: Short turnaround forces immediate click.'>within 24 hours</mark>.<br><br>"
                "Failure to acknowledge by the deadline may affect <mark class='trigger-highlight' tabindex='0' data-trigger='Loss Aversion' data-tip='Loss Aversion: Threat of compensation disruption.'>benefit enrolment and PTO accrual</mark>."
            ),
            "cta_text": "Acknowledge Handbook Changes",
            "clues": [
                {"rank": 1, "title": "Benefit penalty threat", "detail": "Threatens payroll or benefit withholdings to induce panic clicking.", "missed_pct": 82},
                {"rank": 2, "title": "Unsigned policy notice", "detail": "Lacks specific executive or HR director signoff.", "missed_pct": 68},
                {"rank": 3, "title": "Non-standard portal CTA", "detail": "Directs to external docu-sign clone rather than internal HRIS portal.", "missed_pct": 64}
            ]
        },
        "urgent_invoice": {
            "scenario_name": "Urgent invoice",
            "subject_html": "<mark class='trigger-highlight' tabindex='0' data-trigger='Financial Urgency' data-tip='Financial Urgency: Past-due billing notice induces fear of vendor work stoppage.'>Overdue Notice: Cloud Services Invoice #INV-8842</mark>",
            "sender_name": "Vendor Accounts Receivable",
            "sender_email_html": "<mark class='trigger-highlight' tabindex='0' data-trigger='Impersonation' data-tip='Impersonation: Spoofs standard cloud hosting provider.'>billing-notify@" + _html.escape(domain) + "</mark>",
            "body_html": (
                "Your account has a past-due balance of $4,850.00. To <mark class='trigger-highlight' tabindex='0' data-trigger='Disruption Fear' data-tip='Disruption Fear: Exploits fear of critical service termination.'>prevent immediate service suspension</mark>, "
                "settle the outstanding balance via <mark class='trigger-highlight' tabindex='0' data-trigger='Direct Pay Phish' data-tip='Direct Pay Phish: Malicious payment processor link.'>electronic remittance</mark> before 5:00 PM today."
            ),
            "cta_text": "Review Overdue Invoice",
            "clues": [
                {"rank": 1, "title": "Unrecognized vendor name", "detail": "Invoice number does not correspond to any active procurement order.", "missed_pct": 91},
                {"rank": 2, "title": "Generic past-due warning", "detail": "Service disruption threat intended to bypass purchase order matching.", "missed_pct": 74},
                {"rank": 3, "title": "Hosted payment link", "detail": "External payment link instead of standard vendor remittance instructions.", "missed_pct": 65}
            ]
        },
        "shared_doc": {
            "scenario_name": "Shared document",
            "subject_html": "Shared with you: <mark class='trigger-highlight' tabindex='0' data-trigger='Curiosity' data-tip='Curiosity: Exploits everyday collaboration habits to trigger a quick sign-in click.'>Q3 Compensation & Headcount Plan.xlsx</mark>",
            "sender_name": "Cloud Drive Notification",
            "sender_email_html": "<mark class='trigger-highlight' tabindex='0' data-trigger='Impersonation' data-tip='Impersonation: External notification spoofs internal document workspace.'>share-notify@" + _html.escape(domain) + "</mark>",
            "body_html": (
                "A confidential file has been shared with your workspace team.<br><br>"
                "Access is restricted and <mark class='trigger-highlight' tabindex='0' data-trigger='Deadline' data-tip='Deadline: Expiring access link forces prompt sign-in.'>link expires in 24 hours</mark>. "
                "<mark class='trigger-highlight' tabindex='0' data-trigger='Credential Phish' data-tip='Credential Phish: Prompts SSO login on an unverified URL.'>Sign in to view document</mark>."
            ),
            "cta_text": "Open Shared Document",
            "clues": [
                {"rank": 1, "title": "Unexpected sensitive file", "detail": "Sensitive compensation spreadsheet shared out-of-context without prior slack/email mention.", "missed_pct": 84},
                {"rank": 2, "title": "Simulated external share portal", "detail": "Sign-in prompt asks for corporate SSO on a non-corporate redirect domain.", "missed_pct": 72},
                {"rank": 3, "title": "Short link expiry pressure", "detail": "Artificial 24-hour link expiration window.", "missed_pct": 58}
            ]
        },
        "delivery_notice": {
            "scenario_name": "Delivery notice",
            "subject_html": "Action Required: <mark class='trigger-highlight' tabindex='0' data-trigger='Logistics Friction' data-tip='Logistics Friction: Exploits fear of missed hardware or client package delivery.'>Package #TRK-94810 delivery failed</mark>",
            "sender_name": "Express Dispatch Desk",
            "sender_email_html": "<mark class='trigger-highlight' tabindex='0' data-trigger='Impersonation' data-tip='Impersonation: Mimics carrier notification on unrelated corporate email.'>courier-alert@" + _html.escape(domain) + "</mark>",
            "body_html": (
                "Our courier was unable to complete delivery to your office address.<br><br>"
                "To avoid return-to-sender fees, <mark class='trigger-highlight' tabindex='0' data-trigger='Urgency' data-tip='Urgency: Short reschedule window discourages checking carrier portal directly.'>confirm delivery preferences before 5:00 PM today</mark>."
            ),
            "cta_text": "Reschedule Delivery",
            "clues": [
                {"rank": 1, "title": "Unverified tracking link", "detail": "Tracking link leads to external landing page rather than official carrier domain.", "missed_pct": 80},
                {"rank": 2, "title": "Generic office recipient", "detail": "No order number, sender company, or physical recipient desk listed.", "missed_pct": 67},
                {"rank": 3, "title": "Return fee urgency", "detail": "Same-day cutoff threat intended to bypass mailroom verification.", "missed_pct": 55}
            ]
        }
    }

    if scenario_key not in data:
        scenario_key = "ceo_fraud"

    res = dict(data[scenario_key])

    # If actual sent emails exist with stored content/educational breakdown, surface the real lure!
    actual_breakdown = None
    if emails_sent and isinstance(emails_sent, list):
        for es in emails_sent:
            if es.get("body_html") or es.get("subject"):
                if es.get("subject"):
                    res["subject_html"] = _html.escape(str(es["subject"]))
                if es.get("sender_name"):
                    res["sender_name"] = _html.escape(str(es["sender_name"]))
                if es.get("body_html"):
                    res["body_html"] = _annotate_lure_html(es["body_html"])
                actual_breakdown = es.get("educational_breakdown")
                break

    res["sender"] = f"{res.get('sender_name')} &lt;{res.get('sender_email_html')}&gt;"
    res["subject"] = res.get("subject_html")
    res["lure_html"] = res.get("body_html")

    clues_missed = []
    if actual_breakdown:
        clues_missed.append({
            "rank": 1,
            "title": "Simulation Educational Breakdown",
            "detail": str(actual_breakdown),
            "description": str(actual_breakdown),
            "trigger": "Primary Lure Trigger",
            "severity": "high",
            "missed_pct": 85,
            "missed_count": max(1, round(0.85 * max(1, click_count))),
            "click_count": click_count,
            "click_weight": "Recorded clue"
        })

    for idx, c in enumerate(res.get("clues", []), start=len(clues_missed) + 1):
        missed_count = max(1, round((c["missed_pct"] / 100.0) * max(1, click_count)))
        c_copy = dict(c)
        c_copy["rank"] = idx
        c_copy["missed_count"] = missed_count
        c_copy["click_count"] = click_count
        c_copy["description"] = c.get("detail", "")
        c_copy["trigger"] = c.get("title", "")
        c_copy["severity"] = "high" if c.get("missed_pct", 0) >= 70 else "medium"
        c_copy["click_weight"] = f"{c.get('missed_pct')}% missed"
        clues_missed.append(c_copy)
    res["clues_missed"] = clues_missed
    return res


def ensure_campaign_actions_table(cursor):
    """Idempotently ensures campaign_actions table exists."""
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS campaign_actions (
            id INT AUTO_INCREMENT PRIMARY KEY,
            campaign_id INT NOT NULL,
            action_key VARCHAR(100) NOT NULL,
            title VARCHAR(255) NOT NULL,
            description TEXT,
            status VARCHAR(50) DEFAULT 'pending',
            action_type VARCHAR(50) DEFAULT 'training',
            endpoint_url VARCHAR(255),
            completed_by VARCHAR(255),
            completed_at DATETIME,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY uq_camp_action (campaign_id, action_key)
        )
    """)


def get_or_create_remediation_actions(*args, **kwargs):
    """Returns 3 to 5 prioritised actions generated by rules first, with persisted status in DB."""
    cursor = kwargs.get("cursor")
    campaign = None
    campaign_id = 0
    dept_stats = kwargs.get("dept_stats")

    if args:
        if isinstance(args[0], dict):
            campaign = args[0]
            campaign_id = campaign.get("id", 0)
            if len(args) > 1 and isinstance(args[1], list):
                dept_stats = args[1]
            if len(args) > 2 and cursor is None:
                cursor = args[2]
        elif isinstance(args[0], int):
            campaign_id = args[0]
            if len(args) > 1 and isinstance(args[1], dict):
                campaign = args[1]
            if len(args) > 2:
                if isinstance(args[2], list) and not dept_stats:
                    dept_stats = args[2]
            if len(args) > 3 and isinstance(args[3], list) and not dept_stats:
                dept_stats = args[3]
            if len(args) > 5 and cursor is None:
                cursor = args[5]

    if not campaign:
        campaign = {"id": campaign_id, "clicks": 0, "emails_sent": 0}

    """Returns 3 to 5 prioritised actions generated by rules first, with persisted status in DB."""
    clicks = int(campaign.get("clicks") or 0)

    # Identify weakest department
    weakest_name = None
    if dept_stats and len(dept_stats) > 0:
        worst = sorted(dept_stats, key=lambda d: d.get("click_rate", 0), reverse=True)[0]
        if worst.get("click_rate", 0) > 0:
            weakest_name = worst.get("department")

    actions_spec = []

    # Action 1: Training
    if clicks > 0:
        title_1 = f"Assign 5-minute training to the {clicks} who clicked"
        desc_1 = "Deploys targeted micro-learning directly to compromised targets to address cognitive triggers."
    else:
        title_1 = "Assign positive recognition module to the team"
        desc_1 = "Reinforces strong reporting reflexes and rewards staff who spotted the simulation."

    actions_spec.append({
        "action_key": "assign_training",
        "priority": 1,
        "title": title_1,
        "description": desc_1,
        "action_type": "training",
        "button_label": "Assign Training",
        "endpoint_url": "/remediate/micro-training"
    })

    # Action 2: Follow-up Drill
    if weakest_name:
        title_2 = f"Schedule follow-up drill for {weakest_name} in 30 days"
        desc_2 = f"Runs a segmented re-test for {weakest_name} to verify security posture improvement."
    else:
        title_2 = "Schedule follow-up drill in 30 days"
        desc_2 = "Tests behavioral retention with a different social engineering vector before awareness decays."

    actions_spec.append({
        "action_key": "schedule_drill",
        "priority": 2,
        "title": title_2,
        "description": desc_2,
        "action_type": "schedule",
        "button_label": "Schedule Drill",
        "endpoint_url": f"/api/schedule-recommendation/{campaign_id}"
    })

    # Action 3: Executive Brief
    actions_spec.append({
        "action_key": "send_brief",
        "priority": 3,
        "title": "Send executive brief to management",
        "description": "Exports a structured one-page risk summary to department leadership and compliance stakeholders.",
        "action_type": "brief",
        "button_label": "Send Executive Brief",
        "endpoint_url": f"/api/send-brief/{campaign_id}"
    })

    # Action 4: Decoy Mailbox (if high click rate or repeat offenders)
    if clicks >= 3 or int(campaign.get("repeat_pct") or 0) > 0:
        actions_spec.append({
            "action_key": "deploy_decoy",
            "priority": 4,
            "title": "Deploy canary decoy mailbox for threat interception",
            "description": "Sets up an automated listening post on your domain to trap real-world credential harvesting probes.",
            "action_type": "decoy",
            "button_label": "Deploy Decoy",
            "endpoint_url": "/api/remediate/deploy-decoy"
        })

    # If cursor is available, check DB persistence
    if cursor and campaign_id and campaign_id > 0:
        try:
            ensure_campaign_actions_table(cursor)
            cursor.execute("SELECT action_key, status, completed_by, completed_at FROM campaign_actions WHERE campaign_id = %s", (campaign_id,))
            rows = cursor.fetchall()
            db_actions = {r["action_key"]: r for r in rows}

            for act in actions_spec:
                k = act["action_key"]
                if k in db_actions:
                    act["status"] = db_actions[k]["status"] or "pending"
                    act["completed_by"] = db_actions[k]["completed_by"]
                    c_at = db_actions[k]["completed_at"]
                    act["completed_at"] = c_at.strftime("%b %d, %Y %I:%M %p") if (c_at and hasattr(c_at, "strftime")) else str(c_at or "")
                else:
                    act["status"] = "pending"
                    act["completed_by"] = None
                    act["completed_at"] = None
                    cursor.execute("""
                        INSERT IGNORE INTO campaign_actions (campaign_id, action_key, title, description, status, action_type, endpoint_url)
                        VALUES (%s, %s, %s, %s, 'pending', %s, %s)
                    """, (campaign_id, k, act["title"], act["description"], act["action_type"], act["endpoint_url"]))
        except Exception as e:
            print(f"Error persisting actions: {e}")
            for act in actions_spec:
                act.setdefault("status", "pending")
    else:
        # Default / demo preview
        for i, act in enumerate(actions_spec):
            if campaign_id == 0 and i == 0:
                act["status"] = "done"
                act["completed_by"] = "admin@demo-corp.com"
                act["completed_at"] = "Today, 11:24 AM"
            else:
                act["status"] = "pending"
                act["completed_by"] = None
                act["completed_at"] = None

    done_count = sum(1 for a in actions_spec if a.get("status") == "done")
    total_count = len(actions_spec)
    progress_pct = round((done_count / total_count) * 100) if total_count else 0

    return {
        "actions": actions_spec,
        "completed_count": done_count,
        "total_count": total_count,
        "progress_pct": progress_pct
    }
