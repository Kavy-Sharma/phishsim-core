import json
import io
import zipfile
import pytest
from werkzeug.security import generate_password_hash, check_password_hash
from app import app, get_db_connection


@pytest.fixture
def client():
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    with app.test_client() as c:
        yield c


def login_test_user(client, email="admin@phishsim.ai", role="admin"):
    """Helper to inject an authenticated session for testing."""
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT id, name, email, role, password_hash FROM users WHERE email = %s", (email,))
    user = cursor.fetchone()
    if not user:
        cursor.execute(
            "INSERT INTO users (name, email, password_hash, role, email_verified) VALUES (%s, %s, %s, %s, TRUE)",
            ("Test Operator", email, generate_password_hash("testpass123"), role)
        )
        db.commit()
        cursor.execute("SELECT id, name, email, role, password_hash FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
    cursor.close()
    db.close()

    with client.session_transaction() as sess:
        sess["user_id"] = user["id"]
        sess["user_email"] = user["email"]
        sess["user_role"] = user["role"]
    return user


def test_profile_renders_tabs_neutral_avatar_and_mono_account_id(client):
    user = login_test_user(client)
    res = client.get("/profile")
    assert res.status_code == 200
    html = res.get_data(as_text=True)

    # 1. Five discrete tabs present
    assert 'id="tab-profile"' in html
    assert 'id="tab-security"' in html
    assert 'id="tab-notifications"' in html
    assert 'id="tab-preferences"' in html
    assert 'id="tab-privacy"' in html

    # 2. Panels present
    assert 'id="section-profile"' in html
    assert 'id="section-security"' in html
    assert 'id="section-notifications"' in html
    assert 'id="section-preferences"' in html
    assert 'id="section-privacy"' in html

    # 3. Neutral avatar (no yellow orb / no pro-avatar glowing orb)
    assert 'class="profile-avatar-neutral"' in html
    assert 'pro-avatar' not in html

    # 4. Account ID in mono with copy trigger
    assert f"ps_usr_{user['id']:04d}" in html
    assert 'onclick="copyAccountId(' in html

    # 5. Mono headings and jargon removed
    assert "account_identity.key" not in html
    assert "preferences.ini" not in html
    assert "Deployment Status" not in html


def test_profile_update_and_email_change_password_gate(client):
    user = login_test_user(client)

    # 1. Update name and domain without changing email
    res = client.post(
        "/api/profile/update",
        json={"name": "Kavy Sharma Updated", "company_domain": "kavy-defense.io", "email": user["email"]}
    )
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert data["user"]["name"] == "Kavy Sharma Updated"

    # 2. Attempt to change email without providing current password -> must be gated
    res_gate = client.post(
        "/api/profile/update",
        json={"name": "Kavy Sharma Updated", "company_domain": "kavy-defense.io", "email": "new_email@phishsim.ai", "current_password": ""}
    )
    assert res_gate.status_code == 400
    gate_data = res_gate.get_json()
    assert "password is required" in gate_data["error"].lower()

    # 3. Attempt with wrong password -> must fail
    res_wrong = client.post(
        "/api/profile/update",
        json={"name": "Kavy Sharma Updated", "company_domain": "kavy-defense.io", "email": "new_email@phishsim.ai", "current_password": "wrongpassword"}
    )
    assert res_wrong.status_code == 400
    assert "incorrect" in res_wrong.get_json()["error"].lower()


def test_password_change_strength_and_match_validation(client):
    user = login_test_user(client)

    # 1. Wrong current password
    res_bad_curr = client.post(
        "/change-password",
        json={"current_password": "incorrectpassword", "new_password": "validNewPass123!", "confirm_password": "validNewPass123!"}
    )
    assert res_bad_curr.status_code == 400

    # 2. Mismatched confirm password
    res_mismatch = client.post(
        "/change-password",
        json={"current_password": "testpass123", "new_password": "validNewPass123!", "confirm_password": "differentPassword!"}
    )
    assert res_mismatch.status_code == 400
    assert "match" in res_mismatch.get_json()["error"].lower()

    # 3. Too short password (< 8 chars)
    res_short = client.post(
        "/change-password",
        json={"current_password": "testpass123", "new_password": "short", "confirm_password": "short"}
    )
    assert res_short.status_code == 400
    assert "8 characters" in res_short.get_json()["error"]


def test_2fa_test_code_and_backup_codes_lifecycle(client):
    user = login_test_user(client)

    # 1. Send test code
    res_send = client.post("/test-2fa-send")
    assert res_send.status_code == 200
    send_data = res_send.get_json()
    assert send_data["success"] is True

    # Extract test code from session
    with client.session_transaction() as sess:
        test_code = sess.get("test_2fa_code")
    assert test_code is not None

    # 2. Verify test code -> enables 2FA and returns 8 backup recovery codes
    res_verify = client.post("/test-2fa-verify", json={"otp_code": test_code})
    assert res_verify.status_code == 200
    verify_data = res_verify.get_json()
    assert verify_data["success"] is True
    assert "backup_codes" in verify_data
    assert len(verify_data["backup_codes"]) == 8

    # 3. Retrieve backup codes endpoint
    res_codes = client.get("/api/profile/2fa/backup-codes")
    assert res_codes.status_code == 200
    assert len(res_codes.get_json()["backup_codes"]) == 8

    # 4. Disable 2FA
    res_disable = client.post("/api/profile/2fa/disable")
    assert res_disable.status_code == 200
    assert res_disable.get_json()["success"] is True

    # 5. Fetch backup codes when disabled -> 400
    res_codes_disabled = client.get("/api/profile/2fa/backup-codes")
    assert res_codes_disabled.status_code == 400


def test_preferences_instant_save_and_persistence(client):
    user = login_test_user(client)

    # 1. Save preferences via API
    res = client.post(
        "/api/profile/preferences",
        json={
            "theme": "system",
            "timezone": "America/New_York",
            "date_format": "DD/MM/YYYY",
            "default_delivery_mode": "mailtrap",
            "default_scenario": "urgent_invoice"
        }
    )
    assert res.status_code == 200
    assert res.get_json()["success"] is True

    # 2. Verify persistence survives fresh lookup
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT theme, timezone, date_format, default_delivery_mode, default_scenario FROM users WHERE id = %s", (user["id"],))
    row = cursor.fetchone()
    cursor.close()
    db.close()

    assert row["theme"] == "system"
    assert row["timezone"] == "America/New_York"
    assert row["date_format"] == "DD/MM/YYYY"
    assert row["default_delivery_mode"] == "mailtrap"
    assert row["default_scenario"] == "urgent_invoice"


def test_notifications_instant_save_and_persistence(client):
    user = login_test_user(client)

    # Save notifications via API
    res = client.post(
        "/api/profile/notifications",
        json={
            "notify_report_ready": False,
            "notify_campaign_finished": True,
            "notify_weekly_briefing": False
        }
    )
    assert res.status_code == 200
    assert res.get_json()["success"] is True

    # Verify DB persistence
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT notify_report_ready, notify_campaign_finished, notify_weekly_briefing FROM users WHERE id = %s", (user["id"],))
    row = cursor.fetchone()
    cursor.close()
    db.close()

    assert row["notify_report_ready"] == 0
    assert row["notify_campaign_finished"] == 1
    assert row["notify_weekly_briefing"] == 0


def test_export_data_archive_zip_structure(client):
    user = login_test_user(client)

    res = client.get("/api/profile/export-data")
    assert res.status_code == 200
    assert "zip" in res.headers.get("Content-Type", "")

    # Unpack ZIP in memory and inspect files
    zip_bytes = io.BytesIO(res.data)
    with zipfile.ZipFile(zip_bytes, "r") as zf:
        namelist = zf.namelist()
        assert "profile.json" in namelist
        assert "campaigns.csv" in namelist
        assert "audit_log.csv" in namelist
        assert "telemetry_summary.json" in namelist
        assert "README.txt" in namelist

        profile_json = json.loads(zf.read("profile.json").decode("utf-8"))
        assert profile_json["email"] == user["email"]


def test_delete_account_safeguards(client):
    # 1. Admin deletion blocked from profile
    admin_user = login_test_user(client, email="admin@phishsim.ai", role="admin")
    res_admin = client.post("/delete-account", json={"confirm_email": admin_user["email"]})
    assert res_admin.status_code == 400
    assert "admin accounts cannot be deleted" in res_admin.get_json()["error"].lower()

    # 2. Non-matching email confirmation blocked
    res_mismatch = client.post("/delete-account", json={"confirm_email": "wrong_email@phishsim.ai"})
    assert res_mismatch.status_code == 400
    assert "confirmation email does not match" in res_mismatch.get_json()["error"].lower()

    # 3. Non-admin user can be deleted with matching confirmation email
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT id FROM users WHERE email = %s", ("test_user_delete@example.com",))
    existing = cursor.fetchone()
    if not existing:
        cursor.execute("INSERT INTO users (name, email, password_hash, role) VALUES (%s, %s, %s, %s)",
                       ("Test Delete", "test_user_delete@example.com", generate_password_hash("pass"), "company_user"))
        db.commit()
    cursor.close()
    db.close()

    login_test_user(client, email="test_user_delete@example.com", role="company_user")
    res_delete = client.post("/delete-account", json={"confirm_email": "test_user_delete@example.com"})
    assert res_delete.status_code == 200
    assert res_delete.get_json()["success"] is True
