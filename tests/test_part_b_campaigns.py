import io
import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime

from app import app, is_campaign_finished, format_scenario_label


class TestPartBCampaignsHubAndWizard(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        app.config["WTF_CSRF_ENABLED"] = False
        self.client = app.test_client()

    def _auth_user(self, role="company_user", user_id=101, domain="acme-corp.com"):
        with self.client.session_transaction() as sess:
            sess["user_id"] = user_id
            sess["user_name"] = "Alex Rivera"
            sess["user_email"] = f"alex@{domain}"
            sess["role"] = role
            sess["company_domain"] = domain

    # ══════════════════════════════════════════════════════════════════
    # B1. /campaigns Page & Hub Tests
    # ══════════════════════════════════════════════════════════════════

    @patch("app.get_db_connection")
    @patch("app.current_user")
    def test_campaigns_page_renders_with_real_metrics_and_saved_views(self, mock_user, mock_get_db):
        """B1: /campaigns full page renders with saved views, list/grid toggle, and zero fake numbers."""
        mock_user.return_value = {
            "id": 101,
            "name": "Alex Rivera",
            "email": "alex@acme-corp.com",
            "role": "company_user",
            "company_domain": "acme-corp.com"
        }
        self._auth_user()

        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {
                "id": 12,
                "name": "Q3 Password Reset Drill",
                "scenario_type": "it_reset",
                "status": "launched",
                "company_domain": "acme-corp.com",
                "created_at": "2026-09-15 10:00:00",
                "delivery_mode": "preview",
                "employee_count": 25,
                "emails_sent": 25,
                "emails_failed": 0,
                "opens": 20,
                "clicks": 3,
                "reports": 12
            },
            {
                "id": 11,
                "name": "Urgent Invoice Test",
                "scenario_type": "urgent_invoice",
                "status": "launched",
                "company_domain": "acme-corp.com",
                "created_at": "2026-08-01 10:00:00",
                "delivery_mode": "preview",
                "employee_count": 25,
                "emails_sent": 25,
                "emails_failed": 0,
                "opens": 18,
                "clicks": 6,
                "reports": 4
            }
        ]
        mock_db.cursor.return_value = mock_cursor
        mock_get_db.return_value = mock_db

        res = self.client.get("/campaigns")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)

        # Page title & navigation elements
        self.assertIn("Campaigns", html)
        self.assertIn("New campaign", html)
        self.assertIn("Compare (select 2)", html)

        # Saved views
        self.assertIn("All (2)", html)
        self.assertIn("Needs attention (1)", html)  # id 11 has click rate 24% (> 20%)
        self.assertIn("Finished (2)", html)

        # Canonical scenario labels mapped correctly
        self.assertIn("IT password reset", html)
        self.assertIn("Urgent invoice", html)

        # List & Grid elements
        self.assertIn('id="pane-view-list"', html)
        self.assertIn('id="pane-view-grid"', html)

    @patch("app.get_db_connection")
    @patch("app.current_user")
    def test_campaigns_empty_state_truth_rule(self, mock_user, mock_get_db):
        """B1 Truth rule: When no campaigns exist, shows honest empty state without invented benchmarks."""
        mock_user.return_value = {
            "id": 102,
            "name": "New User",
            "email": "user@brandnew.com",
            "role": "company_user",
            "company_domain": "brandnew.com"
        }
        self._auth_user(user_id=102, domain="brandnew.com")

        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_db.cursor.return_value = mock_cursor
        mock_get_db.return_value = mock_db

        res = self.client.get("/campaigns")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)

        # Honest empty state present
        self.assertIn("No campaigns yet", html)
        self.assertIn("Launch first drill", html)
        # Never shows invented metrics to new user
        self.assertNotIn("20.7% industry avg", html)

    @patch("app._fetch_user_campaigns")
    @patch("app.current_user")
    def test_compare_endpoint_side_by_side(self, mock_user, mock_fetch):
        """B1 Compare feature: Computes side-by-side funnel conversion, score delta, and click/report deltas."""
        mock_user.return_value = {
            "id": 101,
            "role": "company_user",
            "company_domain": "acme-corp.com"
        }
        self._auth_user()

        mock_fetch.return_value = [
            {
                "id": 1,
                "name": "Campaign Alpha",
                "scenario_type": "it_reset",
                "company_domain": "acme-corp.com",
                "emails_sent": 50,
                "opens": 40,
                "clicks": 15,
                "reports": 10,
                "open_rate": 80.0,
                "click_rate": 30.0,
                "report_rate": 20.0,
                "hss": {"score": 55},
                "created_at": "2026-07-01"
            },
            {
                "id": 2,
                "name": "Campaign Beta",
                "scenario_type": "hr_policy",
                "company_domain": "acme-corp.com",
                "emails_sent": 50,
                "opens": 45,
                "clicks": 5,
                "reports": 25,
                "open_rate": 90.0,
                "click_rate": 10.0,
                "report_rate": 50.0,
                "hss": {"score": 85},
                "created_at": "2026-08-01"
            }
        ]

        res = self.client.get("/api/campaigns/compare?c1=1&c2=2")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["ok"])

        # Delta checks
        deltas = data["deltas"]
        self.assertEqual(deltas["score"], 30)          # 85 - 55 = +30 pts improvement
        self.assertEqual(deltas["click_rate"], -20.0)  # 10.0 - 30.0 = -20.0 pts (dropped click exposure)
        self.assertEqual(deltas["report_rate"], 30.0)  # 50.0 - 20.0 = +30.0 pts (reporting improved)
        self.assertIn("Click exposure dropped by 20.0 pts", data["summary"])

    # ══════════════════════════════════════════════════════════════════
    # B2. CSV Upload Edge Cases (upload_employees)
    # ══════════════════════════════════════════════════════════════════

    @patch("app.get_db_connection")
    @patch("app.user_can_access_campaign")
    @patch("app.current_user")
    def test_csv_semicolon_delimiter_and_bom_support(self, mock_user, mock_access, mock_get_db):
        """B2 CSV: Semicolon delimiter (;) and UTF-8 BOM are handled seamlessly."""
        mock_user.return_value = {"id": 101, "role": "company_user", "company_domain": "acme.corp"}
        mock_access.return_value = {"id": 5, "user_id": 101, "company_domain": "acme.corp"}
        self._auth_user()

        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_db.cursor.return_value = mock_cursor
        mock_get_db.return_value = mock_db

        # Semicolon CSV with BOM
        csv_text = "\ufeffEmail;Name;Department;Role\r\nalice@acme.corp;Alice Smith;Engineering;Dev\r\nbob@acme.corp;Bob Jones;Finance;Analyst\r\n"
        data = {
            "employee_csv": (io.BytesIO(csv_text.encode("utf-8-sig")), "targets.csv")
        }

        res = self.client.post("/upload-employees/5", data=data, content_type="multipart/form-data")
        # executemany was called with 2 rows
        self.assertTrue(mock_cursor.executemany.called)
        args, _ = mock_cursor.executemany.call_args
        inserted_rows = args[1]
        self.assertEqual(len(inserted_rows), 2)
        self.assertEqual(inserted_rows[0][1], "alice@acme.corp")
        self.assertEqual(inserted_rows[1][1], "bob@acme.corp")

    @patch("app.get_db_connection")
    @patch("app.user_can_access_campaign")
    @patch("app.current_user")
    def test_csv_deduplication_and_bad_email_skipping(self, mock_user, mock_access, mock_get_db):
        """B2 CSV: Duplicate emails and invalid emails are filtered out accurately."""
        mock_user.return_value = {"id": 101, "role": "company_user", "company_domain": "acme.corp"}
        mock_access.return_value = {"id": 5, "user_id": 101}
        self._auth_user()

        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [{"email": "existing@acme.corp"}]
        mock_db.cursor.return_value = mock_cursor
        mock_get_db.return_value = mock_db

        csv_text = (
            "email,name\r\n"
            "valid1@acme.corp,Valid One\r\n"
            "valid1@acme.corp,Duplicate Within Batch\r\n"
            "existing@acme.corp,Already In DB\r\n"
            "not-an-email,Bad Syntax\r\n"
            "valid2@acme.corp,Valid Two\r\n"
        )
        data = {
            "employee_csv": (io.BytesIO(csv_text.encode("utf-8")), "targets.csv")
        }

        res = self.client.post("/upload-employees/5", data=data, content_type="multipart/form-data")
        args, _ = mock_cursor.executemany.call_args
        inserted_rows = args[1]
        # Only valid1@acme.corp and valid2@acme.corp should be inserted
        self.assertEqual(len(inserted_rows), 2)
        emails = [r[1] for r in inserted_rows]
        self.assertIn("valid1@acme.corp", emails)
        self.assertIn("valid2@acme.corp", emails)

    @patch("app.get_db_connection")
    @patch("app.user_can_access_campaign")
    @patch("app.current_user")
    def test_csv_empty_file_rejected(self, mock_user, mock_access, mock_get_db):
        """B2 CSV: Empty CSV is rejected with clean error message."""
        mock_user.return_value = {"id": 101, "name": "Alex Rivera", "email": "alex@acme.corp", "role": "company_user"}
        mock_access.return_value = {
            "id": 5, "user_id": 101, "name": "Q4 Drill", "scenario_type": "hr_policy",
            "company_domain": "acme.corp", "delivery_mode": "preview", "status": "draft"
        }
        self._auth_user()

        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_db.cursor.return_value = mock_cursor
        mock_get_db.return_value = mock_db

        data = {
            "employee_csv": (io.BytesIO(b""), "empty.csv")
        }
        res = self.client.post("/upload-employees/5?wizard=true", data=data, content_type="multipart/form-data", follow_redirects=True)
        html = res.get_data(as_text=True)
        self.assertIn("The uploaded CSV file is empty", html)

    @patch("app.get_db_connection")
    @patch("app.user_can_access_campaign")
    @patch("app.current_user")
    def test_csv_large_batch_insertion(self, mock_user, mock_access, mock_get_db):
        """B2 CSV: High volume list (e.g. 500 rows) is inserted efficiently using batch executemany."""
        mock_user.return_value = {"id": 101, "role": "pro"}
        mock_access.return_value = {"id": 8, "user_id": 101}
        self._auth_user(role="pro")

        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_db.cursor.return_value = mock_cursor
        mock_get_db.return_value = mock_db

        rows = ["email,name,department"] + [f"user{i}@corp.com,User {i},IT" for i in range(500)]
        csv_bytes = "\r\n".join(rows).encode("utf-8")
        data = {
            "employee_csv": (io.BytesIO(csv_bytes), "500_targets.csv")
        }

        res = self.client.post("/upload-employees/8", data=data, content_type="multipart/form-data")
        self.assertTrue(mock_cursor.executemany.called)
        args, _ = mock_cursor.executemany.call_args
        self.assertEqual(len(args[1]), 500)

    # ══════════════════════════════════════════════════════════════════
    # B2. Live-Send Confirmation Barrier
    # ══════════════════════════════════════════════════════════════════

    @patch("app.get_db_connection")
    @patch("app.user_can_access_campaign")
    @patch("app.current_user")
    def test_live_send_requires_typing_send_confirmation(self, mock_user, mock_access, mock_get_db):
        """B2 Safety Barrier: Live send (smtp mode) requires typing SEND to dispatch."""
        mock_user.return_value = {"id": 101, "role": "pro"}
        mock_access.return_value = {"id": 9, "user_id": 101, "delivery_mode": "smtp", "status": "draft"}
        self._auth_user(role="pro")

        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"count": 10}
        mock_db.cursor.return_value = mock_cursor
        mock_get_db.return_value = mock_db

        # Attempt 1: Without typing SEND -> rejected with 400 or redirect flash
        res1 = self.client.post("/launch-campaign/9", data={"confirm_send": "yes"}, headers={"X-Requested-With": "XMLHttpRequest"})
        self.assertEqual(res1.status_code, 400)
        self.assertIn("Type SEND to confirm", res1.get_json()["error"])

        # Attempt 2: With exact confirmation 'SEND' -> accepted
        with patch("threading.Thread"):
            res2 = self.client.post("/launch-campaign/9", data={"confirm_send": "SEND"}, follow_redirects=False)
            self.assertEqual(res2.status_code, 302)

    # ══════════════════════════════════════════════════════════════════
    # B2. Wizard & Old Routes Backward Compatibility
    # ══════════════════════════════════════════════════════════════════

    @patch("app.get_db_connection")
    @patch("app.user_can_access_campaign")
    @patch("app.current_user")
    def test_wizard_and_old_routes_backward_compatibility(self, mock_user, mock_access, mock_get_db):
        """B2 Routes: /new-campaign, /new-campaign/upload/<id>, and /new-campaign/launch/<id> all resolve 200 OK."""
        mock_user.return_value = {"id": 101, "name": "Alex Rivera", "email": "alex@acme.corp", "role": "company_user", "company_domain": "acme.corp"}
        mock_access.return_value = {"id": 15, "name": "Test Campaign", "company_domain": "acme.corp", "scenario_type": "it_reset", "delivery_mode": "preview", "status": "draft"}
        self._auth_user()

        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_cursor.fetchone.return_value = {"count": 5}
        mock_db.cursor.return_value = mock_cursor
        mock_get_db.return_value = mock_db

        # Route 1: /new-campaign
        r1 = self.client.get("/new-campaign")
        self.assertEqual(r1.status_code, 200)
        h1 = r1.get_data(as_text=True)
        self.assertIn("Campaign setup", h1)
        self.assertIn("CEO fraud", h1)
        self.assertIn("IT password reset", h1)
        self.assertIn("Live simulation preview", h1)

        # Route 2: /new-campaign/upload/15
        r2 = self.client.get("/new-campaign/upload/15")
        self.assertEqual(r2.status_code, 200)
        h2 = r2.get_data(as_text=True)
        self.assertIn("Add people", h2)
        self.assertIn("Drop your recipient CSV here", h2)

        # Route 3: /new-campaign/launch/15
        r3 = self.client.get("/new-campaign/launch/15")
        self.assertEqual(r3.status_code, 200)
        h3 = r3.get_data(as_text=True)
        self.assertIn("Review &amp; dispatch", h3)
        self.assertIn("Pre-launch checklist", h3)


if __name__ == "__main__":
    unittest.main()
