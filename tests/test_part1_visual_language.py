import os
import re
import unittest
from unittest.mock import patch, MagicMock

import app as app_module
from app import app


class TestPart1VisualLanguage(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        app.config["WTF_CSRF_ENABLED"] = False
        app.config["AUTH_SCHEMA_READY"] = True
        self.client = app.test_client()

    @patch("app.current_user")
    @patch("app.get_db_connection")
    @patch("app.ensure_email_schema_once")
    @patch("app.recover_stuck_campaigns")
    @patch("app.run_due_scheduled_campaigns")
    def _get_dashboard_html(
        self,
        mock_sched,
        mock_rec,
        mock_schema,
        mock_get_db,
        mock_current_user,
        query="",
    ):
        with self.client.session_transaction() as sess:
            sess["user_id"] = 101
            sess["user_name"] = "Priya Sharma"
            sess["user_email"] = "priya@example.com"
            sess["role"] = "admin"

        mock_current_user.return_value = {
            "id": 101,
            "name": "Priya Sharma",
            "email": "priya@example.com",
            "role": "admin",
            "company_domain": "example.com",
            "whitelabel_company_name": None,
        }
        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {
                "id": 1,
                "name": "Q3 Phishing Assessment",
                "status": "launched",
                "employee_count": 50,
                "emails_sent": 50,
                "opens": 30,
                "clicks": 6,
                "reports": 12,
                "created_at": "2026-10-21 09:00:00",
                "company_domain": "example.com",
            }
        ]
        mock_cursor.fetchone.return_value = {
            "dept_count": 3,
            "total_employees": 50,
            "offender_count": 2,
            "never_reported": 5,
            "avg_risk": 20.0,
            "pending_count": 0,
            "total_count": 1,
            "delivered_count": 50,
            "clicked_count": 6,
            "reported_count": 12,
            "score": 82,
            "delta": 2,
        }
        mock_db.cursor.return_value = mock_cursor
        mock_get_db.return_value = mock_db

        url = f"/dashboard{query}"
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        return res.get_data(as_text=True)

    def test_atmosphere_body_class_and_radial_background(self):
        """Dashboard renders with dash-view body class and static soft radial gradient (no animated blobs)."""
        html = self._get_dashboard_html()
        self.assertIn("dash-view", html, "body must have dash-view class")

        css_path = os.path.join(os.path.dirname(__file__), "..", "static", "css", "app_shell.css")
        with open(css_path, "r", encoding="utf-8") as f:
            css = f.read()

        # Static radial background on dash-view
        self.assertIn("body.dash-view", css)
        self.assertIn("radial-gradient", css)
        self.assertIn("var(--primary-dim)", css)
        # Static: no blob animations on the body background
        self.assertNotIn("@keyframes blob", css.lower())

    def test_single_primary_button_with_dark_text(self):
        """Only ONE primary button on the page ('New campaign') with dark text (NOT white)."""
        html = self._get_dashboard_html()

        # Find all primary buttons in rendered HTML (excluding <script> code blocks)
        html_dom = re.sub(r'<script.*?</script>', '', html, flags=re.DOTALL)
        primary_btn_matches = re.findall(
            r'<(?:a|button)[^>]+class="[^"]*\bbtn-primary\b[^"]*"[^>]*>(.*?)</(?:a|button)>',
            html_dom,
            re.DOTALL,
        )
        self.assertEqual(
            len(primary_btn_matches),
            1,
            f"Expected exactly 1 btn-primary on the dashboard, found {len(primary_btn_matches)}: {primary_btn_matches}",
        )
        self.assertIn("New campaign", primary_btn_matches[0])

        # Verify in CSS that .btn-primary has dark text token (NOT white)
        css_path = os.path.join(os.path.dirname(__file__), "..", "static", "css", "app_shell.css")
        with open(css_path, "r", encoding="utf-8") as f:
            css = f.read()

        self.assertIn(".btn-primary", css)
        self.assertIn("var(--btn-primary-text", css)

        # In style.css, dark text token must NOT be white
        style_path = os.path.join(os.path.dirname(__file__), "..", "static", "style.css")
        with open(style_path, "r", encoding="utf-8") as f:
            style_css = f.read()

        # In dark mode
        self.assertIn("--btn-primary-text: #090C15", style_css)
        # In light mode
        self.assertIn("--btn-primary-text: #042F2E", style_css)

    def test_secondary_and_tertiary_button_primitives(self):
        """Secondary button is transparent with border; tertiary is text-only."""
        css_path = os.path.join(os.path.dirname(__file__), "..", "static", "css", "app_shell.css")
        with open(css_path, "r", encoding="utf-8") as f:
            css = f.read()

        # Secondary: transparent with border
        self.assertIn(".btn-secondary", css)
        self.assertIn("background-color: transparent", css)
        self.assertIn("border: 1px solid var(--border-default)", css)

        # Tertiary: text only
        self.assertIn(".btn-tertiary", css)
        self.assertIn("border: 1px solid transparent", css)

    def test_card_primitives_hover_lift_and_hero_gradient_edge(self):
        """Cards have 16px radius, soft shadow, lift 2px on hover (200ms); Hero card has 1px top gradient edge."""
        css_path = os.path.join(os.path.dirname(__file__), "..", "static", "css", "app_shell.css")
        with open(css_path, "r", encoding="utf-8") as f:
            css = f.read()

        # 16px radius
        self.assertIn("--radius-card: 16px;", css)

        # 200ms lift on hover
        self.assertIn("transform: translateY(-2px)", css)
        self.assertIn("200ms", css)

        # Hero card only: 1px gradient edge (primary -> info) at top
        self.assertIn(".hero-stat-card::before", css)
        self.assertIn("height: 1px", css)
        self.assertIn("linear-gradient(90deg, var(--primary) 0%, var(--info) 100%)", css)

    def test_typography_scale_exact_values(self):
        """Page title 28px, card label 13px muted sentence case, big numbers 40px Space Grotesk tabular numerals, body 15px."""
        css_path = os.path.join(os.path.dirname(__file__), "..", "static", "css", "app_shell.css")
        with open(css_path, "r", encoding="utf-8") as f:
            css = f.read()

        # Page title 28px
        self.assertIn("font-size: 28px", css)

        # Card label 13px sentence case (no caps)
        self.assertIn("font-size: 13px", css)
        self.assertIn("text-transform: none", css)

        # Big numbers 40px Space Grotesk with tabular numerals
        self.assertIn("font-size: 40px", css)
        self.assertIn("tabular-nums", css)
        self.assertIn('"tnum"', css)

        # Body 15px
        self.assertIn("font-size: 15px", css)

    def test_light_theme_warm_off_white_and_darkened_teal(self):
        """Light theme must specify warm off-white page background and darkened teal for AA contrast."""
        style_path = os.path.join(os.path.dirname(__file__), "..", "static", "style.css")
        with open(style_path, "r", encoding="utf-8") as f:
            style_css = f.read()

        # Warm off-white page
        self.assertIn("--bg-base:        #F8F9FA", style_css)
        # White cards
        self.assertIn("--bg-surface:     #FFFFFF", style_css)
        # Darkened teal for AA compliance
        self.assertIn("--primary:        #0D9488", style_css)


if __name__ == "__main__":
    unittest.main()
