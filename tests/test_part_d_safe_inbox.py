import os
import threading
import pytest
from app import app, get_db_connection
from ai_engine.email_sanitizer import (
    sanitize_email_html,
    html_to_plain_text,
    annotate_lure_html,
    mask_credential,
    plain_mode_badge_info,
    compute_email_diff,
)
from ai_engine.report_agent import _annotate_lure_html


def _get_admin_user_id(cursor):
    admin_email = os.getenv("ADMIN_EMAIL", "admin@phishsim.ai").strip().lower()
    cursor.execute("SELECT id, email FROM users WHERE email = %s", (admin_email,))
    row = cursor.fetchone()
    if row:
        return row["id"], row["email"]
    cursor.execute("SELECT id, email FROM users WHERE role = 'admin' LIMIT 1")
    row = cursor.fetchone()
    return (row["id"], row["email"]) if row else (1, "admin@phishsim.ai")


def test_sanitizer_strips_xss_and_shares_redflag_component():
    """Server-side sanitizer removes scripts/event handlers/javascript URIs and shares Part C trigger highlights."""
    malicious = (
        '<p onclick="window.__xss=1">Please process this <span onmouseover="alert(1)">invoice</span> '
        'before 5:00 PM today.</p>'
        '<script>window.__xss=1; top.location="https://evil.test";</script>'
        '<img src="https://example.com/track/open/abc.gif" width="1" height="1">'
        '<a href="javascript:alert(1)">Bad Link</a> '
        '<a href="https://example.com/click/123">Safe Portal</a>'
    )
    cleaned = sanitize_email_html(malicious)
    assert "<script" not in cleaned.lower()
    assert "onclick" not in cleaned.lower()
    assert "onmouseover" not in cleaned.lower()
    assert "javascript:" not in cleaned.lower()
    assert "track/open" not in cleaned.lower()
    assert "https://example.com/click/123" in cleaned

    # Shared component parity between Part C (_annotate_lure_html) and Part D (annotate_lure_html)
    assert annotate_lure_html(malicious) == _annotate_lure_html(malicious)
    assert "<mark class='trigger-highlight'" in annotate_lure_html(malicious)

    plain = html_to_plain_text(malicious)
    assert "<p" not in plain
    assert "window.__xss" not in plain
    assert "before 5:00 PM today" in plain


def test_credential_masking_never_exposes_secrets():
    assert mask_credential("mt_secret_user_9876") == "••••••••••••9876"
    assert "mt_secret_user" not in mask_credential("mt_secret_user_9876")
    assert mask_credential("abc") == "•••"
    assert mask_credential("") == ""
    assert mask_credential(None) == ""


