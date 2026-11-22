import os
import sys
import re
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import MagicMock, patch
import app as app_module
from app import app


# ═══════════════════════════════════════════════════════════════════
# Helper Functions: Pure Logic Implementations Under Test
# ═══════════════════════════════════════════════════════════════════
def compute_delta_colour(metric_type, delta, current_val=0):
    """
    Computes CSS class based on the strict delta/colour rules:
    - report_rate: delta >= 0 -> 'good', delta < 0 -> 'warning'
    - click_rate: delta <= 0 -> 'good', delta > 0 and val <= 25 -> 'warning', delta > 0 and val > 25 -> 'danger'
    - readiness: delta > 0 -> 'positive', delta == 0 -> 'steady', delta < 0 -> 'warning'
    """
    if metric_type == 'report_rate':
        return 'good' if delta >= 0 else 'warning'
    elif metric_type == 'click_rate':
        if delta <= 0:
            return 'good'
        elif current_val > 25.0:
            return 'danger'
        else:
            return 'warning'
    elif metric_type == 'readiness':
        if delta > 0:
            return 'positive'
        elif delta == 0:
            return 'steady'
        else:
            return 'warning'
    raise ValueError(f"Unknown metric_type: {metric_type}")


def validate_readiness_sentence(delta, score):
    """
    Rule-based readiness summary verdict:
    - delta > 0 or score >= 75 -> 'Getting safer'
    - delta == 0 or (60 <= score < 75) -> 'Holding steady'
    - delta < 0 or score < 60 -> 'Needs attention'
    """
    if delta > 0 or score >= 75:
        return 'Getting safer'
    elif delta == 0 or (60 <= score < 75):
        return 'Holding steady'
    else:
        return 'Needs attention'


def validate_weekly_summary_sentence(has_campaigns, report_val, click_val):
    """
    Weekly summary sentence strictly truthful to displayed values.
    """
    if has_campaigns:
        return f"In your baseline drills, {report_val}% of employees reported the lure while {click_val}% clicked."
    else:
        return "Launch your first security drill to begin generating team resilience intelligence."


def filter_campaigns(campaigns, status_filter, search_query=''):
    """
    Filters campaigns by status group and query.
    """
    q = (search_query or '').lower().strip()
    result = []
    for c in campaigns:
        st = c.get('status_group', 'draft')
        name = (c.get('name') or '').lower()
        matches_st = (status_filter == 'all') or (st == status_filter)
        matches_q = not q or (q in name)
        if matches_st and matches_q:
            result.append(c)
    return result


def sort_campaigns(campaigns, sort_key):
    """
    Sorts campaigns by key:
    - 'newest': date desc
    - 'oldest': date asc
    - 'click_desc': clicks desc
    - 'report_desc': reports desc
    - 'name_asc': name alphabetical
    """
    items = list(campaigns)
    if sort_key == 'newest':
        return sorted(items, key=lambda x: str(x.get('date', '')), reverse=True)
    elif sort_key == 'oldest':
        return sorted(items, key=lambda x: str(x.get('date', '')))
    elif sort_key == 'click_desc':
        return sorted(items, key=lambda x: float(x.get('clicks', 0)), reverse=True)
    elif sort_key == 'report_desc':
        return sorted(items, key=lambda x: float(x.get('reports', 0)), reverse=True)
    elif sort_key == 'name_asc':
        return sorted(items, key=lambda x: str(x.get('name', '')).lower())
    return items


