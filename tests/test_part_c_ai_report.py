import pytest
import re
from app import app, get_db_connection
from ai_engine.report_agent import (
    compute_human_security_score,
    generate_verdict_sentence,
    build_attack_replay_timeline,
    get_scenario_lure_and_clues,
    ensure_campaign_actions_table,
    get_or_create_remediation_actions,
)

def test_score_formula_high_click_rate_never_good():
    """Verify that a high click rate (>=25%) can NEVER read 'Good', even with 100% reports."""
    # 40% click rate with 100% report rate
    res = compute_human_security_score(click_rate=40.0, open_rate=80.0, report_rate=100.0, repeat_pct=10.0)
    assert res["tier"] == "red"
    assert res["label"] == "Critical"
    assert res["score"] <= 45
    assert res["terms"]["capped_reason"] is not None

    # 18% click rate (from user's bug report) can never read Good
    res_18 = compute_human_security_score(click_rate=18.0, open_rate=75.0, report_rate=50.0, repeat_pct=5.0)
    assert res_18["tier"] == "amber"
    assert res_18["label"] == "At Risk"
    assert res_18["score"] <= 68
    assert res_18["label"] != "Good"


def test_score_formula_low_click_rate_can_be_good():
    """Verify that a clean campaign (<12% clicks, high reports) earns Good tier."""
    res = compute_human_security_score(click_rate=4.0, open_rate=30.0, report_rate=60.0, repeat_pct=0.0)
    assert res["tier"] == "green"
    assert res["label"] == "Good"
    assert res["score"] >= 70


def test_verdict_sentence_validation_and_fallback():
    """Verify that hallucinated numbers in model sentences are caught and fallback is used."""
    campaign = {
        "id": 1,
        "employee_count": 44,
        "emails_sent": 44,
        "clicks": 18,
        "reports": 8,
        "opens": 28
    }
    report = {"click_rate": 40.9, "report_rate": 18.2}
    weakest = {"department": "Sales"}

    # Hallucinated sentence with numbers not in data (e.g. 99 clicked, 300 reported)
    bad_model_sentence = "99 of 300 people clicked, and nobody reported — Finance was weak."
    sentence = generate_verdict_sentence(campaign, report, weakest, model_sentence=bad_model_sentence)
    
    # Must reject bad sentence and fall back to true figures
    assert "99" not in sentence
    assert "300" not in sentence
    assert "18 of 44 people clicked" in sentence
    assert "8 reported" in sentence
    assert "Sales was the weakest team" in sentence


def test_verdict_zero_clicks_celebrated_honestly():
    """Verify 0 clicks is celebrated honestly rather than blank/error."""
    campaign = {
        "id": 2,
        "employee_count": 20,
        "emails_sent": 20,
        "clicks": 0,
        "reports": 14,
        "opens": 16
    }
    report = {"click_rate": 0.0, "report_rate": 70.0}
    sentence = generate_verdict_sentence(campaign, report, None)
    assert "Nobody clicked" in sentence
    assert "14 of 20 people reported" in sentence


def test_attack_replay_timeline_builder():
    """Verify replay timeline generates chronological 5-lane events and key insights."""
    campaign = {
        "id": 3,
        "emails_sent": 44,
        "opens": 28,
        "clicks": 18,
        "submits": 11,
        "reports": 8
    }
    replay = build_attack_replay_timeline(campaign, None, None)
    assert replay["total_sent"] == 44
    assert replay["total_opened"] == 28
    assert replay["total_clicked"] == 18
    assert replay["total_submitted"] == 11
    assert replay["total_reported"] == 8
    assert len(replay["events"]) > 0
    assert "Median time to click" in replay["key_insight"]
    assert "Median time to report" in replay["key_insight"]