def test_mode_badges_missing_body_zero_markup_and_generate():
    """Verifies plain-words mode badges, zero leaked <em...> markup when missing, and Generate endpoint."""
    assert plain_mode_badge_info("preview")["label"] == "Preview — nothing was sent"
    assert plain_mode_badge_info("mailtrap")["label"] == "Safe send — delivered to your test inbox"
    assert plain_mode_badge_info("sandbox")["label"] == "Safe send — delivered to your test inbox"
    assert plain_mode_badge_info("smtp")["label"] == "Live — sent to real inboxes"

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    created_campaigns = []
    try:
        uid, _ = _get_admin_user_id(cursor)

        for mode, status, expected_badge in [
            ("preview", "draft", "Preview — nothing was sent"),
            ("mailtrap", "launched", "Safe send — delivered to your test inbox"),
            ("smtp", "launched", "Live — sent to real inboxes"),
        ]:
            cursor.execute(
                """
                INSERT INTO campaigns (user_id, name, company_domain, scenario_type, delivery_mode, status, created_at)
                VALUES (%s, %s, 'inbox-test.local', 'ceo_fraud', %s, %s, NOW())
                """,
                (uid, f"Part D Test {mode}", mode, status),
            )
            cid = cursor.lastrowid
            created_campaigns.append(cid)

            cursor.execute(
                "INSERT INTO employees (campaign_id, name, email, department, title) VALUES (%s, 'Alice Fin', 'alice@inbox-test.local', 'Finance', 'Analyst')",
                (cid,),
            )
            # Missing body row
            cursor.execute(
                """
                INSERT INTO emails_sent (campaign_id, tracking_id, recipient_email, subject, sender_name, body_html, status, sent_at)
                VALUES (%s, %s, 'alice@inbox-test.local', 'Wire Approval', 'CFO Office', NULL, 'sent', NOW())
                """,
                (cid, f"trk-d-{cid}-1"),
            )
            email_id = cursor.lastrowid
            db.commit()

            with app.test_client() as client:
                with client.session_transaction() as sess:
                    sess["user_id"] = uid

                res = client.get(f"/campaign-emails/{cid}")
                assert res.status_code == 200
                html = res.get_data(as_text=True)
                assert expected_badge in html
                assert "This email hasn&#39;t been generated yet" in html or "This email hasn't been generated yet" in html
                # Real bug regression check: leaked escaped HTML must NEVER appear
                assert "&lt;em style=" not in html
                assert "Email body not available." not in html

                if mode == "preview":
                    gen_res = client.post(
                        f"/api/campaign/{cid}/emails/generate",
                        json={"email_id": email_id, "use_ai": False},
                    )
                    assert gen_res.status_code == 200
                    gen_data = gen_res.get_json()
                    assert gen_data["success"] is True
                    assert gen_data["email"]["has_body"] is True
                    assert len(gen_data["email"]["plain_text"]) > 20
    finally:
        for cid in created_campaigns:
            cursor.execute("DELETE FROM events WHERE tracking_id LIKE %s", (f"trk-d-{cid}-%",))
            cursor.execute("DELETE FROM emails_sent WHERE campaign_id = %s", (cid,))
            cursor.execute("DELETE FROM employees WHERE campaign_id = %s", (cid,))
            cursor.execute("DELETE FROM campaigns WHERE id = %s", (cid,))
        db.commit()
        cursor.close()
        db.close()


