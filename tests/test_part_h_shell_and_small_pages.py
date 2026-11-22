import os
import re
import pytest
from app import app

@pytest.fixture
def client():
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    with app.test_client() as client:
        yield client


# ══════════════════════════════════════════════════════════════
# 1. FOOTER TESTS
# ══════════════════════════════════════════════════════════════
def test_guest_footer_cleaned(client):
    """Guest/logged-out homepage has full footer with fake telemetry removed."""
    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")

    # Removed fake telemetry & coordinates
    assert "Fleet Defenses Operational" not in html
    assert "99.98% Uptime" not in html
    assert "X: 234.10092" not in html
    assert "Y: 23.001000" not in html
    assert ">Systems</a>" not in html

    # Kept: logo, one-line description, 3 link columns, copyright
    assert "PhishSim" in html
    assert "Autonomous phishing simulation and automated human defense platform" in html
    assert "Product" in html
    assert "Resources" in html
    assert "Legal" in html
    assert "2026 PhishSim AI" in html


def test_logged_in_slim_footer(client):
    """Logged-in session renders slim one-row footer."""
    with client.session_transaction() as sess:
        sess["user_id"] = 1
        sess["user_email"] = "admin@example.com"
        sess["user_role"] = "admin"

    resp = client.get("/dashboard")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")

    # Has slim footer class
    assert "site-footer-slim" in html
    assert "footer-slim-inner" in html
    assert "footer-slim-links" in html

    # Does NOT have the heavy 3-column navigation
    assert '<div class="footer-col">' not in html


# ══════════════════════════════════════════════════════════════
# 2. SANDBOX BANNER TESTS
# ══════════════════════════════════════════════════════════════
def test_sandbox_banner_only_in_demo(client):
    """Sandbox banner shows ONLY when session has is_demo=True, never for real users."""
    # A. Guest homepage: NO banner
    resp = client.get("/")
    html = resp.data.decode("utf-8")
    assert "Sandbox Mode" not in html

    # B. Real logged-in user: NO banner
    with client.session_transaction() as sess:
        sess["user_id"] = 1
        sess["user_email"] = "analyst@realcorp.com"
        sess["user_role"] = "company_user"
        sess.pop("is_demo", None)

    resp = client.get("/dashboard")
    html = resp.data.decode("utf-8")
    assert "Sandbox Mode" not in html

    # C. Demo session: Banner appears with CSS class, no inline styles
    with client.session_transaction() as sess:
        sess["user_id"] = 0
        sess["is_demo"] = True

    resp = client.get("/dashboard")
    html = resp.data.decode("utf-8")
    assert "Sandbox Mode" in html
    assert "Demo environment. Data is illustrative only" in html
    assert 'class="sandbox-banner"' in html
    # Verify inline styles were moved to CSS
    assert 'style="background: #eab308; color: #713f12;' not in html


# ══════════════════════════════════════════════════════════════
# 3. ERROR PAGES TESTS (403, 404, 500, 503)
# ══════════════════════════════════════════════════════════════
def test_404_error_page(client):
    """404 renders error.html with one human sentence + one button."""
    resp = client.get("/non-existent-page-path-12345")
    assert resp.status_code == 404
    html = resp.data.decode("utf-8")

    assert "404" in html
    assert "Page not found" in html
    assert "The page you are looking for does not exist or has been moved." in html
    assert 'class="error-action-btn"' in html


def test_service_unavailable_page(client):
    """503 renders service_unavailable.html with one human sentence + one button."""
    with app.test_request_context("/"):
        from flask import render_template
        html = render_template("service_unavailable.html", referrer="/")
        assert "503" in html
        assert "Service temporarily unavailable" in html
        assert "We are currently undergoing quick maintenance or reconnecting to our secure database." in html
        assert "Try again" in html