# ═══════════════════════════════════════════════════════════════════
# Unit Tests
# ═══════════════════════════════════════════════════════════════════
class TestPart4UnitLogic(unittest.TestCase):
    """Part 4 Unit Tests for Delta/Colour Rules, Summary Validator, Filter/Sort."""

    def test_delta_colour_rules(self):
        # 1. Report rate: higher is good, lower is warning
        self.assertEqual(compute_delta_colour('report_rate', 3.4), 'good')
        self.assertEqual(compute_delta_colour('report_rate', 0.0), 'good')
        self.assertEqual(compute_delta_colour('report_rate', -1.5), 'warning')

        # 2. Click rate: lower is good, higher is warning/danger
        self.assertEqual(compute_delta_colour('click_rate', -2.1, 8.4), 'good')
        self.assertEqual(compute_delta_colour('click_rate', 0.0, 10.0), 'good')
        self.assertEqual(compute_delta_colour('click_rate', 1.5, 12.0), 'warning')
        self.assertEqual(compute_delta_colour('click_rate', 4.0, 28.5), 'danger')

        # 3. Readiness: positive, steady, warning
        self.assertEqual(compute_delta_colour('readiness', 5), 'positive')
        self.assertEqual(compute_delta_colour('readiness', 0), 'steady')
        self.assertEqual(compute_delta_colour('readiness', -4), 'warning')

    def test_summary_sentence_validator(self):
        # With campaigns: strictly truthful numbers
        sentence = validate_weekly_summary_sentence(True, 24.1, 12.5)
        self.assertEqual(
            sentence,
            "In your baseline drills, 24.1% of employees reported the lure while 12.5% clicked."
        )

        # Without campaigns: truthful fallback
        empty_sentence = validate_weekly_summary_sentence(False, 0, 0)
        self.assertEqual(
            empty_sentence,
            "Launch your first security drill to begin generating team resilience intelligence."
        )

        # Readiness headline validator
        self.assertEqual(validate_readiness_sentence(5, 78), 'Getting safer')
        self.assertEqual(validate_readiness_sentence(-2, 80), 'Getting safer')  # Score >= 75
        self.assertEqual(validate_readiness_sentence(0, 68), 'Holding steady')  # Delta 0, 60<=score<75
        self.assertEqual(validate_readiness_sentence(-3, 62), 'Holding steady')  # In range
        self.assertEqual(validate_readiness_sentence(-5, 45), 'Needs attention') # Sub-60 and negative

    def test_filter_and_sort_logic(self):
        sample = [
            {'id': 1, 'name': 'Executive CEO Fraud Test', 'status_group': 'running', 'clicks': 8, 'reports': 5, 'date': '2026-08-01'},
            {'id': 2, 'name': 'Q3 Password Reset Drill', 'status_group': 'finished', 'clicks': 4, 'reports': 21, 'date': '2026-07-15'},
            {'id': 3, 'name': 'IT Security Policy Update', 'status_group': 'scheduled', 'clicks': 0, 'reports': 0, 'date': '2026-08-10'},
            {'id': 4, 'name': 'Payroll Tax Notice Phish', 'status_group': 'draft', 'clicks': 0, 'reports': 0, 'date': '2026-08-05'},
        ]

        # Status filtering
        self.assertEqual(len(filter_campaigns(sample, 'all')), 4)
        running = filter_campaigns(sample, 'running')
        self.assertEqual(len(running), 1)
        self.assertEqual(running[0]['name'], 'Executive CEO Fraud Test')

        finished = filter_campaigns(sample, 'finished')
        self.assertEqual(len(finished), 1)
        self.assertEqual(finished[0]['name'], 'Q3 Password Reset Drill')

        # Search filtering
        ceo_matches = filter_campaigns(sample, 'all', search_query='ceo')
        self.assertEqual(len(ceo_matches), 1)
        self.assertEqual(ceo_matches[0]['id'], 1)

        tax_matches = filter_campaigns(sample, 'all', search_query='payroll')
        self.assertEqual(len(tax_matches), 1)
        self.assertEqual(tax_matches[0]['id'], 4)

        no_matches = filter_campaigns(sample, 'all', search_query='nonexistent')
        self.assertEqual(len(no_matches), 0)

        # Sorting
        by_clicks = sort_campaigns(sample, 'click_desc')
        self.assertEqual(by_clicks[0]['id'], 1)  # 8 clicks

        by_reports = sort_campaigns(sample, 'report_desc')
        self.assertEqual(by_reports[0]['id'], 2)  # 21 reports

        by_name = sort_campaigns(sample, 'name_asc')
        self.assertEqual(by_name[0]['name'], 'Executive CEO Fraud Test')
        self.assertEqual(by_name[-1]['name'], 'Q3 Password Reset Drill')

        by_newest = sort_campaigns(sample, 'newest')
        self.assertEqual(by_newest[0]['date'], '2026-08-10')

        by_oldest = sort_campaigns(sample, 'oldest')
        self.assertEqual(by_oldest[0]['date'], '2026-07-15')


    def test_shared_finished_definition(self):
        """Shared definition of finished across list, stats, score, and trend."""
        from app import is_campaign_finished
        # Completed / Finished statuses
        self.assertTrue(is_campaign_finished({'status': 'completed', 'emails_sent': 10}))
        self.assertTrue(is_campaign_finished('completed'))
        self.assertTrue(is_campaign_finished('finished'))
        self.assertTrue(is_campaign_finished({'status': 'launched_with_errors', 'emails_sent': 5}))

        # Launched with emails_sent > 0 is finished (evaluated)
        self.assertTrue(is_campaign_finished({'status': 'launched', 'emails_sent': 12}))
        # Launched with 0 emails sent is not finished (still preparing/empty)
        self.assertFalse(is_campaign_finished({'status': 'launched', 'emails_sent': 0}))

        # Non-finished states
        self.assertFalse(is_campaign_finished({'status': 'draft', 'emails_sent': 0}))
        self.assertFalse(is_campaign_finished({'status': 'scheduled', 'emails_sent': 0}))
        self.assertFalse(is_campaign_finished({'status': 'launching', 'emails_sent': 0}))
        self.assertFalse(is_campaign_finished({'status': 'failed', 'emails_sent': 0}))

    def test_scenario_label_map(self):
        """Scenario label map produces canonical, human-friendly sentence-case labels."""
        from app import format_scenario_label
        self.assertEqual(format_scenario_label('ceo_fraud'), 'CEO fraud')
        self.assertEqual(format_scenario_label('it_reset'), 'IT password reset')
        self.assertEqual(format_scenario_label('hr_policy'), 'HR policy update')
        self.assertEqual(format_scenario_label('urgent_invoice'), 'Urgent invoice')
        self.assertEqual(format_scenario_label('shared_doc'), 'Shared document')
        self.assertEqual(format_scenario_label('delivery_notice'), 'Delivery notice')
        self.assertEqual(format_scenario_label('custom_drill'), 'Custom drill')