def test_reports_demo_and_campaign_report_endpoints():
    """Verify /reports-demo and /campaign-report/0 return 200 with the unified template."""
    client = app.test_client()
    
    # 1. /reports-demo
    res_demo = client.get("/reports-demo")
    assert res_demo.status_code == 200
    html = res_demo.get_data(as_text=True)
    assert "The Debrief" in html
    assert "Attack replay" in html
    assert "Why it worked" in html
    assert "Who is exposed" in html
    assert "Fix it — Prioritised Remediation" in html
    assert "Human risk score" in html
    # Check that obsolete markers are completely gone
    assert "PRIMARY VISUAL ANCHOR" not in html
    assert "EXECUTIVE AI SIMULATION REPORT" not in html
    assert "Recommendation 1" not in html
    assert "chart.js" not in html.lower()

    # 2. /campaign-report/0
    res_zero = client.get("/campaign-report/0")
    assert res_zero.status_code == 200


def ensure_test_user_id():
    db = get_db_connection()
    c = db.cursor(dictionary=True)
    c.execute("SELECT id FROM users LIMIT 1")
    row = c.fetchone()
    if not row:
        c.execute("INSERT INTO users (name, email, role) VALUES ('Admin', 'admin@phishsim.ai', 'admin')")
        db.commit()
        uid = c.lastrowid
    else:
        uid = row["id"]
    c.close()
    db.close()
    return uid


def test_pdf_export_route():
    """Verify /download-report/0 returns clean PDF bytes with 200 OK."""
    with app.test_client() as client:
        # Log in as demo or simulate user session
        with client.session_transaction() as sess:
            sess["user_id"] = ensure_test_user_id()
        
        res = client.get("/download-report/0")
        assert res.status_code == 200
        assert res.content_type == "application/pdf"
        assert res.data.startswith(b"%PDF-")


def test_csv_export_route():
    """Verify /export-campaign-csv/0 returns CSV attachment with telemetry headers."""
    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess["user_id"] = ensure_test_user_id()
        
        res = client.get("/export-campaign-csv/0")
        assert res.status_code == 200
        assert "text/csv" in res.content_type
        csv_text = res.get_data(as_text=True)
        assert "Recipient Email,Department,Delivery Status,Opened,Clicked,Reported,Time To Click" in csv_text
        assert "sarah.chen@demo-corp.com" in csv_text


def test_remediation_action_api_endpoint():
    """Verify POST /api/campaign/<id>/action/<key> executes and returns JSON."""
    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess["user_id"] = ensure_test_user_id()
        
        # In test mode or with csrf disabled for test
        res = client.post("/api/campaign/0/action/assign_training", headers={"X-Requested-With": "XMLHttpRequest"})
        # 200 or 400 (if CSRF required in test env, test with json)
        if res.status_code == 400 and b"CSRF" in res.data:
            # Re-test with app.config['WTF_CSRF_ENABLED'] = False
            app.config["WTF_CSRF_ENABLED"] = False
            res = client.post("/api/campaign/0/action/assign_training")
            app.config["WTF_CSRF_ENABLED"] = True

        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert data["action_key"] == "assign_training"
        assert data["status"] == "done"


def test_draft_campaign_redirects_to_setup():
    """Verify that attempting to view a draft campaign report sends the user to finish setup."""
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute("SELECT id, user_id FROM campaigns WHERE status = 'draft' LIMIT 1")
        row = cursor.fetchone()
        if not row:
            # Create a temporary draft campaign
            cursor.execute("INSERT INTO campaigns (user_id, name, status, created_at) VALUES (1, 'Test Draft', 'draft', NOW())")
            db.commit()
            draft_id = cursor.lastrowid
            user_id = 1
        else:
            draft_id = row["id"]
            user_id = row["user_id"]

        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess["user_id"] = user_id
            
            res = client.get(f"/campaign-report/{draft_id}")
            # Should redirect to new campaign page to finish setup
            assert res.status_code in (302, 303)
            assert f"id={draft_id}" in res.location
    finally:
        cursor.close()
        db.close()


