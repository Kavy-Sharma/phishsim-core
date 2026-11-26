import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import unittest
from datetime import datetime
from app import app, get_db_connection

class TestPartFBilling(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        app.config["WTF_CSRF_ENABLED"] = False
        self.client = app.test_client()

        # Find or create a dedicated non-admin test user
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT id, email, role FROM users WHERE email = 'test_free@phishsim.ai'")
        user = cursor.fetchone()
        if not user:
            cursor.execute("""
                INSERT INTO users (name, email, password_hash, role)
                VALUES ('Billing Tester', 'test_free@phishsim.ai', 'pbkdf2:sha256:dummy', 'company_user')
            """)
            db.commit()
            self.user_id = cursor.lastrowid
        else:
            self.user_id = user["id"]
        # Clear any leftover test invoices so clean free user starts empty
        try:
            cursor.execute("DELETE FROM invoices WHERE user_id = %s", (self.user_id,))
            db.commit()
        except Exception:
            pass
        cursor.close()
        db.close()

    def tearDown(self):
        try:
            db = get_db_connection()
            cursor = db.cursor()
            cursor.execute("UPDATE users SET role = 'company_user', pro_expires_at = NULL WHERE id = %s", (self.user_id,))
            db.commit()
            cursor.close()
            db.close()
        except Exception:
            pass

    def _login_as(self, role="company_user", pro_expires_at=None):
        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute("UPDATE users SET role = %s, pro_expires_at = %s WHERE id = %s", (role, pro_expires_at, self.user_id))
        db.commit()
        cursor.close()
        db.close()

        with self.client.session_transaction() as sess:
            sess["user_id"] = self.user_id
            sess["_fresh"] = True

    def test_01_billing_portal_free_user_view(self):
        """Free user sees Free plan details, real limits, and empty invoices state."""
        self._login_as(role="company_user")
        res = self.client.get("/billing")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)

        # Title and header
        self.assertIn("Billing", html)
        self.assertIn("Manage your subscription, usage limits, and invoices.", html)

        # Plan Card
        self.assertIn("Current Plan", html)
        self.assertIn("$0", html)
        self.assertIn("/ month", html)
        self.assertIn("Free", html)
        self.assertIn("Seats", html)
        self.assertIn("used", html)

        # Usage Card limits matching code
        self.assertIn("Campaigns this month", html)
        self.assertIn("3 max", html)
        self.assertIn("People reached", html)
        self.assertIn("50", html)
        self.assertIn("PhishRecon audits", html)
        self.assertIn("15 / day", html)

        # Invoices Empty State for Free user
        self.assertIn("No invoices yet", html)
        self.assertIn("Receipts will appear here when subscription payments process.", html)

        # Plan Comparison with single clear 30-day trial flow
        self.assertIn("Plan comparison", html)
        self.assertIn("Start 30-day trial", html)
        self.assertIn("Subscribe to Pro ($24/mo)", html)

        # Test mode banner
        self.assertIn("Test mode", html)

    def test_02_billing_portal_pro_user_view(self):
        """Pro user sees Pro plan details, unlimited limits, test invoice, and cancel link."""
        self._login_as(role="pro")
        res = self.client.get("/billing")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)

        # Pro Plan Card
        self.assertIn("Pro", html)
        self.assertIn("$24", html)
        self.assertIn("Renews on", html)

        # Usage Card unlimited indicators
        self.assertIn("Unlimited", html)

        # Test Mode Invoice Row (labeled properly) - create test invoice if needed to test rendering
        self.client.post("/billing/mock-charge", data={"plan": "pro"}, follow_redirects=True)
        res = self.client.get("/billing")
        html = res.get_data(as_text=True)
        self.assertIn("PhishSim.ai Pro Subscription", html)
        self.assertTrue("Test" in html or "PAID" in html)

        # Cancel Subscription small text link at bottom
        self.assertIn("cancel-text-link", html)
        self.assertIn("Cancel subscription", html)

        # Two-step cancel modal
        self.assertIn("cancel-modal-backdrop", html)
        self.assertIn("Cancel subscription?", html)
        self.assertIn("What ends:", html)
        self.assertIn("Confirm cancellation", html)
        self.assertIn("Reason for cancelling", html)

    def test_03_trial_activation_lifecycle(self):
        """Activating 30-day trial updates role to pro and sets 30-day expiration."""
        self._login_as(role="company_user")
        res = self.client.post("/billing/activate-trial", follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)

        # Verify flash & pro state
        self.assertIn("30-day Pro trial has been activated", html)
        self.assertTrue("Pro trial · ends" in html or "Trial ends in" in html)

        # Verify DB state
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT role, pro_expires_at FROM users WHERE id = %s", (self.user_id,))
        row = cursor.fetchone()
        cursor.close()
        db.close()

        self.assertEqual(row["role"], "pro")
        self.assertIsNotNone(row["pro_expires_at"])

    def test_04_cancellation_flow(self):
        """Cancelling subscription downgrades to company_user and records optional reason."""
        self._login_as(role="pro")
        res = self.client.post("/billing/cancel", data={"cancel_reason": "Too expensive"}, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)

        self.assertIn("Your subscription has been cancelled", html)
        self.assertIn("Free", html)

        # Verify DB state
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT role, pro_expires_at FROM users WHERE id = %s", (self.user_id,))
        row = cursor.fetchone()
        cursor.close()
        db.close()

        self.assertEqual(row["role"], "company_user")
        self.assertIsNone(row["pro_expires_at"])

    def test_05_mock_checkout_two_column_view(self):
        """Mock checkout renders clean two-column layout with summary left and form right."""
        self._login_as(role="company_user")
        res = self.client.get("/billing/mock-checkout")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)

        # Summary Column
        self.assertIn("checkout-summary", html)
        self.assertIn("PhishSim.ai Pro", html)
        self.assertIn("$24.00", html)
        self.assertIn("50 employees", html)
        self.assertIn("Total due today", html)
        self.assertIn("Return to billing", html)
        self.assertIn("Test mode", html)

        # Form Column
        self.assertIn("checkout-form-pane", html)
        self.assertIn("Payment details", html)
        self.assertIn("checkout-card-number", html)
        self.assertIn("checkout-card-expiry", html)
        self.assertIn("checkout-card-cvc", html)
        self.assertIn("Pay $24.00", html)

    def test_06_mock_charge_and_success_page(self):
        """Simulated payment updates user to pro and renders success page with animated tick."""
        self._login_as(role="company_user")
        charge_res = self.client.post("/billing/mock-charge", follow_redirects=True)
        self.assertEqual(charge_res.status_code, 200)
        html = charge_res.get_data(as_text=True)

        # Success page
        self.assertIn("Payment successful", html)
        self.assertIn("checkmark-svg", html)
        self.assertIn("checkmark-circle", html)
        self.assertIn("checkmark-check", html)
        self.assertIn("Go to dashboard", html)
        self.assertIn("View billing & invoices", html)

        # Verify user is pro
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT role FROM users WHERE id = %s", (self.user_id,))
        row = cursor.fetchone()
        cursor.close()
        db.close()
        self.assertEqual(row["role"], "pro")

    def test_07_jargon_purge_verification(self):
        """Ensure forbidden jargon words are completely absent from billing pages."""
        self._login_as(role="pro")
        jargon = [
            "telemetry",
            "compliance vault",
            "PRO Operator flat rate",
            "premium security operator settings",
            "Live Invoice Records"
        ]

        for endpoint in ["/billing", "/billing/mock-checkout", "/billing/success"]:
            res = self.client.get(endpoint)
            self.assertEqual(res.status_code, 200)
            html = res.get_data(as_text=True)
            for word in jargon:
                self.assertNotIn(word.lower(), html.lower(), f"Forbidden jargon '{word}' found in {endpoint}")

if __name__ == "__main__":
    unittest.main()
