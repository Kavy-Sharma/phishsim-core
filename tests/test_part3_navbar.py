import os
import re
import unittest
from unittest.mock import patch, MagicMock

import app as app_module
from app import app


class TestPart3Navbar(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        app.config["WTF_CSRF_ENABLED"] = False
        app.config["AUTH_SCHEMA_READY"] = True
        self.client = app.test_client()

    def _render_page_as_guest(self, path="/"):
        with self.client.session_transaction() as sess:
            sess.clear()
        return self.client.get(path)

    def _render_page_as_user(self, path="/dashboard", role="company_user", name="Alex Rivera", email="alex@example.com"):
        with self.client.session_transaction() as sess:
            sess["user_id"] = 201
            sess["user_name"] = name
            sess["user_email"] = email
            sess["role"] = role

        user_data = {
            "id": 201,
            "name": name,
            "email": email,
            "role": role,
            "company_domain": "example.com",
            "whitelabel_company_name": None,
        }
        with patch("app.current_user", return_value=user_data):
            return self.client.get(path)

    def test_signed_out_shows_marketing_navbar(self):
        """When signed out, the navbar is the marketing bar with Check, Train, Pricing, About."""
        res = self._render_page_as_guest("/")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)

        # Marketing triggers and links
        self.assertIn("Check something", html)
        self.assertIn("Train your team", html)
        self.assertIn("How it works", html)
        self.assertIn("Pricing", html)
        self.assertIn("About", html)
        self.assertIn("Sign in", html)

    @patch("app.get_db_connection")
    @patch("app.ensure_email_schema_once")
    @patch("app.recover_stuck_campaigns")
    @patch("app.run_due_scheduled_campaigns")
    def test_signed_in_navbar_is_app_bar_with_center_tabs(self, mock_sched, mock_rec, mock_schema, mock_get_db):
        """When signed in, navbar becomes an app bar with Dashboard, Campaigns, Tools, Reports."""
        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_cursor.fetchone.return_value = {"dept_count": 0, "total_employees": 0, "delivered_count": 0, "clicked_count": 0, "reported_count": 0, "total_count": 0, "pending_count": 0}
        mock_db.cursor.return_value = mock_cursor
        mock_get_db.return_value = mock_db

        res = self._render_page_as_user(path="/dashboard", role="company_user")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)

        # Logo links to /dashboard
        self.assertIn('href="/dashboard"', html)
        self.assertIn('class="brand-logo"', html)

        # Center tabs
        self.assertIn('id="app-nav-tabs"', html)
        self.assertIn("Dashboard", html)
        self.assertIn("Campaigns", html)
        self.assertIn("Tools", html)
        self.assertIn("Reports", html)

        # Sliding underline element exists
        self.assertIn('id="app-nav-underline"', html)

        # Marketing plain links leave the main desktop bar
        # (they should not be direct children of the top nav menu)
        self.assertNotIn('class="nav-plain-link">How it works<', html)
        self.assertNotIn('class="nav-plain-link">Pricing<', html)

        # Duplicate right-hand "Dashboard" link removed
        self.assertNotIn('class="nav-plain-link nav-active-section">Dashboard<', html)

    @patch("app.get_db_connection")
    @patch("app.ensure_email_schema_once")
    @patch("app.recover_stuck_campaigns")
    @patch("app.run_due_scheduled_campaigns")
    def test_tools_and_reports_compact_menus(self, mock_sched, mock_rec, mock_schema, mock_get_db):
        """Tools menu has 2 columns (PhishRecon, Header analyzer, URL decoder, Breach check, Threat analyzer)."""
        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_cursor.fetchone.return_value = {"dept_count": 0, "total_employees": 0, "delivered_count": 0, "clicked_count": 0, "reported_count": 0, "total_count": 0, "pending_count": 0}
        mock_db.cursor.return_value = mock_cursor
        mock_get_db.return_value = mock_db

        res = self._render_page_as_user(path="/dashboard", role="company_user")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)

        # Tools menu & items
        self.assertIn('id="app-tools-menu"', html)
        self.assertIn("PhishRecon", html)
        self.assertIn("Header analyzer", html)
        self.assertIn("URL decoder", html)
        self.assertIn("Password breach check", html)
        self.assertIn("Threat analyzer", html)

        # Reports menu & items
        self.assertIn('id="app-reports-menu"', html)
        self.assertIn("Campaign reports", html)
        self.assertIn("Briefing", html)

    @patch("app.get_db_connection")
    @patch("app.ensure_email_schema_once")
    @patch("app.recover_stuck_campaigns")
    @patch("app.run_due_scheduled_campaigns")
    def test_notifications_bell_hidden_since_no_backend_system(self, mock_sched, mock_rec, mock_schema, mock_get_db):
        """Notification bell must be hidden because no notification system exists in backend."""
        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_cursor.fetchone.return_value = {"dept_count": 0, "total_employees": 0, "delivered_count": 0, "clicked_count": 0, "reported_count": 0, "total_count": 0, "pending_count": 0}
        mock_db.cursor.return_value = mock_cursor
        mock_get_db.return_value = mock_db

        res = self._render_page_as_user(path="/dashboard", role="company_user")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)

        # Must not fake an in-app notification bell
        self.assertNotIn('id="nav-notifications-bell"', html)
        self.assertNotIn('class="nav-bell-active"', html)

    @patch("app.get_db_connection")
    @patch("app.ensure_email_schema_once")
    @patch("app.recover_stuck_campaigns")
    @patch("app.run_due_scheduled_campaigns")
    def test_theme_toggle_is_simple_icon_button(self, mock_sched, mock_rec, mock_schema, mock_get_db):
        """Theme toggle is a clean sun/moon icon button, not the glowing pill switch."""
        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_cursor.fetchone.return_value = {"dept_count": 0, "total_employees": 0, "delivered_count": 0, "clicked_count": 0, "reported_count": 0, "total_count": 0, "pending_count": 0}
        mock_db.cursor.return_value = mock_cursor
        mock_get_db.return_value = mock_db

        res = self._render_page_as_user(path="/dashboard", role="company_user")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)

        # Has id="theme-toggle" and class="theme-toggle-pill" (consistent across all states)
        self.assertIn('id="theme-toggle"', html)
        self.assertIn('class="theme-toggle-pill"', html)
        self.assertIn('class="theme-track-icons"', html)

    @patch("app.get_db_connection")
    @patch("app.ensure_email_schema_once")
    @patch("app.recover_stuck_campaigns")
    @patch("app.run_due_scheduled_campaigns")
    def test_upgrade_button_visible_for_free_hidden_for_admin_and_pro(self, mock_sched, mock_rec, mock_schema, mock_get_db):
        """Upgrade outline button appears next to avatar for Free users only."""
        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_cursor.fetchone.return_value = {"dept_count": 0, "total_employees": 0, "delivered_count": 0, "clicked_count": 0, "reported_count": 0, "total_count": 0, "pending_count": 0}
        mock_db.cursor.return_value = mock_cursor
        mock_get_db.return_value = mock_db

        # Free user -> Upgrade button visible
        res_free = self._render_page_as_user(path="/dashboard", role="company_user")
        html_free = res_free.get_data(as_text=True)
        self.assertIn('id="app-upgrade-btn"', html_free)
        self.assertIn("Upgrade", html_free)

        # Admin user -> Upgrade button absent, Admin menu link visible
        res_admin = self._render_page_as_user(path="/dashboard", role="admin")
        html_admin = res_admin.get_data(as_text=True)
        self.assertNotIn('id="app-upgrade-btn"', html_admin)
        self.assertIn('href="/admin"', html_admin)

        # Pro user -> Upgrade button absent, Admin menu link absent
        res_pro = self._render_page_as_user(path="/dashboard", role="pro")
        html_pro = res_pro.get_data(as_text=True)
        self.assertNotIn('id="app-upgrade-btn"', html_pro)
        self.assertNotIn('href="/admin"', html_pro)

    @patch("app.get_db_connection")
    @patch("app.ensure_email_schema_once")
    @patch("app.recover_stuck_campaigns")
    @patch("app.run_due_scheduled_campaigns")
    def test_avatar_menu_card_contents(self, mock_sched, mock_rec, mock_schema, mock_get_db):
        """Avatar menu card shows user name, email, plan badge, Profile, Billing, Help, Sign out."""
        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_cursor.fetchone.return_value = {"dept_count": 0, "total_employees": 0, "delivered_count": 0, "clicked_count": 0, "reported_count": 0, "total_count": 0, "pending_count": 0}
        mock_db.cursor.return_value = mock_cursor
        mock_get_db.return_value = mock_db

        res = self._render_page_as_user(path="/dashboard", role="company_user", name="Sam Altman", email="sam@openai.com")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)

        self.assertIn("Sam Altman", html)
        self.assertIn("sam@openai.com", html)
        self.assertIn('class="app-avatar-circle"', html)
        self.assertIn("SA", html)  # Initials

        # Links in account card
        self.assertIn('href="/profile"', html)
        self.assertIn("Profile & security", html)
        self.assertIn('href="/billing"', html)
        self.assertIn("Billing & plan", html)
        self.assertIn("Help & resources", html)
        self.assertIn('href="/logout"', html)
        self.assertIn("Sign out", html)

    @patch("app.get_db_connection")
    @patch("app.ensure_email_schema_once")
    @patch("app.recover_stuck_campaigns")
    @patch("app.run_due_scheduled_campaigns")
    def test_command_palette_and_mobile_bottom_nav(self, mock_sched, mock_rec, mock_schema, mock_get_db):
        """Command palette dialog and mobile bottom nav tab bar are present."""
        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_cursor.fetchone.return_value = {"dept_count": 0, "total_employees": 0, "delivered_count": 0, "clicked_count": 0, "reported_count": 0, "total_count": 0, "pending_count": 0}
        mock_db.cursor.return_value = mock_cursor
        mock_get_db.return_value = mock_db

        res = self._render_page_as_user(path="/dashboard", role="company_user")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)

        # Search button with shortcut
        self.assertIn('id="nav-search-trigger"', html)
        self.assertIn("Search…", html)
        self.assertIn("⌘K", html)

        # Command palette dialog
        self.assertIn('id="command-palette-dialog"', html)
        self.assertIn('id="command-palette-input"', html)

        # Mobile bottom tab bar
        self.assertIn('id="app-bottom-nav"', html)
        self.assertIn("Dashboard", html)
        self.assertIn("Campaigns", html)
        self.assertIn("You", html)


if __name__ == "__main__":
    unittest.main()
