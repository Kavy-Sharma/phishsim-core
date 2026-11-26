import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import unittest
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from app import app, get_db_connection

class TestPartGAdmin(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config["TESTING"] = True
        app.config["WTF_CSRF_ENABLED"] = False

        db = get_db_connection()
        cursor = db.cursor(dictionary=True)

        # 1. Ensure primary admin
        cursor.execute("SELECT id FROM users WHERE email = 'admin_primary@phishsim.ai'")
        admin = cursor.fetchone()
        if not admin:
            cursor.execute("""
                INSERT INTO users (name, email, password_hash, role, email_verified, is_disabled)
                VALUES ('Primary Admin', 'admin_primary@phishsim.ai', %s, 'admin', TRUE, FALSE)
            """, (generate_password_hash("AdminPass123!"),))
            db.commit()
            cls.admin_id = cursor.lastrowid
        else:
            cls.admin_id = admin["id"]
            cursor.execute("UPDATE users SET role = 'admin', is_disabled = FALSE WHERE id = %s", (cls.admin_id,))
            db.commit()

        # 2. Ensure secondary admin (to test last-admin logic)
        cursor.execute("SELECT id FROM users WHERE email = 'admin_secondary@phishsim.ai'")
        sec_admin = cursor.fetchone()
        if not sec_admin:
            cursor.execute("""
                INSERT INTO users (name, email, password_hash, role, email_verified, is_disabled)
                VALUES ('Secondary Admin', 'admin_secondary@phishsim.ai', %s, 'admin', TRUE, FALSE)
            """, (generate_password_hash("AdminPass123!"),))
            db.commit()
            cls.sec_admin_id = cursor.lastrowid
        else:
            cls.sec_admin_id = sec_admin["id"]
            cursor.execute("UPDATE users SET role = 'admin', is_disabled = FALSE WHERE id = %s", (cls.sec_admin_id,))
            db.commit()

        # 3. Ensure standard non-admin user
        cursor.execute("SELECT id FROM users WHERE email = 'standard_user@phishsim.ai'")
        std = cursor.fetchone()
        if not std:
            cursor.execute("""
                INSERT INTO users (name, email, password_hash, role, email_verified, is_disabled)
                VALUES ('Standard User', 'standard_user@phishsim.ai', %s, 'company_user', TRUE, FALSE)
            """, (generate_password_hash("UserPass123!"),))
            db.commit()
            cls.standard_user_id = cursor.lastrowid
        else:
            cls.standard_user_id = std["id"]
            cursor.execute("UPDATE users SET role = 'company_user', is_disabled = FALSE WHERE id = %s", (cls.standard_user_id,))
            db.commit()

        # 4. Ensure a disposable target user for actions (role/plan/delete/disable)
        cursor.execute("SELECT id FROM users WHERE email = 'target_employee@phishsim.ai'")
        tgt = cursor.fetchone()
        if not tgt:
            cursor.execute("""
                INSERT INTO users (name, email, password_hash, role, email_verified, is_disabled)
                VALUES ('Target Employee', 'target_employee@phishsim.ai', %s, 'company_user', FALSE, FALSE)
            """, (generate_password_hash("TempPass123!"),))
            db.commit()
            cls.target_user_id = cursor.lastrowid
        else:
            cls.target_user_id = tgt["id"]

        cursor.close()
        db.close()

    def setUp(self):
        self.client = app.test_client()

    def _login(self, user_id):
        with self.client.session_transaction() as sess:
            sess["user_id"] = user_id
            sess["_fresh"] = True

    # =========================================================================
    # 1. SECURITY & ACCESS CONTROL: Non-Admin Gets 403 on ALL Admin Routes
    # =========================================================================
    def test_01_unauthenticated_access_redirects_to_login(self):
        """Unauthenticated requests to admin routes must redirect to /login."""
        routes = ["/admin", "/users"]
        for r in routes:
            res = self.client.get(r)
            self.assertEqual(res.status_code, 302, f"Failed on {r}")
            self.assertIn("/login", res.headers.get("Location", ""))

    def test_02_non_admin_gets_403_on_all_admin_routes(self):
        """Logged-in non-admin user must receive HTTP 403 on all admin routes and actions."""
        self._login(self.standard_user_id)

        # GET routes
        get_routes = [
            "/admin",
            "/users",
            f"/api/admin/user/{self.target_user_id}/details"
        ]
        for r in get_routes:
            res = self.client.get(r)
            self.assertEqual(res.status_code, 403, f"Expected 403 on GET {r}, got {res.status_code}")

        # POST routes
        post_routes = [
            ("/admin/save-settings", {"enforce_work_emails": "true"}),
            ("/users", {"name": "Hacker", "email": "hacker@evil.com"}),
            (f"/set-user-role/{self.target_user_id}", {"role": "admin"}),
            (f"/set-user-plan/{self.target_user_id}", {"plan": "pro"}),
            (f"/verify-user/{self.target_user_id}", {}),
            (f"/reset-user-password/{self.target_user_id}", {"new_password": "pwned"}),
            (f"/toggle-user-status/{self.target_user_id}", {}),
            (f"/delete-user/{self.target_user_id}", {}),
        ]
        for r, data in post_routes:
            res = self.client.post(r, data=data)
            self.assertEqual(res.status_code, 403, f"Expected 403 on POST {r}, got {res.status_code}")

    # =========================================================================
    # 2. ADMIN OVERVIEW (/admin) — Real Data, Health Checks, Settings
    # =========================================================================
    def test_03_admin_overview_renders_dense_real_data(self):
        """Admin overview page renders stat tiles, system health, recent activity, and settings."""
        self._login(self.admin_id)
        res = self.client.get("/admin")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)

        # Header and nav
        self.assertIn("Admin Overview", html)
        self.assertIn("Manage Users", html)
        self.assertIn("/users", html)

        # Stat tiles with real labels
        self.assertIn("Total Users", html)
        self.assertIn("Verified Users", html)
        self.assertIn("Campaigns", html)
        self.assertIn("Sends This Week", html)
        self.assertIn("Failed Sends", html)

        # System Health Card
        self.assertIn("System Health", html)
        self.assertIn("Database", html)
        self.assertIn("SMTP", html)
        self.assertIn("AI", html)
        self.assertIn("Scheduler", html)

        # Needs Attention & Recent Activity
        self.assertIn("Needs Attention", html)
        self.assertIn("Recent Activity", html)

        # Settings tab & Mailtrap help text (not warning)
        self.assertIn("Work Email Enforcement", html)
        self.assertIn("Active Mail Provider", html)
        self.assertIn("Mailtrap", html)
        # Ensure no blank screen empty cards
        self.assertNotIn("screen of blank space", html)

    def test_04_admin_save_settings_endpoint(self):
        """Admin can update work-email enforcement setting with audit event logging."""
        self._login(self.admin_id)

        # Save enforce_work_emails = true via JSON
        res = self.client.post("/admin/save-settings", json={"enforce_work_emails": "true"})
        self.assertEqual(res.status_code, 200)
        json_data = res.get_json()
        self.assertTrue(json_data["success"])
        self.assertEqual(json_data["enforce_work_emails"], "true")

        # Verify audit event written
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        cursor.execute("""
            SELECT event_type FROM audit_events
            WHERE user_id = %s AND event_type LIKE '%enforce_work_emails=true%'
            ORDER BY id DESC LIMIT 1
        """, (self.admin_id,))
        audit = cursor.fetchone()
        cursor.close()
        db.close()
        self.assertIsNotNone(audit)

    # =========================================================================
    # 3. USERS PAGE (/users) — Table, Drawers, Action Buttons Never Empty
    # =========================================================================
    def test_05_users_page_renders_table_and_action_buttons_with_text(self):
        """Users page renders table, avatars, badges, and all action buttons have visible text spans."""
        self._login(self.admin_id)
        res = self.client.get("/users")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)

        # Title & drawer trigger
        self.assertIn("Users", html)
        self.assertIn("Add user", html)

        # Search, filter, pagination
        self.assertIn("user-search-input", html)
        self.assertIn("role-filter", html)
        self.assertIn("plan-filter", html)
        self.assertIn("status-filter", html)
        self.assertIn("sort-select", html)
        self.assertIn("Showing", html)

        # Ensure action buttons have visible text spans (NEVER empty boxes!)
        self.assertIn("<span>Details</span>", html)
        self.assertTrue("<span>Reset Password</span>" in html or "<span>Reset PW</span>" in html)
        self.assertTrue("<span>Delete User</span>" in html or "<span>Delete</span>" in html)

        # Ensure drawers and modals exist
        self.assertIn("add-user-drawer", html)
        self.assertIn("user-detail-drawer", html)
        self.assertIn("reset-password-modal", html)
        self.assertIn("confirm-action-modal", html)

    # =========================================================================
    # 4. USER MANAGEMENT CRUD & AUDITING
    # =========================================================================
    def test_06_create_user_with_temp_password_and_audit(self):
        """Creating user generates temporary password, creates record, and logs audit event."""
        self._login(self.admin_id)
        test_email = "new_emp_admin_test@cyberdyne.corp"

        # Cleanup in case already exists
        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute("DELETE FROM users WHERE email = %s", (test_email,))
        db.commit()
        cursor.close()
        db.close()

        res = self.client.post("/users", json={
            "name": "Sarah Connor",
            "email": test_email,
            "role": "company_user",
            "company_domain": "cyberdyne.corp"
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertTrue(data.get("generated_temp_pass"))
        self.assertTrue(data.get("temp_password"))
        new_id = data["user_id"]

        # Verify record in DB
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT id, name, email, email_verified, is_disabled FROM users WHERE id = %s", (new_id,))
        created = cursor.fetchone()
        cursor.close()
        db.close()

        self.assertIsNotNone(created)
        self.assertEqual(created["name"], "Sarah Connor")
        self.assertTrue(created["email_verified"])
        self.assertFalse(created["is_disabled"])

    def test_07_set_user_role_and_plan(self):
        """Admin can change user role and plan; changes are saved and audited."""
        self._login(self.admin_id)

        # 1. Promote target to admin
        res = self.client.post(f"/set-user-role/{self.target_user_id}", json={"role": "admin"})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["role"], "admin")

        # 2. Switch target plan to Pro
        res = self.client.post(f"/set-user-plan/{self.target_user_id}", json={"plan": "pro"})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["plan"], "Pro")

        # 3. Switch back to company_user and Free
        res = self.client.post(f"/set-user-role/{self.target_user_id}", json={"role": "company_user"})
        self.assertEqual(res.status_code, 200)
        res = self.client.post(f"/set-user-plan/{self.target_user_id}", json={"plan": "free"})
        self.assertEqual(res.status_code, 200)

    def test_08_verify_and_reset_password(self):
        """Admin can verify email and reset password for a user."""
        self._login(self.admin_id)

        # Verify user
        res = self.client.post(f"/verify-user/{self.target_user_id}", json={})
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.get_json()["success"])

        # Reset password
        res = self.client.post(f"/reset-user-password/{self.target_user_id}", json={"new_password": "NewSecretPass2026!"})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["temp_password"], "NewSecretPass2026!")

        # Verify password hash updated in DB
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT password_hash FROM users WHERE id = %s", (self.target_user_id,))
        u = cursor.fetchone()
        cursor.close()
        db.close()
        self.assertTrue(check_password_hash(u["password_hash"], "NewSecretPass2026!"))

    # =========================================================================
    # 5. SAFETY & SELF-PROTECTION: Admin Cannot Demote, Disable, or Delete Self
    # =========================================================================
    def test_09_admin_self_protection(self):
        """Admin cannot demote, disable, or delete their own admin account."""
        self._login(self.admin_id)

        # 1. Demote self
        res = self.client.post(f"/set-user-role/{self.admin_id}", json={"role": "company_user"})
        self.assertEqual(res.status_code, 400)
        self.assertIn("cannot remove your own admin access", res.get_json().get("error", "").lower())

        # 2. Disable self
        res = self.client.post(f"/toggle-user-status/{self.admin_id}", json={})
        self.assertEqual(res.status_code, 400)
        self.assertIn("cannot disable your own admin account", res.get_json().get("error", "").lower())

        # 3. Delete self
        res = self.client.post(f"/delete-user/{self.admin_id}", json={})
        self.assertEqual(res.status_code, 400)
        self.assertIn("cannot delete your own account", res.get_json().get("error", "").lower())

    def test_10_last_admin_protection(self):
        """Platform prevents demoting or deleting the last remaining admin."""
        # Demote secondary admin first so primary is the sole admin
        self._login(self.admin_id)
        res = self.client.post(f"/set-user-role/{self.sec_admin_id}", json={"role": "company_user"})
        self.assertEqual(res.status_code, 200)

        # Attempt to delete or demote the sole admin (primary)
        # Even from an API call, it must be rejected with 400
        res = self.client.post(f"/delete-user/{self.admin_id}", json={})
        self.assertEqual(res.status_code, 400)

        # Restore secondary admin
        self.client.post(f"/set-user-role/{self.sec_admin_id}", json={"role": "admin"})

    # =========================================================================
    # 6. ACCOUNT STATUS & DISABLED LOGIN GATE
    # =========================================================================
    def test_11_disabled_account_cannot_login(self):
        """A disabled user cannot sign in; login route rejects disabled accounts."""
        self._login(self.admin_id)

        # Disable target user
        res = self.client.post(f"/toggle-user-status/{self.target_user_id}", json={})
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.get_json()["is_disabled"])

        # Reset target password to known string
        self.client.post(f"/reset-user-password/{self.target_user_id}", json={"new_password": "DisabledUserPass123!"})

        # Clear session
        with self.client.session_transaction() as sess:
            sess.clear()

        # Attempt login
        login_res = self.client.post("/login", data={
            "email": "target_employee@phishsim.ai",
            "password": "DisabledUserPass123!"
        }, follow_redirects=True)

        html = login_res.get_data(as_text=True)
        self.assertIn("disabled", html.lower())

        # Restore target user status
        self._login(self.admin_id)
        self.client.post(f"/toggle-user-status/{self.target_user_id}", json={})

    # =========================================================================
    # 7. USER DETAIL API ENDPOINT FOR DRAWER
    # =========================================================================
    def test_12_user_detail_api_drawer_data(self):
        """User detail endpoint returns profile, plan, campaigns, and audit trail without raw passwords."""
        self._login(self.admin_id)
        res = self.client.get(f"/api/admin/user/{self.target_user_id}/details")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()

        self.assertEqual(data["id"], self.target_user_id)
        self.assertIn("name", data)
        self.assertIn("email", data)
        self.assertIn("plan", data)
        self.assertIn("campaigns", data)
        self.assertIn("audit_trail", data)

        # Ensure no password hashes or credentials leaked!
        self.assertNotIn("password_hash", data)
        self.assertNotIn("password", data)
        self.assertNotIn("verification_token", data)

if __name__ == "__main__":
    unittest.main()