def test_one_person_campaign_handles_gracefully():
    """Verify a 1-person campaign generates a valid report without division by zero errors."""
    campaign = {
        "id": 999,
        "name": "Single Target Drill",
        "employee_count": 1,
        "emails_sent": 1,
        "opens": 1,
        "clicks": 1,
        "reports": 0,
        "submits": 0
    }
    report = {
        "delivery_rate": 100.0,
        "open_rate": 100.0,
        "click_rate": 100.0,
        "report_rate": 0.0,
        "hss": compute_human_security_score(100.0, 100.0, 0.0)
    }
    sentence = generate_verdict_sentence(campaign, report, None)
    assert "1 of 1 people clicked" in sentence
    replay = build_attack_replay_timeline(campaign, None, None)
    assert replay["total_sent"] == 1


def test_real_timestamp_replay_builder_maps_all_lanes():
    """Verify build_attack_replay_timeline maps real emails_sent and events timestamps accurately."""
    from datetime import datetime, timedelta
    t0 = datetime(2026, 8, 1, 10, 0, 0)
    emails_sent = [
        {"tracking_id": "tr-1", "recipient_email": "alice@acme.com", "department": "Sales", "sent_at": t0},
        {"tracking_id": "tr-2", "recipient_email": "bob@acme.com", "department": "Finance", "sent_at": t0 + timedelta(seconds=10)},
    ]
    events = [
        {"tracking_id": "tr-1", "event_type": "open", "created_at": t0 + timedelta(minutes=2)},
        {"tracking_id": "tr-1", "event_type": "click", "created_at": t0 + timedelta(minutes=4)},
        {"tracking_id": "tr-1", "event_type": "submit", "created_at": t0 + timedelta(minutes=6)},
        {"tracking_id": "tr-2", "event_type": "open", "created_at": t0 + timedelta(minutes=15)},
        {"tracking_id": "tr-2", "event_type": "report", "created_at": t0 + timedelta(minutes=38)},
    ]
    campaign = {"id": 50, "emails_sent": 2, "opens": 2, "clicks": 1, "submits": 1, "reports": 1}
    replay = build_attack_replay_timeline(campaign, emails_sent_rows=emails_sent, events_rows=events)
    lanes_present = {e["lane"] for e in replay["events"]}
    assert lanes_present == {"sent", "opened", "clicked", "submitted", "reported"}
    assert replay["median_time_to_click"] == 4
    assert replay["median_time_to_report"] == 38
    assert replay["attacker_lead_time"] == 34
    assert "34-minute head start" in replay["key_insight"]


def test_real_sent_lure_annotation_and_clues():
    """Verify real sent email HTML is sanitized, annotated with trigger highlights, and clues parsed."""
    emails_sent = [{
        "subject": "Urgent Wire Confirmation",
        "sender_name": "CEO Office",
        "body_html": "<html><body><p>Please complete wire transfer urgent before 5 pm today.</p><img src='https://x/track/1' /></body></html>",
        "educational_breakdown": "Leveraged executive pressure and short cutoff."
    }]
    lure = get_scenario_lure_and_clues("ceo_fraud", "acme.com", click_count=3, sent_count=10, emails_sent=emails_sent)
    assert "Urgent Wire Confirmation" in lure["subject"]
    assert "<img" not in lure["lure_html"]
    assert "<mark class='trigger-highlight'" in lure["lure_html"]
    assert any("Leveraged executive pressure" in c["description"] for c in lure["clues_missed"])