# ══════════════════════════════════════════════════════════════
# 4. LEGAL PAGES TESTS
# ══════════════════════════════════════════════════════════════
@pytest.mark.parametrize("route,title", [
    ("/privacy", "Privacy Policy"),
    ("/terms", "Terms of Service"),
    ("/acceptable-use", "Acceptable Use Policy"),
    ("/consent-policy", "Consent & Authorization Policy"),
    ("/data-handling-policy", "Data Handling Policy")
])
def test_legal_pages_primitives(client, route, title):
    """Legal pages have 680px reading column, sticky contents list, and last-updated date."""
    resp = client.get(route)
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")

    assert title in html
    assert "legal-column-680" in html
    assert "legal-toc-sticky" in html
    assert "legal-last-updated" in html
    assert "Last updated:" in html


# ══════════════════════════════════════════════════════════════
# 5. CERTIFICATE PAGE & VERIFICATION
# ══════════════════════════════════════════════════════════════
def test_certificate_white_paper_layout():
    """Certificate template has white paper layout, QR code, and verify link."""
    with app.test_request_context("/"):
        from flask import render_template
        mock_data = {
            "name": "Alex Mercer",
            "date": "October 26, 2026",
            "campaignName": "Executive Drill Q4",
            "verificationId": "PSV-TEST1234"
        }
        html = render_template("certificate.html", data=mock_data)

        # White paper layout
        assert "cert-paper" in html
        assert "cert-border-outer" in html
        assert "cert-border-inner" in html
        assert "Alex Mercer" in html
        assert "Executive Drill Q4" in html

        # QR and verify link
        assert "cert-qr-verify" in html
        assert "/verify/PSV-TEST1234" in html
        assert "phishsim.ai/verify/PSV-TEST1234" in html

        # Print styles
        assert "@media print" in html


def test_public_verify_endpoint(client):
    """Public /verify endpoint handles verification requests."""
    # Missing/unknown ID shows calm 404 message
    resp = client.get("/verify/PSV-UNKNOWN999")
    assert resp.status_code == 404
    html = resp.data.decode("utf-8")
    assert "Certificate not found" in html


# ══════════════════════════════════════════════════════════════
# 6. EMPLOYEE-FACING PAGES
# ══════════════════════════════════════════════════════════════
def test_simulated_awareness_wording():
    """simulated.html uses calm educational wording: 'This was a practice test. Here are 3 clues...'."""
    with app.test_request_context("/"):
        from flask import render_template
        html = render_template("simulated.html", flags=[], scenario="Payroll Security Update")

        assert "This was a practice test" in html
        assert "Here are 3 clues you could have spotted" in html
        assert "Simulation Triggered" not in html


def test_already_actioned_wording():
    """already_actioned.html uses calm educational tone with 3 clues."""
    with app.test_request_context("/"):
        from flask import render_template
        html_clicked = render_template("already_actioned.html", type="clicked", token="abc-123")
        assert "This was a practice test" in html_clicked
        assert "Here are 3 clues you could have spotted:" in html_clicked

        html_reported = render_template("already_actioned.html", type="reported", token="abc-123")
        assert "Great catch" in html_reported
        assert "threat reported" in html_reported
        assert "Here are 3 clues you successfully spotted:" in html_reported


def test_thank_you_for_reporting_wording():
    """thank_you_for_reporting.html uses calm educational tone with 3 clues."""
    with app.test_request_context("/"):
        from flask import render_template
        html = render_template("thank_you_for_reporting.html", tracking_id="xyz-789")
        assert "Great catch" in html
        assert "threat reported" in html
        assert "This was a practice test" in html
        assert "Here are 3 clues you spotted:" in html
        # CDN script removed
        assert "canvas-confetti" not in html


# ══════════════════════════════════════════════════════════════
# 7. LURE MASCOT SAFETY & DIALOG HIDING
# ══════════════════════════════════════════════════════════════
def test_lure_mascot_css_rules():
    """CSS hides mascot while any dialog is open and respects mobile bottom navigation."""
    css_path = os.path.join(os.path.dirname(__file__), "..", "static", "css", "app_shell.css")
    with open(css_path, "r", encoding="utf-8") as f:
        css = f.read()

    # Mascot hiding rules when dialog is open
    assert "body:has(dialog[open]) #pb-host" in css
    assert "body.has-modal-open #pb-host" in css
    assert "pointer-events: none !important" in css

    # Mascot mobile safe bottom distance
    assert "calc(84px + env(safe-area-inset-bottom, 0px))" in css
