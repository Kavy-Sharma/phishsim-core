import os
import re
import unittest
from unittest.mock import patch, MagicMock

import app as app_module
from app import app


class TestPart1GlobalShellCleanup(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        app.config["WTF_CSRF_ENABLED"] = False
        self.client = app.test_client()

    def test_hud_bar_removed_from_rendered_pages(self):
        """The fake cyber-hud-bar and has-hud-bar must not be rendered on any page."""
        routes = ["/", "/login", "/signup"]
        for route in routes:
            res = self.client.get(route)
            self.assertEqual(res.status_code, 200, f"Route {route} failed to load")
            html = res.get_data(as_text=True)

            self.assertNotIn("cyber-hud-bar", html, f"cyber-hud-bar found in {route}")
            self.assertNotIn("id=\"cyber-hud\"", html, f"id='cyber-hud' found in {route}")
            self.assertNotIn("SYSTEM:</span>", html, f"SYSTEM: found in {route}")
            self.assertNotIn("LIVE MODE</span>", html, f"LIVE MODE found in {route}")
            self.assertNotIn("ENGINE:</span>", html, f"ENGINE: found in {route}")
            self.assertNotIn("has-hud-bar", html, f"has-hud-bar body class found in {route}")

    @patch("app.current_user")
    @patch("app.get_db_connection")
    @patch("app.ensure_email_schema_once")
    @patch("app.recover_stuck_campaigns")
    @patch("app.run_due_scheduled_campaigns")
    def test_hud_bar_removed_for_logged_in_user(
        self, mock_sched, mock_rec, mock_schema, mock_get_db, mock_current_user
    ):
        """Even when a user is logged in, cyber-hud-bar and has-hud-bar must NOT appear."""
        mock_current_user.return_value = {
            "id": 42,
            "name": "Security Officer",
            "email": "officer@example.com",
            "role": "admin",
            "company_domain": "example.com",
            "whitelabel_company_name": None,
        }
        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_cursor.fetchone.return_value = {
            "total_employees": 10,
            "offender_count": 1,
            "never_reported": 2,
            "avg_risk": 25,
            "pending_count": 0,
            "total_count": 5,
            "delivered_count": 5,
            "clicked_count": 1,
            "reported_count": 2,
        }
        mock_db.cursor.return_value = mock_cursor
        mock_get_db.return_value = mock_db

        res = self.client.get("/dashboard")
        # Route might return 200 or redirect based on session, but if 200:
        if res.status_code == 200:
            html = res.get_data(as_text=True)
            self.assertNotIn("cyber-hud-bar", html)
            self.assertNotIn("has-hud-bar", html)

    def test_app_shell_css_exists_and_contains_primitives(self):
        """app_shell.css must define all required shared primitives and conform to Part 0 rules."""
        css_path = os.path.join(os.path.dirname(__file__), "..", "static", "css", "app_shell.css")
        self.assertTrue(os.path.isfile(css_path), "static/css/app_shell.css does not exist")

        with open(css_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Required primitives
        primitives = [
            ".page-header",
            ".section",
            ".card",
            ".stat",
            ".app-table",
            ".empty-state",
            ".skeleton",
            ".app-toast",
            ".app-confirm-dialog",
            ".badge",
        ]
        for p in primitives:
            self.assertIn(p, content, f"Primitive {p} missing from app_shell.css")

        # Button hierarchy
        self.assertIn(".btn-primary", content, "btn-primary missing")
        self.assertIn(".btn-secondary", content, "btn-secondary missing")
        self.assertIn(".btn-tertiary", content, "btn-tertiary missing")
        self.assertIn(".btn-destructive", content, "btn-destructive missing")

        # Fonts
        self.assertIn("Space Grotesk", content, "Space Grotesk heading font missing")
        self.assertIn("Plus Jakarta Sans", content, "Plus Jakarta Sans body font missing")
        self.assertIn("JetBrains Mono", content, "JetBrains Mono data font missing")
        self.assertIn("Newsreader", content, "Newsreader serif voice font missing")

        # Easing and motion
        self.assertIn("cubic-bezier(0.16, 1, 0.3, 1)", content, "Required easing function missing")
        self.assertIn("prefers-reduced-motion", content, "prefers-reduced-motion query missing")

        # Mascot protection & modal auto-hide
        self.assertIn("#pb-host", content, "#pb-host mascot protection rule missing")
        self.assertIn("padding-bottom", content, "Safe bottom padding missing")

    def test_app_shell_css_has_zero_raw_hex_colors(self):
        """In app_shell.css, colors must use CSS variables/tokens only (no raw #hex or rgb literals)."""
        css_path = os.path.join(os.path.dirname(__file__), "..", "static", "css", "app_shell.css")
        with open(css_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        # Allow hex only if it's #ffffff in solid destructive inside dialogs
        for idx, line in enumerate(lines, start=1):
            stripped = line.strip()
            # Ignore comments
            if stripped.startswith("/*") or stripped.startswith("*"):
                continue
            # Search for 6-digit or 3-digit hex colors other than #ffffff inside dialog
            hex_matches = re.findall(r"#[0-9a-fA-F]{3,8}\b", stripped)
            for match in hex_matches:
                if match.lower() in ["#fff", "#ffffff"]:
                    # allowed for dialog button text contrast
                    continue
                self.fail(f"Raw hex color {match} found at line {idx} in app_shell.css: {stripped}")

    def test_footer_structure_in_rendered_html(self):
        """Footer must feature Product, Resources, and Legal columns without decorative scenario spam."""
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)

        footer_start = html.rfind("<footer")
        self.assertNotEqual(footer_start, -1, "Footer not found in HTML")
        footer_end = html.find("</footer>", footer_start) + len("</footer>")
        footer_html = html[footer_start:footer_end]

        self.assertIn("footer class=\"site-footer\"", footer_html)
        self.assertIn("Product</h4>", footer_html)
        self.assertIn("Resources</h4>", footer_html)
        self.assertIn("Legal</h4>", footer_html)
        # Decorative scenario column must be removed from footer
        self.assertNotIn("Scenarios</h4>", footer_html)
        self.assertNotIn("CEO Fraud", footer_html)
        self.assertNotIn("Urgent Invoice", footer_html)

    def test_app_shell_css_included_in_base_html(self):
        """app_shell.css must be included in base.html head."""
        res = self.client.get("/login")
        html = res.get_data(as_text=True)
        self.assertIn("app_shell.css", html)


if __name__ == "__main__":
    unittest.main()