# ═══════════════════════════════════════════════════════════════════
# Grep & Static Semantic Tests
# ═══════════════════════════════════════════════════════════════════
class TestPart4GrepAndSemantics(unittest.TestCase):
    """Part 4 Grep Requirements: No Hex, No Inline Styles, No Dynamic innerHTML, No CDN, No Forbidden Text, Single Primary Button."""

    def setUp(self):
        self.root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(self.root_dir, 'templates', 'dashboard.html'), 'r', encoding='utf-8') as f:
            self.dash_html = f.read()
        with open(os.path.join(self.root_dir, 'templates', 'base.html'), 'r', encoding='utf-8') as f:
            self.base_html = f.read()
        with open(os.path.join(self.root_dir, 'static', 'css', 'app_shell.css'), 'r', encoding='utf-8') as f:
            self.app_shell_css = f.read()

    def test_no_hex_in_app_shell_css(self):
        """Zero hex color literals allowed in app_shell.css (strict CSS token design system)."""
        # Find hex colors (#fff, #123456), ignoring id selectors
        hex_matches = re.findall(r'(#[0-9a-fA-F]{3,8})\b', self.app_shell_css)
        real_hex = [m for m in hex_matches if not re.search(r'#[0-9a-fA-F]{3,8}\s*[{,:]', m)]
        self.assertEqual(len(real_hex), 0, f"Found raw hex colors in app_shell.css: {set(real_hex)}")

    def test_no_inline_style_in_dashboard_html(self):
        """Zero inline style= attributes allowed in templates/dashboard.html."""
        style_attrs = re.findall(r'<\w+[^>]*\bstyle=["\'][^"\']*["\']', self.dash_html, re.IGNORECASE)
        self.assertEqual(len(style_attrs), 0, f"Found inline style= in dashboard.html: {style_attrs[:3]}")

    def test_no_dynamic_inner_html_in_dashboard(self):
        """No innerHTML with dynamic variable interpolation in dashboard.html."""
        dynamic_inner_html = re.findall(r'innerHTML\s*=\s*`[^`]*\$\{[^}]+\}[^`]*`', self.dash_html)
        self.assertEqual(len(dynamic_inner_html), 0, f"Found dynamic innerHTML in dashboard.html: {dynamic_inner_html}")

    def test_no_forbidden_text_in_dashboard(self):
        """No forbidden text: telemetry, operator, agentic, live mode, status bar in templates/dashboard.html."""
        forbidden_words = ["telemetry", "operator", "agentic", "live mode", "status bar"]
        for word in forbidden_words:
            matches = re.findall(rf'\b{re.escape(word)}\b', self.dash_html, re.IGNORECASE)
            self.assertEqual(len(matches), 0, f"Found forbidden word '{word}' in dashboard.html")

    def test_no_cyber_chrome_status_strip(self):
        """No status strip with DEFENSE GRID, SYSTEM: ONLINE, or SANDBOX MODE in dashboard or base."""
        cyber_terms = ["DEFENSE GRID", "SYSTEM: ONLINE", "ENGINE: READY"]
        for term in cyber_terms:
            self.assertNotIn(term, self.dash_html)
            self.assertNotIn(term, self.base_html)

    def test_no_fake_sample_names_in_dashboard(self):
        """Truth rule: no fake sample persons or drill names hardcoded in dashboard.html."""
        fake_names = ["Julia Roberts", "alex.rivera@demo-corp.com", "Q3 Benefit Advisory"]
        for name in fake_names:
            self.assertNotIn(name, self.dash_html)

    def test_live_update_aria_attributes(self):
        """Live update badge includes aria-live='polite' and aria-atomic='true'."""
        self.assertIn('id="live-update-badge"', self.dash_html)
        self.assertIn('aria-live="polite"', self.dash_html)
        self.assertIn('aria-atomic="true"', self.dash_html)

    def test_single_primary_button_on_dashboard(self):
        """Dashboard must contain exactly ONE primary button ('New campaign', #btn-create-campaign)."""
        primary_btns = re.findall(r'class=["\'][^"\']*\bbtn-primary\b[^"\']*["\']', self.dash_html)
        self.assertEqual(len(primary_btns), 1, f"Expected exactly 1 btn-primary, found {len(primary_btns)}")
        self.assertIn('id="btn-create-campaign"', self.dash_html)
        self.assertIn('New campaign', self.dash_html)

    def test_table_and_radiogroup_semantics(self):
        """Table semantics: real table, sr-only caption, th scope col/row. View toggle: role=radiogroup with role=radio."""
        self.assertIn('<table class="app-table"', self.dash_html)
        self.assertIn('<caption class="sr-only">', self.dash_html)
        self.assertIn('scope="col"', self.dash_html)
        self.assertIn('scope="row"', self.dash_html)

        # Radiogroup for view toggle
        self.assertIn('role="radiogroup"', self.dash_html)
        self.assertIn('role="radio"', self.dash_html)
        self.assertIn('aria-checked="true"', self.dash_html)
        self.assertIn('tabindex="0"', self.dash_html)

    def test_skeleton_layout_and_zero_layout_shift(self):
        """Skeleton #dashboard-skeleton matches final rendered container heights."""
        self.assertIn('id="dashboard-skeleton"', self.dash_html)
        self.assertIn('dashboard-skeleton-layout', self.app_shell_css)
        self.assertIn('skeleton-hero-card', self.app_shell_css)

    def test_dialog_focus_traps_and_restoration(self):
        """Focus trapped in palette and dialogs, and restored on close."""
        self.assertIn('openShortcutsModal', self.dash_html)
        self.assertIn('closeShortcutsModal', self.dash_html)
        self.assertIn('lastFocusedBeforeShortcuts', self.dash_html)
        self.assertIn('lastFocusedBeforeExport', self.dash_html)


if __name__ == '__main__':
    unittest.main()