def test_real_campaign_action_persistence_and_live_badge():
    """Verify DB persistence for campaign_actions and running campaign Live badge."""
    from flask import render_template
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    created_ids = []
    try:
        cursor.execute("SELECT id, email FROM users WHERE role = 'admin' LIMIT 1")
        user_row = cursor.fetchone()
        if not user_row:
            cursor.execute("SELECT id, email FROM users LIMIT 1")
            user_row = cursor.fetchone()
        uid = user_row["id"] if user_row else 1

        # Create real running campaign + 1 employee target + sent email + 0 clicks + 1 report
        cursor.execute("""
            INSERT INTO campaigns (user_id, name, company_domain, scenario_type, delivery_mode, status, created_at)
            VALUES (%s, 'Live Running Zero Click Drill', 'test-debrief.local', 'it_reset', 'preview', 'running', NOW())
        """, (uid,))
        cid = cursor.lastrowid
        created_ids.append(cid)

        cursor.execute("INSERT INTO employees (campaign_id, name, email, department, title) VALUES (%s, 'Jane Doe', 'jane@test-debrief.local', 'Sales', 'AE')", (cid,))
        cursor.execute("""
            INSERT INTO emails_sent (campaign_id, recipient_email, subject, sender_name, body_html, tracking_id, status, sent_at)
            VALUES (%s, 'jane@test-debrief.local', 'Password expires in 2 hours', 'IT Desk', '<p>Verify your account immediately.</p>', %s, 'sent', NOW())
        """, (cid, f"trk-{cid}-1"))
        cursor.execute("INSERT INTO events (tracking_id, event_type, created_at) VALUES (%s, 'report', NOW())", (f"trk-{cid}-1",))
        db.commit()

        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess["user_id"] = uid

            # 1. Running campaign renders 200 with Live badge, 15s refresh, honest 0-click message, and no &lt;mark literals
            res = client.get(f"/campaign-report/{cid}")
            assert res.status_code == 200
            html = res.get_data(as_text=True)
            assert 'http-equiv="refresh" content="15"' in html
            assert "LIVE DRILL" in html
            assert "Nobody clicked" in html
            assert "&lt;mark class=" not in html

            # 2. Execute real schedule_drill remediation action -> must persist in DB and create follow-up drill
            act_res = client.post(f"/api/campaign/{cid}/action/schedule_drill")
            assert act_res.status_code == 200
            act_json = act_res.get_json()
            assert act_json["success"] is True
            assert act_json["status"] == "done"

            cursor.execute("SELECT status, completed_by FROM campaign_actions WHERE campaign_id = %s AND action_key = 'schedule_drill'", (cid,))
            db_act = cursor.fetchone()
            assert db_act is not None and db_act["status"] == "done"

            cursor.execute("SELECT id, status FROM campaigns WHERE user_id = %s AND id > %s AND status = 'scheduled'", (uid, cid))
            sched_row = cursor.fetchone()
            assert sched_row is not None
            created_ids.append(sched_row["id"])
    finally:
        for del_id in created_ids:
            try:
                cursor.execute("DELETE FROM events WHERE tracking_id LIKE %s", (f"trk-{del_id}-%",))
                cursor.execute("DELETE FROM emails_sent WHERE campaign_id = %s", (del_id,))
                cursor.execute("DELETE FROM employees WHERE campaign_id = %s", (del_id,))
                cursor.execute("DELETE FROM campaign_actions WHERE campaign_id = %s", (del_id,))
                cursor.execute("DELETE FROM campaigns WHERE id = %s", (del_id,))
            except Exception:
                pass
        db.commit()
        cursor.close()
        db.close()


def test_cdn_blocked_zero_console_errors_and_interactivity():
    """Verify /reports-demo renders and interacts with 0 console/page errors when CDNs are blocked."""
    import threading
    from werkzeug.serving import make_server
    from playwright.sync_api import sync_playwright

    server = make_server("127.0.0.1", 0, app)
    port = server.server_port
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    console_errors = []
    page_errors = []

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            ctx = browser.new_context(viewport={"width": 1440, "height": 900})
            page = ctx.new_page()

            def block_cdn(route):
                url = route.request.url.lower()
                if "127.0.0.1" not in url and "localhost" not in url:
                    ctype = "text/css" if ".css" in url else "text/javascript"
                    route.fulfill(status=200, content_type=ctype, body="")
                else:
                    route.continue_()

            page.route("**/*", block_cdn)
            page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
            page.on("pageerror", lambda err: page_errors.append(str(err)))

            page.goto(f"http://127.0.0.1:{port}/reports-demo", wait_until="domcontentloaded")
            page.wait_for_timeout(400)

            # Verify SVG attack replay dots exist & counters respond to scrubbing
            dots_count = page.locator("#attack-timeline-svg .event-dot").count()
            assert dots_count > 0

            # Scrub slider to 0% -> live clicked counter drops to 0
            page.locator("#replay-scrubber").fill("0")
            page.locator("#replay-scrubber").dispatch_event("input")
            assert page.locator("#live-cnt-clicked").text_content().strip() == "0"

            # Scrub slider back to 100% -> live clicked counter restores
            page.locator("#replay-scrubber").fill("100")
            page.locator("#replay-scrubber").dispatch_event("input")
            assert int(page.locator("#live-cnt-clicked").text_content().strip()) > 0

            # Toggle trigger highlights & anonymise without JS errors
            page.locator("#toggle-trigger-highlights").click()
            assert page.locator(".trigger-highlight.force-active").count() > 0

            first_emp_before = page.locator(".emp-name").first.text_content().strip()
            page.locator("#toggle-anonymise").click()
            first_emp_after = page.locator(".emp-name").first.text_content().strip()
            assert first_emp_before != first_emp_after
            assert first_emp_after.startswith("Employee ")

            browser.close()
    finally:
        server.shutdown()

    assert console_errors == [], f"Console errors with CDN blocked: {console_errors}"
    assert page_errors == [], f"Uncaught page errors with CDN blocked: {page_errors}"