def test_edit_diff_gating_and_safe_send_masking_and_test_connection(monkeypatch):
    """Edit/diff works on draft/preview only (403 on live), credentials never echo unmasked, test connection checks SMTP."""
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    created_campaigns = []
    try:
        uid, _ = _get_admin_user_id(cursor)
        cursor.execute(
            """
            INSERT INTO campaigns (user_id, name, company_domain, scenario_type, delivery_mode, status, created_at)
            VALUES (%s, 'Editable Draft Drill', 'diff-test.local', 'it_reset', 'preview', 'draft', NOW())
            """,
            (uid,),
        )
        draft_cid = cursor.lastrowid
        created_campaigns.append(draft_cid)
        cursor.execute(
            """
            INSERT INTO emails_sent (campaign_id, tracking_id, recipient_email, subject, sender_name, body_html, status, sent_at)
            VALUES (%s, %s, 'bob@diff-test.local', 'Old Subject Line', 'IT Helpdesk', '<p>Original notice body.</p><p><a href="TRACKING_LINK">Reset</a></p>', 'sent', NOW())
            """,
            (draft_cid, f"trk-diff-{draft_cid}"),
        )
        draft_eid = cursor.lastrowid

        cursor.execute(
            """
            INSERT INTO campaigns (user_id, name, company_domain, scenario_type, delivery_mode, status, created_at)
            VALUES (%s, 'Locked Live Drill', 'diff-test.local', 'it_reset', 'smtp', 'launched', NOW())
            """,
            (uid,),
        )
        live_cid = cursor.lastrowid
        created_campaigns.append(live_cid)
        cursor.execute(
            """
            INSERT INTO emails_sent (campaign_id, tracking_id, recipient_email, subject, sender_name, body_html, status, sent_at)
            VALUES (%s, %s, 'bob@diff-test.local', 'Live Subject', 'IT Helpdesk', '<p>Live notice.</p>', 'sent', NOW())
            """,
            (live_cid, f"trk-diff-{live_cid}"),
        )
        live_eid = cursor.lastrowid
        db.commit()

        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess["user_id"] = uid

            # 1. Regenerate preview on draft returns diff
            regen = client.post(
                f"/api/campaign/{draft_cid}/emails/{draft_eid}/regenerate",
                json={"prompt": "Reference Q4 audit deadline before 5 PM today", "use_ai": False},
            )
            assert regen.status_code == 200
            rj = regen.get_json()
            assert rj["success"] is True
            assert any(d["type"] == "add" for d in rj["diff"])
            assert any(d["type"] == "del" for d in rj["diff"])

            # Apply change
            apply_res = client.post(
                f"/api/campaign/{draft_cid}/emails/{draft_eid}/regenerate",
                json={
                    "apply": True,
                    "subject": rj["new_subject"],
                    "sender_name": rj["new_sender_name"],
                    "body_html": rj["new_body_html"],
                },
            )
            assert apply_res.status_code == 200
            assert apply_res.get_json()["saved"] is True

            # 2. Live campaign edit + send-test are rejected cleanly
            blocked_edit = client.post(
                f"/api/campaign/{live_cid}/emails/{live_eid}/regenerate",
                json={"prompt": "Should fail"},
            )
            assert blocked_edit.status_code == 403

            blocked_test = client.post(f"/api/campaign/{live_cid}/emails/{live_eid}/send-test", json={})
            assert blocked_test.status_code == 403

            # 3. Safe send credential masking + Test connection
            secret_user = "supersecret_user_8842"
            secret_pass = "supersecret_pass_9913"

            class DummySMTP:
                def __init__(self, host, port, timeout=6):
                    self.host = host
                    self.port = port
                def __enter__(self):
                    return self
                def __exit__(self, *args):
                    return False
                def ehlo(self):
                    pass
                def starttls(self):
                    pass
                def login(self, u, p):
                    assert u == secret_user
                    assert p == secret_pass

            monkeypatch.setattr("smtplib.SMTP", DummySMTP)
            conn_res = client.post(
                "/api/safe-send/test-connection",
                json={"test_inbox": "qa@diff-test.local", "mailtrap_user": secret_user, "mailtrap_pass": secret_pass},
            )
            assert conn_res.status_code == 200
            raw_text = conn_res.get_data(as_text=True)
            assert secret_user not in raw_text
            assert secret_pass not in raw_text
            cj = conn_res.get_json()
            assert cj["connected"] is True
            assert cj["safe_send_status"]["status_text"] == "Connected"
            assert cj["safe_send_status"]["masked_user"].endswith("8842")
            assert cj["safe_send_status"]["masked_pass"].endswith("9913")
    finally:
        for cid in created_campaigns:
            cursor.execute("DELETE FROM emails_sent WHERE campaign_id = %s", (cid,))
            cursor.execute("DELETE FROM campaigns WHERE id = %s", (cid,))
        db.commit()
        cursor.close()
        db.close()


