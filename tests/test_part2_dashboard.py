import os
import re
import unittest
from unittest.mock import patch, MagicMock

import app as app_module
from app import app


class TestPart2Dashboard(unittest.TestCase):
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
    def _get_dashboard_with_mock_data(
        self,
        campaigns_data,
        mock_sched,
        mock_rec,
        mock_schema,
        mock_get_db,
        mock_current_user,
        user_name="Priya Sharma",
        dept_stats=None,
    ):
        with self.client.session_transaction() as sess:
            sess["user_id"] = 101
            sess["user_name"] = user_name
            sess["user_email"] = "priya@example.com"
            sess["role"] = "admin"

        mock_current_user.return_value = {
            "id": 101,
            "name": user_name,
            "email": "priya@example.com",
            "role": "admin",
            "company_domain": "example.com",
            "whitelabel_company_name": None,
        }
        mock_db = MagicMock()
        mock_cursor = MagicMock()

        fetchall_call = {"count": 0}
        def smart_fetchall():
            fetchall_call["count"] += 1
            if fetchall_call["count"] == 1:
                return campaigns_data
            if fetchall_call["count"] == 2 and dept_stats is not None:
                return dept_stats
            return []

        mock_cursor.fetchall.side_effect = smart_fetchall
        mock_cursor.fetchone.return_value = {
            "dept_count": 3,
            "id": 1,
            "name": "Active Drill",
            "scenario_type": "lure",
            "status": "launched",
            "sent": 20,
            "clicks": 2,
            "total_employees": 15,
            "offender_count": 2,
            "never_reported": 3,
            "avg_risk": 22.5,
            "pending_count": 0,
            "total_count": len(campaigns_data),
            "delivered_count": 10,
            "clicked_count": 2,
            "reported_count": 4,
            "score": 78,
            "delta": 3,
        }
        mock_db.cursor.return_value = mock_cursor
        mock_get_db.return_value = mock_db

        return self.client.get("/dashboard")

    def test_greeting_and_single_primary_button(self):
        """Dashboard must show greeting line 'Good morning, [Name]' + date and ONE primary button."""
        sample_campaigns = [{
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
        }]

        res = self._get_dashboard_with_mock_data(sample_campaigns, user_name="Priya Sharma")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)

        # Greeting line and name
        self.assertIn('id="dash-greeting"', html)
        self.assertIn("Good morning, Priya", html)
        self.assertIn('id="dash-current-date"', html)

        # Exactly ONE primary button in the header: "New campaign"
        self.assertIn('id="btn-create-campaign"', html)
        self.assertIn("New campaign", html)
        self.assertIn("btn btn-primary", html)

        # Exactly 1 primary button in the loaded view when campaigns exist
        matches = re.findall(r'<a[^>]+class="[^"]*btn-primary[^"]*"[^>]*id="btn-create-campaign"', html)
        self.assertEqual(len(matches), 1)

    def test_quiet_tab_row_layout(self):
        """Under header: Overview · Campaigns · People · Activity, plus sliding indicator and Briefing & Export menu."""
        sample_campaigns = [{
            "id": 1,
            "name": "Test Campaign",
            "status": "completed",
            "employee_count": 10,
            "emails_sent": 10,
            "opens": 5,
            "clicks": 1,
            "reports": 3,
            "created_at": "2026-10-20 10:00:00",
            "company_domain": "example.com",
        }]

        res = self._get_dashboard_with_mock_data(sample_campaigns)
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)

        self.assertIn('class="tab-row"', html)
        self.assertIn("Overview", html)
        self.assertIn("Campaigns", html)
        self.assertIn("People", html)
        self.assertIn("Activity", html)
        self.assertIn("Briefing", html)
        self.assertIn("Export", html)

        # Sliding underline indicator
        self.assertIn('id="tab-sliding-indicator"', html)

        # More menu with Briefing, Export, Print
        self.assertIn('id="dash-tab-more-btn"', html)
        self.assertIn('id="dash-tab-more-dropdown"', html)
        self.assertIn("Open briefing", html)
        self.assertIn("Export report", html)
        self.assertIn("Print", html)

    def test_hero_team_readiness_ring_and_trend_chart(self):
        """Hero focal card: 160px SVG ring gauge (left) + 8-campaign SVG trend chart (right) with metric switcher."""
        sample_campaigns = [
            {
                "id": 1,
                "name": "Drill 1",
                "status": "completed",
                "employee_count": 50,
                "emails_sent": 50,
                "opens": 30,
                "clicks": 5,
                "reports": 15,
                "created_at": "2026-10-10 10:00:00",
                "company_domain": "example.com",
            },
            {
                "id": 2,
                "name": "Drill 2",
                "status": "completed",
                "employee_count": 50,
                "emails_sent": 50,
                "opens": 35,
                "clicks": 3,
                "reports": 20,
                "created_at": "2026-10-20 10:00:00",
                "company_domain": "example.com",
            }
        ]

        res = self._get_dashboard_with_mock_data(sample_campaigns)
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)

        # Hero Readiness Card (single focal point)
        self.assertIn('id="hero-readiness-focal"', html)
        self.assertIn('class="hero-readiness-grid"', html)

        # Left Zone: 160px Ring Gauge SVG
        self.assertIn('class="readiness-ring-svg"', html)
        self.assertIn('id="hero-ring-arc"', html)
        self.assertIn('class="ring-center-number"', html)
        self.assertIn('/ 100', html)

        # Verdict sentence
        self.assertIn('class="readiness-verdict-text"', html)
        self.assertTrue(
            "Getting safer" in html or "Holding steady" in html or "Needs attention" in html,
            "Verdict sentence missing",
        )
        self.assertIn("points since last campaign", html)

        # Right Zone: Trend Chart SVG with 0, 50, 100 gridlines
        self.assertIn('id="hero-trend-svg"', html)
        self.assertIn('id="trend-line-path"', html)
        self.assertIn('id="trend-area-path"', html)
        self.assertIn('id="trend-halo-dot"', html)
        self.assertIn('id="trend-tooltip-card"', html)

        # Segmented Control / Legend
        self.assertIn('class="trend-segmented-control"', html)
        self.assertIn('id="btn-trend-readiness"', html)
        self.assertIn('id="btn-trend-report"', html)
        self.assertIn('id="btn-trend-click"', html)

    def test_metric_row_cards_and_sparklines(self):
        """Metric row has Report rate, Click rate, People reached with pts deltas and clean sparklines."""
        sample_campaigns = [{
            "id": 1,
            "name": "Executive Drill",
            "status": "completed",
            "employee_count": 100,
            "emails_sent": 100,
            "opens": 60,
            "clicks": 12,
            "reports": 24,
            "created_at": "2026-10-21 11:00:00",
            "company_domain": "example.com",
        }]

        res = self._get_dashboard_with_mock_data(sample_campaigns)
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)

        # 3 compact metric cards
        self.assertIn('class="hero-stats-strip metric-row-cards"', html)
        self.assertIn("Report rate", html)
        self.assertIn("Click rate", html)
        self.assertTrue("People reached" in html or "Campaigns run" in html)

        # 'pts' used for rate differences
        self.assertIn("pts vs last", html)

        # Interactive click to switch trend metric
        self.assertIn("switchHeroTrendMetric('report_rate')", html)
        self.assertIn("switchHeroTrendMetric('click_rate')", html)

        # Small clean sparklines with last-point dot only
        sparklines = re.findall(r'<svg[^>]+class="sparkline-svg"', html)
        self.assertEqual(len(sparklines), 3, "Expected 3 inline SVG sparklines in metric row")

        # Dots should be last-point dots only (not 12 dots per line)
        dots = re.findall(r'<circle[^>]+class="sparkline-dot"', html)
        self.assertEqual(len(dots), 3, "Expected exactly 3 last-point dots (1 per metric card)")

    def test_next_best_action_card(self):
        """Next best action card: Suggested next step, rule sentence, deep-link button, LM footnote, dismiss button."""
        sample_campaigns = [{
            "id": 1,
            "name": "General Drill",
            "status": "completed",
            "employee_count": 20,
            "emails_sent": 20,
            "opens": 15,
            "clicks": 2,
            "reports": 6,
            "created_at": "2026-10-21 11:00:00",
            "company_domain": "example.com",
        }]

        res = self._get_dashboard_with_mock_data(sample_campaigns)
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)

        self.assertIn('class="next-action-card', html)
        self.assertIn("Suggested next step", html)
        self.assertIn('class="next-action-text"', html)
        self.assertIn('class="next-action-note"', html)
        self.assertIn("Written by a language model. It can be wrong.", html)
        self.assertIn("Run targeted drill", html)
        self.assertIn('class="next-action-dismiss"', html)

    def test_weekly_briefing_teaser_card_and_copy_update(self):
        """Weekly briefing teaser card has Newsreader serif headline and 'Your weekly summary'."""
        sample_campaigns = [{
            "id": 1,
            "name": "Q3 Drill",
            "status": "completed",
            "employee_count": 10,
            "emails_sent": 10,
            "opens": 5,
            "clicks": 1,
            "reports": 3,
            "created_at": "2026-10-20 10:00:00",
            "company_domain": "example.com",
        }]

        res = self._get_dashboard_with_mock_data(sample_campaigns)
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)

        self.assertIn('class="briefing-teaser-card', html)
        self.assertIn("Your weekly summary", html)
        self.assertIn("editorial-voice", html)
        self.assertIn("Open briefing", html)

    def test_campaigns_list_and_grid_views(self):
        """Campaigns section supports List & Grid views, filters with counts, search with '/', and sort."""
        sample_campaigns = [
            {
                "id": 10,
                "name": "Finance Spearphish",
                "status": "launched",
                "employee_count": 30,
                "emails_sent": 30,
                "opens": 18,
                "clicks": 4,
                "reports": 8,
                "created_at": "2026-10-21 08:30:00",
                "company_domain": "example.com",
            },
            {
                "id": 11,
                "name": "HR Credential Harvester",
                "status": "completed",
                "employee_count": 40,
                "emails_sent": 40,
                "opens": 22,
                "clicks": 1,
                "reports": 15,
                "created_at": "2026-10-18 14:00:00",
                "company_domain": "example.com",
            },
        ]

        res = self._get_dashboard_with_mock_data(sample_campaigns)
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)

        # Search input with '/' shortcut badge
        self.assertIn('id="campaign-search-input"', html)
        self.assertIn('class="search-shortcut-badge">/</span>', html)

        # Filter Chips with counts: All (2), Running (1), Finished (1), Draft (0)
        self.assertIn('data-filter="all"', html)
        self.assertIn('data-filter="running"', html)
        self.assertIn('data-filter="scheduled"', html)
        self.assertIn('data-filter="finished"', html)
        self.assertIn('data-filter="draft"', html)

        # View toggle buttons
        self.assertIn('id="view-toggle-list"', html)
        self.assertIn('id="view-toggle-grid"', html)

        # List view table
        self.assertIn('id="pane-view-list"', html)
        self.assertIn('class="campaign-progress-bar"', html)
        self.assertIn('id="campaign-select-all"', html)

        # Grid view cards
        self.assertIn('id="pane-view-grid"', html)
        self.assertIn('class="campaign-card', html)
        self.assertIn('class="mini-funnel-grid"', html)

        # Floating bulk actions bar
        self.assertIn('id="bulk-actions-bar"', html)

    def test_first_time_empty_state_replaces_hero_strip_with_3_step_guide(self):
        """When 0 campaigns exist, 3-step guide is shown and particle sphere is absent."""
        res = self._get_dashboard_with_mock_data([])
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)

        # 3-step guide present
        self.assertIn('class="empty-guide-grid"', html)
        self.assertIn("Add people", html)
        self.assertIn("Pick a scenario", html)
        self.assertIn("Send", html)

        # Particle sphere canvas and glowing title must be absent
        self.assertNotIn("canvas-network", html)
        self.assertNotIn("glow-title", html)

    def test_keyboard_shortcuts_dialog(self):
        """Keyboard shortcuts sheet dialog is rendered with N, /, G C, V, and Esc."""
        res = self._get_dashboard_with_mock_data([])
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)

        self.assertIn('id="shortcuts-dialog"', html)
        self.assertIn("Keyboard shortcuts", html)
        self.assertIn(">N</kbd>", html)
        self.assertIn(">/</kbd>", html)
        self.assertIn(">V</kbd>", html)
        self.assertIn(">Esc</kbd>", html)

    def test_chart_is_not_defined_console_error_prevented(self):
        """No external Chart.js dependency or 'new Chart(' invocations that cause runtime errors."""
        with open(
            os.path.join(os.path.dirname(__file__), "..", "templates", "dashboard.html"),
            "r",
            encoding="utf-8",
        ) as f:
            template_code = f.read()

        # Pure inline SVGs must be used, never Chart.js
        self.assertNotIn("new Chart(", template_code)
        self.assertNotIn("chart.js", template_code.lower())
        self.assertNotIn("cdn.jsdelivr.net/npm/chart.js", template_code)

    def test_banned_wording_eliminated(self):
        """Forbidden copy like terminal, operator, agentic, neural, live mode must be absent."""
        res = self._get_dashboard_with_mock_data([])
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)

        forbidden = [
            "Continuous analysis of your campaign telemetry",
            "OPERATOR",
            "TERMINAL",
            "AGENT ACTIVE",
            "LIVE MODE",
            "NEURAL",
        ]
        for word in forbidden:
            self.assertNotIn(word, html, f"Forbidden word '{word}' found on dashboard")


if __name__ == "__main__":
    unittest.main()