def test_clean_database_schema_and_campaign_report_resilience():
    """Builds schema from scratch in a fresh database, seeds real campaigns,
    and asserts report returns 200 with verdict, replay, departments, and actions.
    Also tests: 0 clicks, 1 person, draft campaign, and campaign with no emails.
    """
    import os
    import mysql.connector
    from app import (
        ensure_auth_schema, ensure_core_tables, ensure_email_tracking_table,
        ensure_events_table, ensure_audit_table, get_db_connection
    )
    import app as app_module

    clean_db_name = "phishsim_clean_scratch_test"

    raw_db = get_db_connection()
    raw_cursor = raw_db.cursor()
    raw_cursor.execute(f"DROP DATABASE IF EXISTS {clean_db_name}")
    raw_cursor.execute(f"CREATE DATABASE {clean_db_name}")
    raw_cursor.close()
    raw_db.close()

    host = os.getenv("DB_HOST", "localhost")
    user = os.getenv("DB_USER", "root")
    password = os.getenv("DB_PASS", os.getenv("DB_PASSWORD", "root"))
    port = int(os.getenv("DB_PORT", 3306))

    clean_conn = mysql.connector.connect(
        host=host, user=user, password=password, port=port, database=clean_db_name
    )
    cursor = clean_conn.cursor(dictionary=True)

    original_get_db = app_module.get_db_connection
    app_module.get_db_connection = lambda: mysql.connector.connect(
        host=host, user=user, password=password, port=port, database=clean_db_name
    )

    try:
        # 1. Bootstrap schema from scratch
        ensure_auth_schema(cursor)
        ensure_core_tables(cursor)
        ensure_email_tracking_table(cursor)
        ensure_events_table(cursor)
        ensure_audit_table(cursor)
        clean_conn.commit()

        # Verify clean events table columns
        cursor.execute("DESCRIBE events")
        cols = [r["Field"] for r in cursor.fetchall()]
        assert "ip_address" in cols
        assert "created_at" in cols

        # 2. Seed admin user
        cursor.execute("""
            INSERT INTO users (name, email, password_hash, role, email_verified, created_at)
            VALUES ('Clean Admin', 'admin@clean-test.local', 'hash', 'admin', 1, NOW())
        """)
        clean_conn.commit()
        admin_id = cursor.lastrowid

        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess["user_id"] = admin_id
                sess["_fresh"] = True

            # Case A: Real campaign with opens, clicks, and reports
            cursor.execute("""
                INSERT INTO campaigns (user_id, name, company_domain, scenario_type, delivery_mode, status, created_at)
                VALUES (%s, 'Clean DB Standard Campaign', 'clean.local', 'it_reset', 'preview', 'completed', NOW())
            """, (admin_id,))
            clean_conn.commit()
            c1_id = cursor.lastrowid

            cursor.execute("INSERT INTO employees (campaign_id, name, email, department, title) VALUES (%s, 'Alice Vance', 'alice@clean.local', 'Finance', 'Analyst')", (c1_id,))
            cursor.execute("INSERT INTO employees (campaign_id, name, email, department, title) VALUES (%s, 'Bob Ross', 'bob@clean.local', 'Sales', 'Manager')", (c1_id,))
            cursor.execute("INSERT INTO employees (campaign_id, name, email, department, title) VALUES (%s, 'Charlie Day', 'charlie@clean.local', 'Finance', 'Clerk')", (c1_id,))

            cursor.execute("""
                INSERT INTO emails_sent (campaign_id, recipient_email, subject, sender_name, body_html, tracking_id, status, sent_at)
                VALUES (%s, 'alice@clean.local', 'Urgent Alert', 'IT Help', '<p>Test</p>', 'trk-clean-1', 'sent', NOW())
            """, (c1_id,))
            cursor.execute("""
                INSERT INTO emails_sent (campaign_id, recipient_email, subject, sender_name, body_html, tracking_id, status, sent_at)
                VALUES (%s, 'bob@clean.local', 'Urgent Alert', 'IT Help', '<p>Test</p>', 'trk-clean-2', 'sent', NOW())
            """, (c1_id,))
            cursor.execute("""
                INSERT INTO emails_sent (campaign_id, recipient_email, subject, sender_name, body_html, tracking_id, status, sent_at)
                VALUES (%s, 'charlie@clean.local', 'Urgent Alert', 'IT Help', '<p>Test</p>', 'trk-clean-3', 'sent', NOW())
            """, (c1_id,))

            cursor.execute("INSERT INTO events (tracking_id, event_type, ip_address, user_agent, created_at) VALUES ('trk-clean-1', 'open', '127.0.0.1', 'Mozilla', NOW())")
            cursor.execute("INSERT INTO events (tracking_id, event_type, ip_address, user_agent, created_at) VALUES ('trk-clean-1', 'click', '127.0.0.1', 'Mozilla', NOW())")
            cursor.execute("INSERT INTO events (tracking_id, event_type, ip_address, user_agent, created_at) VALUES ('trk-clean-2', 'open', '127.0.0.1', 'Mozilla', NOW())")
            cursor.execute("INSERT INTO events (tracking_id, event_type, ip_address, user_agent, created_at) VALUES ('trk-clean-2', 'report', '127.0.0.1', 'Mozilla', NOW())")
            cursor.execute("INSERT INTO events (tracking_id, event_type, ip_address, user_agent, created_at) VALUES ('trk-clean-3', 'open', '127.0.0.1', 'Mozilla', NOW())")
            clean_conn.commit()

            resp = client.get(f"/campaign-report/{c1_id}")
            assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
            html = resp.get_data(as_text=True)
            assert "Attack replay" in html
            assert "Finance" in html
            assert "Sales" in html
            assert "Recommended remediation" in html or "Remediation" in html

            # Case B: 0 clicks campaign
            cursor.execute("""
                INSERT INTO campaigns (user_id, name, company_domain, scenario_type, delivery_mode, status, created_at)
                VALUES (%s, 'Zero Click Drill', 'clean.local', 'it_reset', 'preview', 'completed', NOW())
            """, (admin_id,))
            clean_conn.commit()
            c2_id = cursor.lastrowid
            cursor.execute("INSERT INTO employees (campaign_id, name, email, department, title) VALUES (%s, 'Eve Polastri', 'eve@clean.local', 'Security', 'Lead')", (c2_id,))
            cursor.execute("""
                INSERT INTO emails_sent (campaign_id, recipient_email, subject, sender_name, body_html, tracking_id, status, sent_at)
                VALUES (%s, 'eve@clean.local', 'Password alert', 'IT', '<p>Test</p>', 'trk-clean-2-1', 'sent', NOW())
            """, (c2_id,))
            cursor.execute("INSERT INTO events (tracking_id, event_type, ip_address, user_agent, created_at) VALUES ('trk-clean-2-1', 'open', '127.0.0.1', 'Mozilla', NOW())")
            cursor.execute("INSERT INTO events (tracking_id, event_type, ip_address, user_agent, created_at) VALUES ('trk-clean-2-1', 'report', '127.0.0.1', 'Mozilla', NOW())")
            clean_conn.commit()

            resp2 = client.get(f"/campaign-report/{c2_id}")
            assert resp2.status_code == 200
            html2 = resp2.get_data(as_text=True)
            assert "Nobody clicked" in html2 or "0%" in html2

            # Case C: 1 person campaign
            cursor.execute("""
                INSERT INTO campaigns (user_id, name, company_domain, scenario_type, delivery_mode, status, created_at)
                VALUES (%s, 'Single Person Drill', 'clean.local', 'it_reset', 'preview', 'completed', NOW())
            """, (admin_id,))
            clean_conn.commit()
            c3_id = cursor.lastrowid
            cursor.execute("INSERT INTO employees (campaign_id, name, email, department, title) VALUES (%s, 'Solo Worker', 'solo@clean.local', 'Engineering', 'Dev')", (c3_id,))
            cursor.execute("""
                INSERT INTO emails_sent (campaign_id, recipient_email, subject, sender_name, body_html, tracking_id, status, sent_at)
                VALUES (%s, 'solo@clean.local', 'Dev alert', 'IT', '<p>Test</p>', 'trk-clean-3-1', 'sent', NOW())
            """, (c3_id,))
            cursor.execute("INSERT INTO events (tracking_id, event_type, ip_address, user_agent, created_at) VALUES ('trk-clean-3-1', 'click', '127.0.0.1', 'Mozilla', NOW())")
            clean_conn.commit()

            resp3 = client.get(f"/campaign-report/{c3_id}")
            assert resp3.status_code == 200
            html3 = resp3.get_data(as_text=True)
            assert "Engineering" in html3

            # Case D: Draft campaign (graceful redirect, never 503)
            cursor.execute("""
                INSERT INTO campaigns (user_id, name, company_domain, scenario_type, delivery_mode, status, created_at)
                VALUES (%s, 'Draft Campaign', 'clean.local', 'it_reset', 'preview', 'draft', NOW())
            """, (admin_id,))
            clean_conn.commit()
            c4_id = cursor.lastrowid

            resp4 = client.get(f"/campaign-report/{c4_id}")
            assert resp4.status_code in (302, 303)
            assert f"id={c4_id}" in resp4.headers.get("Location", "")

            # Case E: Campaign with no emails
            cursor.execute("""
                INSERT INTO campaigns (user_id, name, company_domain, scenario_type, delivery_mode, status, created_at)
                VALUES (%s, 'No Emails Drill', 'clean.local', 'it_reset', 'preview', 'completed', NOW())
            """, (admin_id,))
            clean_conn.commit()
            c5_id = cursor.lastrowid

            resp5 = client.get(f"/campaign-report/{c5_id}")
            assert resp5.status_code == 200

            # Case F: Replay resilience fallback
            with app.test_request_context(f"/campaign-report/{c1_id}"):
                from flask import render_template
                from ai_engine.report_agent import compute_human_security_score
                test_hss = compute_human_security_score(10, 20, 5, 0)
                rendered = render_template(
                    "campaign_report.html",
                    campaign={"id": c1_id, "name": "Resilience Test", "status": "completed", "emails_sent": 3, "scenario_type": "it_reset"},
                    report={"summary": "test", "risk_level": "Good", "hss": test_hss},
                    hss=test_hss,
                    verdict_sentence="Test verdict",
                    attack_replay=None,
                    lure_data={},
                    department_stats=[],
                    employee_logs=[],
                    funnel_data={"current": {"sent": 3, "opened": 2, "clicked": 1, "submitted": 0, "reported": 1}, "prev": None, "is_first_campaign": True, "score_history": []},
                    remediation_data={},
                    is_demo_preview=False,
                    is_live=False,
                    user={"role": "admin"}
                )
                assert "Replay isn't available for this campaign" in rendered

    finally:
        app_module.get_db_connection = original_get_db
        cursor.close()
        clean_conn.close()

        raw_db = get_db_connection()
        raw_cursor = raw_db.cursor()
        raw_cursor.execute(f"DROP DATABASE IF EXISTS {clean_db_name}")
        raw_cursor.close()
        raw_db.close()