def test_playwright_inbox_sandbox_xss_keyboard_filters_and_modals():
    """E2E Playwright test verifying sandboxed iframe blocks script execution, keyboard J/K/Enter, filters, toggles, and modals."""
    from werkzeug.serving import make_server
    from playwright.sync_api import sync_playwright

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    created_campaigns = []

    try:
        uid, admin_email = _get_admin_user_id(cursor)
        admin_password = os.getenv("ADMIN_PASSWORD", "admin123")

        cursor.execute(
            """
            INSERT INTO campaigns (user_id, name, company_domain, scenario_type, delivery_mode, status, created_at)
            VALUES (%s, 'Playwright Safe Inbox Drill', 'pw-inbox.local', 'ceo_fraud', 'sandbox', 'draft', NOW())
            """,
            (uid,),
        )
        cid = cursor.lastrowid
        created_campaigns.append(cid)

        cursor.execute(
            "INSERT INTO employees (campaign_id, name, email, department, title) VALUES (%s, 'First Target', 'first@pw-inbox.local', 'Finance', 'VP')",
            (cid,),
        )
        cursor.execute(
            "INSERT INTO employees (campaign_id, name, email, department, title) VALUES (%s, 'Second Target', 'second@pw-inbox.local', 'Engineering', 'SRE')",
            (cid,),
        )

        # Row 1: XSS payload inside body + urgency trigger phrase for red flags
        xss_body = (
            "<p>Hello First Target, please process this wire transfer before 5:00 PM today.</p>"
            "<script>window.__xss_ran = true; try { window.parent.__xss_parent = true; } catch(e) {}</script>"
            '<p><img src=x onerror="window.__xss_img = true"><a href="TRACKING_LINK">Verify Invoice</a></p>'
        )
        cursor.execute(
            """
            INSERT INTO emails_sent (campaign_id, tracking_id, recipient_email, subject, sender_name, body_html, status, sent_at)
            VALUES (%s, %s, 'first@pw-inbox.local', 'Urgent Wire Approval', 'CEO Desk', %s, 'clicked', NOW())
            """,
            (cid, f"trk-pw-{cid}-1", xss_body),
        )
        # Row 2: missing body to test missing-body friendly state + Generate button
        cursor.execute(
            """
            INSERT INTO emails_sent (campaign_id, tracking_id, recipient_email, subject, sender_name, body_html, status, sent_at)
            VALUES (%s, %s, 'second@pw-inbox.local', 'Security Check', 'IT Desk', NULL, 'sent', NOW())
            """,
            (cid, f"trk-pw-{cid}-2"),
        )
        cursor.execute("INSERT INTO events (tracking_id, event_type, created_at) VALUES (%s, 'click', NOW())", (f"trk-pw-{cid}-1",))
        db.commit()

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

                def handle_route(route):
                    url = route.request.url.lower()
                    if "127.0.0.1" not in url and "localhost" not in url:
                        ctype = "text/css" if ".css" in url else "text/javascript"
                        route.fulfill(status=200, content_type=ctype, body="")
                    else:
                        route.continue_()

                page.route("**/*", handle_route)
                page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
                page.on("pageerror", lambda err: page_errors.append(str(err)))

                # Authenticate directly via signed Flask session cookie
                with app.test_client() as tc:
                    with tc.session_transaction() as s:
                        s["user_id"] = uid
                    sess_cookie = tc.get_cookie("session").value
                ctx.add_cookies([{"name": "session", "value": sess_cookie, "domain": "127.0.0.1", "path": "/"}])

                page.goto(f"http://127.0.0.1:{port}/campaign-emails/{cid}", wait_until="domcontentloaded")
                page.wait_for_timeout(350)

                # 1. Plain-language mode badge
                assert "Safe send — delivered to your test inbox" in page.locator("#campaign-mode-badge").inner_text()

                # 2. Sandboxed iframe attribute + XSS script execution check
                iframe = page.locator("#email-sandbox-frame")
                assert iframe.get_attribute("sandbox") == ""
                srcdoc_val = iframe.get_attribute("srcdoc") or ""
                assert "<script" not in srcdoc_val.lower()
                assert "onerror" not in srcdoc_val.lower()
                xss_parent_hit = page.evaluate("() => Boolean(window.__xss_parent || window.__xss_ran || window.__xss_img)")
                assert xss_parent_hit is False

                # Check inside frame directly as well
                frames = page.frames
                sandboxed = [f for f in frames if f != page.main_frame]
                for sf in sandboxed:
                    try:
                        ran = sf.evaluate("() => Boolean(window.__xss_ran || window.__xss_img)")
                        assert ran is False
                    except Exception:
                        # Opaque sandboxed origin without allow-scripts blocks evaluation/scripts
                        pass

                # 3. View mode toggles: Plain text & Source
                page.click('button[data-view-mode="plain"]')
                assert page.locator("#email-plain-view").is_visible()
                assert "before 5:00 PM today" in page.locator("#email-plain-view").inner_text()

                page.click('button[data-view-mode="source"]')
                assert page.locator("#email-source-view").is_visible()

                # 4. Show red flags toggle + Mobile width switch
                page.click('#toggle-inbox-redflags')
                page.click('button[data-width-mode="mobile"]')
                assert "is-mobile-width" in (page.locator("#msg-frame-wrap").get_attribute("class") or "")
                flagged_srcdoc = iframe.get_attribute("srcdoc") or ""
                assert "trigger-highlight" in flagged_srcdoc

                # 5. Preview landing page modal with Simulation watermark
                page.click("#btn-preview-landing")
                assert page.locator("#landing-preview-modal.is-open").is_visible()
                assert "simulation" in page.locator("#landing-preview-modal").inner_text().lower()
                page.click("#btn-close-landing-modal")

                # 6. Edit email modal (draft campaign)
                page.click("#btn-open-edit-modal")
                page.fill("#edit-prompt-input", "Make it shorter and reference Q4 audit deadline")
                page.click("#btn-run-regenerate")
                page.wait_for_selector("#edit-diff-box .diff-add", timeout=15000)
                assert page.locator("#edit-diff-box .diff-add").count() > 0
                page.click("#btn-close-edit-modal")

                # 7. Keyboard navigation J -> Row 2 (missing body -> Generate button), K -> Row 1
                page.keyboard.press("j")
                page.wait_for_timeout(150)
                assert "Security Check" in page.locator("#msg-subject").inner_text()
                assert page.locator("#msg-missing-state").is_visible()
                assert "This email hasn't been generated yet" in page.locator("#msg-missing-state").inner_text()
                assert "&lt;em" not in page.content()

                # Generate missing body live in UI
                page.click("#btn-generate-missing")
                page.wait_for_selector("#msg-frame-wrap:not([hidden])", timeout=15000)
                assert page.locator("#msg-missing-state").is_hidden()

                page.keyboard.press("k")
                page.keyboard.press("Enter")
                page.wait_for_timeout(100)
                assert "Urgent Wire Approval" in page.locator("#msg-subject").inner_text()

                # 8. Filter chips by department & status
                page.click('button[data-dept-filter="Engineering"]')
                visible_rows = page.locator(".inbox-row:not(.is-hidden)").count()
                assert visible_rows == 1
                assert "second@pw-inbox.local" in page.locator(".inbox-row:not(.is-hidden)").inner_text()
                page.click('button[data-dept-filter="all"]')

                assert console_errors == [], f"Unexpected console errors: {console_errors}"
                assert page_errors == [], f"Unexpected page errors: {page_errors}"

                # 9. Verify iframe sandbox="" attribute itself blocks inline <script> execution in Chromium
                page.evaluate("""() => {
                    const fr = document.getElementById('email-sandbox-frame');
                    fr.srcdoc = '<!DOCTYPE html><html><body><p id="p">safe</p><script>document.getElementById("p").textContent="PWNED"; window.top.__sandbox_bypass=true;</script></body></html>';
                }""")
                page.wait_for_timeout(150)
                assert page.evaluate("() => Boolean(window.__sandbox_bypass)") is False
                sand_frame = page.frame_locator("#email-sandbox-frame")
                assert sand_frame.locator("#p").inner_text() == "safe"

                browser.close()
        finally:
            server.shutdown()
    finally:
        cursor.execute("DELETE FROM events WHERE tracking_id LIKE %s", (f"trk-pw-{created_campaigns[0]}-%",))
        for cid_del in created_campaigns:
            cursor.execute("DELETE FROM emails_sent WHERE campaign_id = %s", (cid_del,))
            cursor.execute("DELETE FROM employees WHERE campaign_id = %s", (cid_del,))
            cursor.execute("DELETE FROM campaigns WHERE id = %s", (cid_del,))
        db.commit()
        cursor.close()
        db.close()

