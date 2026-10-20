import io
import json
import os
import sys
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from flask_wtf.csrf import generate_csrf
from app import (
    app,
    get_decoy_cipher,
    encrypt_decoy_password,
    decrypt_decoy_password,
    safe_imap_ssl_connect,
)
import app as app_module


class TestPart3SecurityAndPlumbing(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        app.config["WTF_CSRF_ENABLED"] = True
        app.config["SECRET_KEY"] = "test-secret-key-for-part3"
        self.client = app.test_client()

    # ────────────────────────────────────────────────────────────────
    # 1. Route Redirection & Access Control
    # ────────────────────────────────────────────────────────────────
    def test_ai_risk_advisor_301_redirect(self):
        """GET /ai-risk-advisor must 301-redirect to /briefing so external links don't break."""
        res = self.client.get("/ai-risk-advisor", follow_redirects=False)
        self.assertEqual(res.status_code, 301)
        self.assertTrue(res.headers.get("Location", "").endswith("/briefing"))

    @patch("app.current_user")
    @patch("app.get_db_connection")
    @patch("app.ensure_email_schema_once")
    @patch("app.recover_stuck_campaigns")
    @patch("app.run_due_scheduled_campaigns")
    def test_briefing_accessible_to_logged_in_free_user(
        self, mock_sched, mock_rec, mock_schema, mock_get_db, mock_current_user
    ):
        """Any logged-in user (including Free tier) can view their Risk Briefing without redirect to /billing."""
        mock_current_user.return_value = {
            "id": 101,
            "name": "Free User",
            "email": "free_user@example.com",
            "role": "company_user",
            "company_domain": "example.com",
            "whitelabel_company_name": None,
        }
        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_cursor.fetchone.return_value = {
            "total_employees": 0,
            "offender_count": 0,
            "never_reported": 0,
            "last_run": None,
        }
        mock_db.cursor.return_value = mock_cursor
        mock_get_db.return_value = mock_db

        with self.client.session_transaction() as sess:
            sess["user_id"] = 101

        res = self.client.get("/briefing", follow_redirects=False)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Risk Briefing", res.data)
        # Should show honest empty state when 0 campaigns
        self.assertIn(b"No campaigns yet", res.data)

    # ────────────────────────────────────────────────────────────────
    # 2. CSRF Enforcement on Remediation Endpoints
    # ────────────────────────────────────────────────────────────────
    @patch("app.current_user")
    def test_remediation_endpoints_csrf_enforced(self, mock_current_user):
        """POST remediation endpoints must reject requests missing a valid CSRF token with 400 Bad Request."""
        mock_current_user.return_value = {
            "id": 102,
            "name": "Pro User",
            "email": "pro_user@example.com",
            "role": "pro",
            "company_domain": "example.com",
        }
        with self.client.session_transaction() as sess:
            sess["user_id"] = 102

        endpoints = [
            "/api/remediate/deploy-decoy",
            "/api/remediate/check-decoys",
            "/remediate/micro-training",
            "/api/remediate/domain-lockdown",
            "/api/profile/whitelabel",
        ]
        for ep in endpoints:
            res = self.client.post(ep, data={"dummy": "data"})
            self.assertEqual(res.status_code, 400, f"Endpoint {ep} allowed POST without CSRF token!")

    # ────────────────────────────────────────────────────────────────
    # 3. Free User Pro-Gating on Sensitive Endpoints
    # ────────────────────────────────────────────────────────────────
    @patch("app.current_user")
    def test_free_user_pro_gating(self, mock_current_user):
        """Free users must be rejected with 403 Forbidden on Pro-only remediation and recon endpoints."""
        mock_current_user.return_value = {
            "id": 103,
            "name": "Free User",
            "email": "free_user@example.com",
            "role": "company_user",
            "company_domain": "example.com",
        }
        with self.client.session_transaction() as sess:
            sess["user_id"] = 103

        # Generate valid CSRF token for the session via login GET
        with self.client:
            self.client.get("/login")
            csrf_token = generate_csrf()

        headers = {"X-CSRFToken": csrf_token}

        # POST /api/remediate/deploy-decoy -> 403
        res = self.client.post("/api/remediate/deploy-decoy", data={"decoy_email": "decoy@example.com"}, headers=headers)
        self.assertEqual(res.status_code, 403)
        self.assertIn("Pro subscription required", res.get_json().get("error", ""))

        # GET /api/remediate/get-decoys -> 403
        res = self.client.get("/api/remediate/get-decoys")
        self.assertEqual(res.status_code, 403)

        # POST /api/remediate/check-decoys -> 403
        res = self.client.post("/api/remediate/check-decoys", headers=headers)
        self.assertEqual(res.status_code, 403)

        # POST /remediate/micro-training -> 403
        res = self.client.post("/remediate/micro-training", headers=headers)
        self.assertEqual(res.status_code, 403)

        # GET /api/recon/history -> 403
        res = self.client.get("/api/recon/history")
        self.assertEqual(res.status_code, 403)

        # GET /api/recon/compare/<domain> -> 403
        res = self.client.get("/api/recon/compare/example.com")
        self.assertEqual(res.status_code, 403)

        # GET /api/recon/export/json?domain=example.com -> 403
        res = self.client.get("/api/recon/export/json?domain=example.com")
        self.assertEqual(res.status_code, 403)

        # POST /api/profile/whitelabel -> 403
        res = self.client.post("/api/profile/whitelabel", data={"whitelabel_company_name": "Hacked"}, headers=headers)
        self.assertEqual(res.status_code, 403)

    # ────────────────────────────────────────────────────────────────
    # 4. Decoy Credential Encryption & Non-Leakage
    # ────────────────────────────────────────────────────────────────
    def test_decoy_password_encryption_at_rest(self):
        """Decoy passwords must be encrypted with Fernet and decrypted reliably."""
        secret = "SuperSecretDecoyPassw0rd!#$"
        ciphertext = encrypt_decoy_password(secret)
        self.assertNotEqual(secret, ciphertext)
        self.assertTrue(ciphertext.startswith("gAAAAA"), "Fernet token format expected")
        decrypted = decrypt_decoy_password(ciphertext)
        self.assertEqual(secret, decrypted)

    @patch("app.current_user")
    @patch("app.get_db_connection")
    def test_get_decoys_never_returns_password(self, mock_get_db, mock_current_user):
        """GET /api/remediate/get-decoys must never return imap_pass to the browser."""
        mock_current_user.return_value = {
            "id": 104,
            "name": "Pro Admin",
            "email": "pro_admin@example.com",
            "role": "pro",
            "company_domain": "example.com",
        }
        with self.client.session_transaction() as sess:
            sess["user_id"] = 104

        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {
                "id": 1,
                "email": "decoy@example.com",
                "label": "Trap 1",
                "status": "active",
                "imap_host": "imap.example.com",
                "imap_port": 993,
                "imap_user": "decoy@example.com",
                "created_at": None,
            }
        ]
        mock_db.cursor.return_value = mock_cursor
        mock_get_db.return_value = mock_db

        res = self.client.get("/api/remediate/get-decoys")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("success"))
        for dec in data.get("decoys", []):
            self.assertNotIn("imap_pass", dec)
            self.assertNotIn("password", dec)

    # ────────────────────────────────────────────────────────────────
    # 5. Decoy SSRF Prevention
    # ────────────────────────────────────────────────────────────────
    def test_safe_imap_ssl_connect_rejects_private_ips_and_bad_ports(self):
        """safe_imap_ssl_connect must strictly reject private, loopback, link-local IPs and non-993 ports."""
        unsafe_targets = [
            ("127.0.0.1", 993),
            ("localhost", 993),
            ("10.0.0.1", 993),
            ("192.168.1.1", 993),
            ("169.254.169.254", 993),
            ("imap.gmail.com", 25),   # Disallowed port
            ("imap.gmail.com", 80),   # Disallowed port
            ("imap.gmail.com", 143),  # Non-SSL port
        ]
        for host, port in unsafe_targets:
            with self.assertRaises(ValueError):
                safe_imap_ssl_connect(host, port=port, timeout=1)

    # ────────────────────────────────────────────────────────────────
    # 6. Domain Lockdown Security (No Demo Fallback)
    # ────────────────────────────────────────────────────────────────
    @patch("app.current_user")
    def test_domain_lockdown_rejects_missing_company_domain(self, mock_current_user):
        """User with no company domain must receive 400 Bad Request, never falling back to demo-corp.com."""
        mock_current_user.return_value = {
            "id": 105,
            "name": "No Domain",
            "email": "nodomain@example.com",
            "role": "company_user",
            "company_domain": None,
        }
        with self.client.session_transaction() as sess:
            sess["user_id"] = 105

        with self.client:
            self.client.get("/login")
            csrf_token = generate_csrf()

        res = self.client.post("/api/remediate/domain-lockdown", headers={"X-CSRFToken": csrf_token})
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertFalse(data.get("success"))
        self.assertIn("company domain", data.get("error", "").lower())

    # ────────────────────────────────────────────────────────────────
    # 7. PhishRecon Code Switch (PHISHRECON_REQUIRE_PRO)
    # ────────────────────────────────────────────────────────────────
    def test_phishrecon_code_switch_behavior(self):
        """Tests both False and True states of the PHISHRECON_REQUIRE_PRO switch."""
        # State A: PHISHRECON_REQUIRE_PRO = False
        app_module.PHISHRECON_REQUIRE_PRO = False

        # Anonymous visiting /exposure-report -> 200 OK
        res = self.client.get("/exposure-report")
        self.assertEqual(res.status_code, 200)

        # State B: PHISHRECON_REQUIRE_PRO = True
        try:
            app_module.PHISHRECON_REQUIRE_PRO = True

            # 1. Anonymous visitor GET /exposure-report -> redirect to /login
            res = self.client.get("/exposure-report", follow_redirects=False)
            self.assertEqual(res.status_code, 302)
            self.assertIn("/login", res.headers.get("Location", ""))

            # 2. Anonymous visitor POST /api/exposure-report -> 401 JSON
            res = self.client.post("/api/exposure-report", json={"domain": "example.com"})
            self.assertEqual(res.status_code, 401)
            self.assertEqual(res.get_json().get("login_url"), "/login")

            # 3. Logged-in Free user GET /exposure-report -> redirect to /billing
            with patch("app.current_user") as mock_user:
                mock_user.return_value = {
                    "id": 106,
                    "name": "Free User",
                    "role": "company_user",
                    "email": "free@test.com",
                    "company_domain": "example.com",
                }
                with self.client.session_transaction() as sess:
                    sess["user_id"] = 106

                res = self.client.get("/exposure-report", follow_redirects=False)
                self.assertEqual(res.status_code, 302)
                self.assertIn("/billing", res.headers.get("Location", ""))

                # 4. Logged-in Free user POST /api/exposure-report -> 403 JSON
                res = self.client.post("/api/exposure-report", json={"domain": "example.com"})
                self.assertEqual(res.status_code, 403)
                self.assertEqual(res.get_json().get("upgrade_url"), "/billing")

            # 5. Logged-in Pro user GET /exposure-report -> 200 OK
            with patch("app.current_user") as mock_user:
                mock_user.return_value = {
                    "id": 107,
                    "name": "Pro User",
                    "role": "pro",
                    "email": "pro@test.com",
                    "company_domain": "example.com",
                    "whitelabel_company_name": None,
                }
                with self.client.session_transaction() as sess:
                    sess["user_id"] = 107

                res = self.client.get("/exposure-report", follow_redirects=False)
                self.assertEqual(res.status_code, 200)

        finally:
            # Restore default state
            app_module.PHISHRECON_REQUIRE_PRO = False


if __name__ == "__main__":
    unittest.main()
