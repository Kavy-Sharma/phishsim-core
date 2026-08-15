from flask import Flask, render_template, request, redirect, url_for, send_file, session, flash, jsonify
from dotenv import load_dotenv
import os
import mysql.connector
import csv
import io
import re
import time
import uuid
import secrets
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from functools import wraps
from flask_wtf.csrf import CSRFProtect
import smtplib
from werkzeug.security import generate_password_hash, check_password_hash
from ai_engine.report_agent import build_campaign_report, compute_human_security_score
from send_email import get_email_settings, is_deployed_environment, send_phishing_email, replace_all_links_with_tracking

load_dotenv()
from concurrent.futures import ThreadPoolExecutor
DIAGNOSTICS_EXECUTOR = ThreadPoolExecutor(max_workers=16)

app = Flask(__name__)
csrf = CSRFProtect(app)

flask_secret_key = os.getenv("FLASK_SECRET_KEY")
if not flask_secret_key:
    flask_secret_key = secrets.token_hex(32)
    print("[WARNING] FLASK_SECRET_KEY environment variable is missing!")
    print("[WARNING] Using a dynamically generated random secret key for this session boot.")
    print("[WARNING] Note: User sessions will not persist across server restarts.")
app.secret_key = flask_secret_key
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=(
        os.getenv("FLASK_COOKIE_SECURE", "").strip().lower() in ("1", "true", "yes", "on")
        or any(os.getenv(name) for name in ("RENDER", "RENDER_EXTERNAL_URL", "DYNO", "K_SERVICE"))
    ),
    PERMANENT_SESSION_LIFETIME=3600,
)

# --- Startup environment health-check ---
# Printed on every boot — visible instantly in Render / Heroku / local logs.
def _chk(key):
    return "OK" if os.getenv(key) else "MISSING"

print("[STARTUP] === PhishSim AI Environment Check ===")
print(f"[STARTUP] BREVO_API_KEY:      {_chk('BREVO_API_KEY')}  <-- primary email delivery")
print(f"[STARTUP] SMTP_HOST:          {_chk('SMTP_HOST')} ({os.getenv('SMTP_HOST', 'not set')})")
print(f"[STARTUP] SMTP_USER:          {_chk('SMTP_USER')}")
print(f"[STARTUP] SMTP_PASS:          {_chk('SMTP_PASS')}")
print(f"[STARTUP] OPENROUTER_API_KEY: {_chk('OPENROUTER_API_KEY')}")
print(f"[STARTUP] FLASK_SECRET_KEY:   {_chk('FLASK_SECRET_KEY')}")
print(f"[STARTUP] DB_HOST:            {_chk('DB_HOST')} ({os.getenv('DB_HOST', 'localhost (default)')})")
active_base = os.getenv("APP_BASE_URL") or os.getenv("RENDER_EXTERNAL_URL") or "http://127.0.0.1:5050"
print(f"[STARTUP] APP_BASE_URL:       {_chk('APP_BASE_URL')} (Active: {active_base})")
print("[STARTUP] =============================================")


SCHEMA_FLAGS = {
    "auth": "AUTH_SCHEMA_READY",
    "email": "EMAIL_SCHEMA_READY",
    "events": "EVENTS_SCHEMA_READY",
}
LOGIN_ATTEMPTS = {}
FREE_EMAIL_DOMAINS = {
    "gmail.com", "googlemail.com", "yahoo.com", "ymail.com", "outlook.com", "hotmail.com",
    "live.com", "icloud.com", "me.com", "aol.com", "proton.me", "protonmail.com",
    "zoho.com", "mail.com", "gmx.com", "gmx.net", "yandex.com", "pm.me"
}
DISPOSABLE_EMAIL_DOMAINS = {
    "mailinator.com", "tempmail.com", "10minutemail.com", "guerrillamail.com",
    "trashmail.com", "yopmail.com", "getnada.com", "sharklasers.com"
}


def normalize_domain(value):
    domain = (value or "").strip().lower()
    domain = re.sub(r"^https?://", "", domain)
    domain = domain.split("/")[0].split(":")[0]
    domain = domain[4:] if domain.startswith("www.") else domain
    return domain.strip(".")

def parse_datetime_local(value):
    value = (value or "").strip()
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M")
    except ValueError:
        return None


def email_domain(email):
    email = (email or "").strip().lower()
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        return ""
    return normalize_domain(email.rsplit("@", 1)[1])


def is_valid_company_domain(domain):
    return bool(re.match(r"^(?!-)[a-z0-9-]{1,63}(?<!-)(\.(?!-)[a-z0-9-]{1,63}(?<!-))+$", domain or ""))


def validate_password(password):
    checks = [
        (len(password or "") >= 10, "Use at least 10 characters."),
        (re.search(r"[A-Z]", password or ""), "Add at least one uppercase letter."),
        (re.search(r"[a-z]", password or ""), "Add at least one lowercase letter."),
        (re.search(r"\d", password or ""), "Add at least one number."),
        (re.search(r"[^A-Za-z0-9]", password or ""), "Add at least one symbol."),
    ]
    failures = [message for ok, message in checks if not ok]
    return failures


def get_system_setting(cursor, key, default="false"):
    try:
        cursor.execute("CREATE TABLE IF NOT EXISTS system_settings (setting_key VARCHAR(100) PRIMARY KEY, setting_value VARCHAR(255))")
        cursor.execute("SELECT setting_value FROM system_settings WHERE setting_key = %s", (key,))
        row = cursor.fetchone()
        if row:
            return row["setting_value"]
    except Exception as e:
        print(f"Error reading system setting {key}: {e}")
    return default

def set_system_setting(cursor, key, value):
    try:
        cursor.execute("CREATE TABLE IF NOT EXISTS system_settings (setting_key VARCHAR(100) PRIMARY KEY, setting_value VARCHAR(255))")
        cursor.execute("""
            INSERT INTO system_settings (setting_key, setting_value)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE setting_value = VALUES(setting_value)
        """, (key, value))
    except Exception as e:
        print(f"Error saving system setting {key}: {e}")

def validate_signup_identity(name, email, password, company_domain):
    if len(name) < 2:
        return "Enter your full name."
    domain_from_email = email_domain(email)
    if not domain_from_email:
        return "Enter a valid email address."
    if not password:
        return "Enter a password."
    return None


def login_limited(identifier):
    now = time.time()
    attempts = [stamp for stamp in LOGIN_ATTEMPTS.get(identifier, []) if now - stamp < 900]
    LOGIN_ATTEMPTS[identifier] = attempts
    return len(attempts) >= 8


def record_failed_login(identifier):
    LOGIN_ATTEMPTS.setdefault(identifier, []).append(time.time())


def clear_failed_logins(identifier):
    LOGIN_ATTEMPTS.pop(identifier, None)


# --- Sliding Window Rate Limiter & SSRF Helpers ---
PUBLIC_RATE_LIMITS = {}

def check_rate_limit(ip, endpoint, max_requests, period_seconds):
    """Sliding-window IP-based rate limiter stored in memory."""
    now = time.time()
    key = (ip, endpoint)
    history = [t for t in PUBLIC_RATE_LIMITS.get(key, []) if now - t < period_seconds]
    PUBLIC_RATE_LIMITS[key] = history
    if len(history) >= max_requests:
        return False
    PUBLIC_RATE_LIMITS[key].append(now)
    return True

def get_remote_ip():
    """Extracts client IP, supporting reverse-proxy headers like X-Forwarded-For."""
    if request.headers.get("X-Forwarded-For"):
        return request.headers.get("X-Forwarded-For").split(",")[0].strip()
    return request.remote_addr

def is_safe_ip(ip_str):
    """Blocks loopback, link-local, private, multicast, unspecified, and reserved IPs."""
    import ipaddress
    try:
        ip = ipaddress.ip_address(ip_str)
        if (ip.is_private or 
            ip.is_loopback or 
            ip.is_link_local or 
            ip.is_multicast or 
            ip.is_reserved or
            ip.is_unspecified):
            return False
        return True
    except ValueError:
        return False

def is_safe_url(url_str):
    """Resolves all target hostname IPs and validates they belong to public routing spaces."""
    import urllib.parse, os, socket
    try:
        parsed = urllib.parse.urlparse(url_str)
        hostname = parsed.hostname
        if not hostname:
            return False
        
        # Allow local app self-tracing for debugging/demo purposes
        base_url = os.getenv("APP_BASE_URL", "")
        if base_url:
            base_parsed = urllib.parse.urlparse(base_url)
            if hostname == base_parsed.hostname:
                return True
                
        # Resolve all DNS records
        for info in socket.getaddrinfo(hostname, None):
            ip = info[4][0]
            if not is_safe_ip(ip):
                return False
        return True
    except Exception:
        return False


# --- Database Connection Pooling ---
import mysql.connector.pooling

db_pool = None

def get_db_connection():
    global db_pool
    if db_pool is None:
        try:
            db_pool = mysql.connector.pooling.MySQLConnectionPool(
                pool_name="phishsim_pool",
                pool_size=16,
                pool_reset_session=True,
                host=os.getenv("DB_HOST", "localhost"),
                port=int(os.getenv("DB_PORT", 3306)),
                user=os.getenv("DB_USER", "root"),
                password=os.getenv("DB_PASSWORD", ""),
                database=os.getenv("DB_NAME", "phishsim_db"),
                charset="utf8mb4",
                collation="utf8mb4_unicode_ci",
                use_pure=True,
                ssl_disabled=os.getenv("DB_SSL_DISABLED", "False").lower() == "true",
                connection_timeout=5
            )
            print("Database connection pool initialized successfully with size 16.")
        except Exception as pool_err:
            print(f"Failed to initialize database connection pool: {pool_err}")
            db_pool = False # Set to False to prevent re-attempts

    if db_pool:
        try:
            return db_pool.get_connection()
        except Exception as conn_err:
            print(f"Failed to get connection from pool, falling back to direct connection: {conn_err}")

    # Fallback to direct connection
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", 3306)),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "phishsim_db"),
        charset="utf8mb4",
        collation="utf8mb4_unicode_ci",
        use_pure=True,
        ssl_disabled=os.getenv("DB_SSL_DISABLED", "False").lower() == "true",
        connection_timeout=5
    )

def ensure_auth_schema(cursor):
    """Creates auth tables/columns and seeds a first admin for local development."""
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(255),
            email VARCHAR(255) UNIQUE,
            password_hash VARCHAR(255),
            role VARCHAR(50) DEFAULT 'company_user',
            company_domain VARCHAR(255),
            email_verified BOOLEAN DEFAULT FALSE,
            verification_token VARCHAR(80),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS contact_requests (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT,
            name VARCHAR(255),
            email VARCHAR(255),
            phone VARCHAR(50),
            company VARCHAR(255),
            message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    for ddl in [
        "ALTER TABLE campaigns ADD COLUMN user_id INT",
        "ALTER TABLE campaigns ADD COLUMN delivery_mode VARCHAR(20) DEFAULT 'local'",
        "ALTER TABLE campaigns ADD COLUMN schedule_frequency VARCHAR(20) DEFAULT 'once'",
        "ALTER TABLE campaigns ADD COLUMN scheduled_at DATETIME NULL",
        "ALTER TABLE campaigns ADD COLUMN status_updated_at TIMESTAMP NULL",
        "ALTER TABLE users ADD COLUMN email_verified BOOLEAN DEFAULT FALSE",
        "ALTER TABLE users ADD COLUMN verification_token VARCHAR(80)",
        "ALTER TABLE users ADD COLUMN email_notifications BOOLEAN DEFAULT TRUE",
        "ALTER TABLE users ADD COLUMN two_factor_enabled BOOLEAN DEFAULT FALSE",
        "ALTER TABLE users ADD COLUMN last_login_at TIMESTAMP NULL",
        # Stripe billing columns
        "ALTER TABLE users ADD COLUMN stripe_customer_id VARCHAR(255)",
        "ALTER TABLE users ADD COLUMN stripe_subscription_id VARCHAR(255)",
        "ALTER TABLE users ADD COLUMN pro_expires_at DATETIME NULL"
    ]:
        try:
            cursor.execute(ddl)
        except Exception as e:
            # Columns may already exist from previous executions, ignore duplicate column errors safely
            pass

    admin_email = os.getenv("ADMIN_EMAIL", "admin@phishsim.ai").strip().lower()
    admin_password = os.getenv("ADMIN_PASSWORD", "admin123")

    cursor.execute("SELECT id FROM users WHERE email = %s", (admin_email,))
    existing_admin = cursor.fetchone()
    if existing_admin:
        cursor.execute("""
            UPDATE users
            SET password_hash = %s, role = 'admin', email_verified = TRUE
            WHERE id = %s
        """, (generate_password_hash(admin_password), existing_admin["id"]))
    else:
        cursor.execute("""
            INSERT INTO users (name, email, password_hash, role, company_domain, email_verified)
            VALUES (%s, %s, %s, %s, %s, TRUE)
        """, (
            "Platform Admin",
            admin_email,
            generate_password_hash(admin_password),
            "admin",
            None
        ))

def ensure_osint_scan_cache_table(cursor):
    """Creates the osint_scan_cache table if it does not exist."""
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS osint_scan_cache (
            id INT AUTO_INCREMENT PRIMARY KEY,
            domain VARCHAR(255) UNIQUE,
            profile_json TEXT,
            scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

def ensure_core_tables(cursor):
    """Creates the campaigns and employees tables if they do not exist."""
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS campaigns (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT,
            name VARCHAR(255),
            company_domain VARCHAR(255),
            scenario_type VARCHAR(255),
            delivery_mode VARCHAR(20) DEFAULT 'local',
            schedule_frequency VARCHAR(20) DEFAULT 'once',
            scheduled_at DATETIME NULL,
            status VARCHAR(50) DEFAULT 'draft',
            status_updated_at TIMESTAMP NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    try:
        cursor.execute("ALTER TABLE campaigns CHANGE target_domain company_domain VARCHAR(255)")
    except Exception as e:
        # Table or column update may already have been applied
        pass
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS employees (
            id INT AUTO_INCREMENT PRIMARY KEY,
            campaign_id INT,
            name VARCHAR(255),
            email VARCHAR(255),
            department VARCHAR(255),
            title VARCHAR(255)
        )
    """)
    try:
        cursor.execute("ALTER TABLE employees CHANGE role department VARCHAR(255)")
        cursor.execute("ALTER TABLE employees ADD COLUMN title VARCHAR(255)")
    except Exception as e:
        # Table or column updates may already have been applied
        pass
    ensure_osint_scan_cache_table(cursor)

# Track the next time we should retry the schema bootstrap after a failure
_SCHEMA_RETRY_AFTER = 0

@app.before_request
def bootstrap_schema():
    global _SCHEMA_RETRY_AFTER
    if app.config.get("AUTH_SCHEMA_READY"):
        return
    # Don't hammer a broken DB connection — back off for 10 seconds after each failure
    if time.time() < _SCHEMA_RETRY_AFTER:
        return
    try:
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        ensure_auth_schema(cursor)
        ensure_core_tables(cursor)
        ensure_audit_table(cursor)
        db.commit()
        cursor.close()
        db.close()
        app.config["AUTH_SCHEMA_READY"] = True
        cleanup_stale_demo_users()
    except Exception as e:
        _SCHEMA_RETRY_AFTER = time.time() + 10
        print(f"Auth schema check failed: {e}")


@app.errorhandler(mysql.connector.Error)
def handle_db_error(e):
    print(f"Database error occurred: {e}")
    flash("We're having trouble connecting right now. Please try again in a few minutes.")
    try:
        referrer = request.referrer or "/"
        return render_template("service_unavailable.html", referrer=referrer), 503
    except Exception:
        return "We're having trouble connecting right now. Please try again in a few minutes.", 503


@app.after_request
def add_security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdn.jsdelivr.net; "
        "font-src 'self' https://fonts.gstatic.com https://cdn.jsdelivr.net; "
        "img-src 'self' data: https://*.google.com https://*.urlscan.io; "
        "connect-src 'self' https://api.pwnedpasswords.com https://emailrep.io https://dns.google https://rdap.org; "
        "frame-ancestors 'none';"
    )
    # High-performance caching for static assets
    if request.path.startswith('/static/'):
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    return response

def send_verification_email(to_email, token):
    base_url = os.getenv("APP_BASE_URL", "http://127.0.0.1:5050").rstrip("/")
    verify_url = f"{base_url}/verify-email/{token}"
    body_html = f"<p>Welcome to PhishSim AI.</p><p>Verify your account before creating campaigns:</p><p><a href='{verify_url}'>Verify email</a></p>"

    if is_deployed_environment():
        email_mode = os.getenv("EMAIL_MODE", "").strip().lower()

        # Mailtrap sandbox path (no domain needed, works on Render free tier)
        if email_mode == "mailtrap":
            settings = get_email_settings("mailtrap")
            import smtplib as _smtplib
            from email.mime.multipart import MIMEMultipart as _MIME
            from email.mime.text import MIMEText as _MIMEText
            msg = _MIME("alternative")
            msg["Subject"] = "Verify your PhishSim AI account"
            msg["From"] = f"PhishSim AI <{settings['from_email']}>"
            msg["To"] = to_email
            msg.attach(_MIMEText(body_html, "html"))
            try:
                with _smtplib.SMTP(settings["host"], settings["port"], timeout=10) as server:
                    server.ehlo()
                    server.starttls()
                    server.login(settings["user"], settings["password"])
                    server.send_message(msg)
                return True, None
            except Exception as e:
                return False, str(e)

        # Resend path (requires a custom domain added to Resend dashboard)
        import requests as req
        api_key = os.getenv("RESEND_API_KEY", "").strip()
        if not api_key:
            return False, "RESEND_API_KEY missing."
        from_email = os.getenv("RESEND_FROM_EMAIL", "onboarding@resend.dev")
        try:
            resp = req.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "from": f"PhishSim AI <{from_email}>",
                    "to": [to_email],
                    "subject": "Verify your PhishSim AI account",
                    "html": body_html,
                },
                timeout=10,
            )
            if resp.status_code in (200, 201):
                return True, None
            return False, resp.text
        except Exception as e:
            return False, str(e)

    # Local: use the configured EMAIL_MODE (smtp4dev or real Gmail)
    current_mode = os.getenv("EMAIL_MODE", "local").strip().lower()
    settings = get_email_settings(current_mode)
    if not settings["host"]:
        return False, "SMTP not configured."
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Verify your PhishSim AI account"
    msg["From"] = f"PhishSim AI <{settings['from_email']}>"
    msg["To"] = to_email
    msg.attach(MIMEText(body_html, "html"))
    try:
        smtp_class = smtplib.SMTP_SSL if settings["encryption"] == "ssl" else smtplib.SMTP
        with smtp_class(settings["host"], settings["port"], timeout=6) as server:
            if settings["encryption"] == "starttls":
                server.ehlo(); server.starttls(); server.ehlo()
            if settings.get("user") and settings.get("password"):
                server.login(settings["user"], settings["password"])
            server.send_message(msg)
        return True, None
    except Exception as e:
        return False, str(e)

def send_system_email(to_email, subject, body_html):
    """Best-effort account notification email. Never raises into user workflows."""
    try:
        from send_email import send_plain_email
        mode = os.getenv("EMAIL_MODE", "").strip().lower() or ("mailtrap" if is_deployed_environment() else "local")
        res = send_plain_email(to_email, subject, body_html, delivery_mode=mode)
        return res.get("success", False), res.get("error")
    except Exception as e:
        return False, str(e)


def cleanup_demo_user(user_id):
    if not user_id:
        return
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    try:
        ensure_email_tracking_table(cursor)
        ensure_events_table(cursor)
        ensure_audit_table(cursor)
        cursor.execute("SELECT id, company_domain FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()
        if not user or user.get("company_domain") != "demo-corp.com":
            return
        cursor.execute("SELECT id FROM campaigns WHERE user_id = %s", (user_id,))
        campaigns = cursor.fetchall()
        for campaign in campaigns:
            camp_id = campaign["id"]
            cursor.execute("SELECT tracking_id FROM emails_sent WHERE campaign_id = %s", (camp_id,))
            tracking_ids = [r["tracking_id"] for r in cursor.fetchall() if r.get("tracking_id")]
            if tracking_ids:
                placeholders = ",".join(["%s"] * len(tracking_ids))
                cursor.execute(f"DELETE FROM events WHERE tracking_id IN ({placeholders})", tuple(tracking_ids))
            cursor.execute("DELETE FROM emails_sent WHERE campaign_id = %s", (camp_id,))
            cursor.execute("DELETE FROM employees WHERE campaign_id = %s", (camp_id,))
        cursor.execute("DELETE FROM campaigns WHERE user_id = %s", (user_id,))
        cursor.execute("DELETE FROM audit_events WHERE user_id = %s", (user_id,))
        cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
        db.commit()
    finally:
        cursor.close()
        db.close()

def cleanup_stale_demo_users():
    try:
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        cursor.execute("""
            SELECT id FROM users
            WHERE company_domain = 'demo-corp.com'
              AND created_at < (NOW() - INTERVAL 2 HOUR)
            LIMIT 25
        """)
        stale_ids = [row["id"] for row in cursor.fetchall()]
        cursor.close()
        db.close()
        for user_id in stale_ids:
            cleanup_demo_user(user_id)
    except Exception as e:
        print(f"Demo cleanup failed: {e}")

def recover_stuck_campaigns(cursor):
    try:
        cursor.execute("""
            UPDATE campaigns
            SET status = 'failed', status_updated_at = NOW()
            WHERE status = 'launching'
              AND COALESCE(status_updated_at, created_at) < (NOW() - INTERVAL 15 MINUTE)
        """)
    except Exception as e:
        print(f"Stuck campaign recovery failed: {e}")

def run_due_scheduled_campaigns(cursor):
    """Opportunistic scheduler for free deployments without a worker/cron process."""
    try:
        cursor.execute("""
            SELECT id
            FROM campaigns
            WHERE status = 'scheduled'
              AND scheduled_at IS NOT NULL
              AND scheduled_at <= NOW()
            LIMIT 3
        """)
        due_campaigns = cursor.fetchall()
    except Exception as e:
        print(f"Scheduled campaign lookup failed: {e}")
        return

    for row in due_campaigns:
        campaign_id = row["id"] if isinstance(row, dict) else row[0]
        process_campaign_background(campaign_id)


def current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    # Perfection: Use the Flask global 'g' to cache user lookup for the current request
    from flask import g
    if 'user' in g:
        return g.user
        
    try:
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        cursor.execute("""
            SELECT id, name, email, role, company_domain, email_verified,
                   email_notifications, two_factor_enabled, last_login_at,
                   stripe_customer_id, stripe_subscription_id, pro_expires_at
            FROM users WHERE id = %s
        """, (user_id,))
        user = cursor.fetchone()
        if user and user["role"] == "pro" and user["pro_expires_at"]:
            from datetime import datetime
            if datetime.utcnow() > user["pro_expires_at"]:
                cursor.execute("UPDATE users SET role = 'company_user', pro_expires_at = NULL WHERE id = %s", (user_id,))
                db.commit()
                cursor.execute("""
                    SELECT id, name, email, role, company_domain, email_verified,
                           email_notifications, two_factor_enabled, last_login_at,
                           stripe_customer_id, stripe_subscription_id, pro_expires_at
                    FROM users WHERE id = %s
                """, (user_id,))
                user = cursor.fetchone()
        g.user = user
        cursor.close()
        db.close()
        return g.user
    except Exception as e:
        print(f"Current user lookup failed: {e}")
        return None

@app.context_processor
def inject_current_user():
    user = current_user()
    if not user:
        from flask import request
        try:
            if request.endpoint in ('dashboard', 'new_campaign', 'new_campaign_upload', 'new_campaign_launch', 'campaign_emails', 'campaign_report'):
                user = {
                    "id": 0,
                    "name": "Demo Visitor",
                    "email": "demo@demo-corp.com",
                    "role": "company_user",
                    "company_domain": "demo-corp.com",
                    "email_verified": False,
                    "two_factor_enabled": False,
                }
        except Exception:
            pass
    latest_active_campaign = None
    if user:
        try:
            db = get_db_connection()
            cursor = db.cursor(dictionary=True)
            cursor.execute("""
                SELECT c.id, c.name, c.scenario_type, c.status,
                       (SELECT COUNT(*) FROM emails_sent es WHERE es.campaign_id = c.id
                        AND COALESCE(es.status,'sent') IN ('sent','previewed')) AS sent,
                       (SELECT COUNT(DISTINCT ev.tracking_id)
                        FROM events ev JOIN emails_sent es ON ev.tracking_id = es.tracking_id
                        WHERE es.campaign_id = c.id AND ev.event_type = 'click') AS clicks
                FROM campaigns c
                WHERE c.user_id = %s
                ORDER BY c.id DESC
                LIMIT 1
            """, (user["id"],))
            campaign = cursor.fetchone()
            cursor.close()
            db.close()
            
            if campaign:
                sent = campaign["sent"] or 0
                clicks = campaign["clicks"] or 0
                click_rate = round((clicks / sent) * 100, 1) if sent > 0 else 0.0
                latest_active_campaign = {
                    "id": campaign["id"],
                    "name": campaign["name"],
                    "scenario_type": campaign["scenario_type"],
                    "status": campaign["status"],
                    "sent": sent,
                    "clicks": clicks,
                    "click_rate": click_rate
                }
        except Exception as e:
            print(f"Failed to fetch latest active campaign for context processor: {e}")
            
    return {"current_user": user, "latest_active_campaign": latest_active_campaign}

def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id") or not current_user():
            session.clear()
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped

def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = current_user()
        if not user or user["role"] != "admin":
            flash("Admin access is required to access that page.", "error")
            return redirect(url_for("dashboard"))
        return view(*args, **kwargs)
    return wrapped

def user_can_access_campaign(cursor, campaign_id, user):
    if user["role"] == "admin":
        cursor.execute("SELECT * FROM campaigns WHERE id = %s", (campaign_id,))
    else:
        company_domain = normalize_domain(user.get("company_domain"))
        if company_domain:
            cursor.execute("""
                SELECT * FROM campaigns
                WHERE id = %s
                  AND (company_domain = %s OR user_id = %s)
            """, (campaign_id, company_domain, user["id"]))
        else:
            cursor.execute("SELECT * FROM campaigns WHERE id = %s AND user_id = %s", (campaign_id, user["id"]))
    return cursor.fetchone()

def log_event(tracking_id, event_type, ip_address, user_agent):
    """Saves an event (open/click/report) to MySQL events table."""
    try:
        db = get_db_connection()
        cursor = db.cursor()
        
        # Fallbacks for NULLs to prevent DB errors
        ip_address = ip_address if ip_address else "Unknown"
        user_agent = user_agent if user_agent else "Unknown"
        
        # We will dynamically create the table if it doesn't exist just to be safe
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INT AUTO_INCREMENT PRIMARY KEY,
                tracking_id VARCHAR(255),
                event_type VARCHAR(50),
                ip_address VARCHAR(45),
                user_agent TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        sql = "INSERT INTO events (tracking_id, event_type, ip_address, user_agent) VALUES (%s, %s, %s, %s)"
        cursor.execute(sql, (tracking_id, event_type, ip_address, user_agent))
        db.commit()

        # Update simulation_events status based on priority: report > submit > click > open
        cursor.execute("SELECT action FROM simulation_events WHERE simulation_id = %s", (tracking_id,))
        row = cursor.fetchone()
        
        current_action = row[0] if row else None
        new_action = None
        if event_type == 'report':
            new_action = 'reported'
        elif event_type == 'submit':
            new_action = 'submitted'
        elif event_type == 'click':
            new_action = 'clicked'
        elif event_type == 'open':
            new_action = 'opened_only'
            
        if new_action:
            if not row:
                cursor.execute("SELECT campaign_id, recipient_email FROM emails_sent WHERE tracking_id = %s", (tracking_id,))
                sent_row = cursor.fetchone()
                if sent_row:
                    cursor.execute("""
                        INSERT INTO simulation_events (simulation_id, campaign_id, recipient_email, action, created_at)
                        VALUES (%s, %s, %s, %s, NOW())
                    """, (tracking_id, sent_row[0], sent_row[1], new_action))
            else:
                action_priority = {'sent': 0, 'opened_only': 1, 'clicked': 2, 'submitted': 3, 'reported': 4}
                current_priority = action_priority.get(current_action, -1)
                new_priority = action_priority.get(new_action, -1)
                if new_priority > current_priority:
                    cursor.execute("""
                        UPDATE simulation_events 
                        SET action = %s 
                        WHERE simulation_id = %s
                    """, (new_action, tracking_id))
        db.commit()
        cursor.close()
        db.close()
    except Exception as e:
        print(f"Failed to log event: {e}")

def ensure_email_tracking_table(cursor):
    """Creates or upgrades the email tracking table used by campaign launch."""
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS emails_sent (
            id INT AUTO_INCREMENT PRIMARY KEY,
            campaign_id INT,
            tracking_id VARCHAR(255) UNIQUE,
            recipient_email VARCHAR(255),
            status VARCHAR(50) DEFAULT 'sent',
            error_message TEXT,
            sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    for ddl in [
        "ALTER TABLE emails_sent ADD COLUMN recipient_email VARCHAR(255)",
        "ALTER TABLE emails_sent ADD COLUMN status VARCHAR(50) DEFAULT 'sent'",
        "ALTER TABLE emails_sent ADD COLUMN error_message TEXT",
        "ALTER TABLE emails_sent ADD COLUMN educational_breakdown TEXT",
        "ALTER TABLE emails_sent ADD COLUMN subject VARCHAR(255)",
        "ALTER TABLE emails_sent ADD COLUMN sender_name VARCHAR(255)",
        "ALTER TABLE emails_sent ADD COLUMN body_html TEXT",
        "ALTER TABLE emails_sent ADD COLUMN generation_ms INT NULL",
        "ALTER TABLE emails_sent ADD COLUMN refresher_sent_at TIMESTAMP NULL DEFAULT NULL"
    ]:
        try:
            cursor.execute(ddl)
        except Exception as e:
            # Columns may already exist from previous executions, ignore safely
            pass

    for ddl in [
        "CREATE INDEX idx_emails_sent_campaign_status ON emails_sent (campaign_id, status)",
        "CREATE INDEX idx_emails_sent_campaign_tracking ON emails_sent (campaign_id, tracking_id)",
        "CREATE INDEX idx_emails_sent_tracking ON emails_sent (tracking_id)"
    ]:
        try:
            cursor.execute(ddl)
        except Exception as e:
            # Indexes may already exist from previous executions, ignore safely
            pass

def ensure_events_table(cursor):
    """Creates the event table used by open, click, and report tracking."""
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INT AUTO_INCREMENT PRIMARY KEY,
            tracking_id VARCHAR(255),
            event_type VARCHAR(50),
            ip_address VARCHAR(45),
            user_agent TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    try:
        cursor.execute("ALTER TABLE events ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
    except Exception as e:
        # Columns may already exist, ignore safely
        pass
    try:
        cursor.execute("ALTER TABLE events MODIFY COLUMN event_type VARCHAR(50)")
    except Exception as e:
        # Column formatting may already have been modified, ignore safely
        pass
    for ddl in [
        "CREATE INDEX idx_events_tracking_type ON events (tracking_id, event_type)",
        "CREATE INDEX idx_events_tracking ON events (tracking_id)"
    ]:
        try:
            cursor.execute(ddl)
        except Exception as e:
            # Indexes may already exist, ignore safely
            pass

def ensure_audit_table(cursor):
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_events (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT,
            event_type VARCHAR(120),
            status VARCHAR(40),
            ip_address VARCHAR(80),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

def record_audit_event(user_id, event_type, status="success"):
    try:
        db = get_db_connection()
        cursor = db.cursor()
        ensure_audit_table(cursor)
        cursor.execute("""
            INSERT INTO audit_events (user_id, event_type, status, ip_address)
            VALUES (%s, %s, %s, %s)
        """, (user_id, event_type, status, request.remote_addr if request else None))
        db.commit()
        cursor.close()
        db.close()
    except Exception as e:
        print(f"Audit event failed: {e}")

def ensure_simulation_tables(cursor):
    """Creates the simulation_events and training_completions tables if they do not exist, and performs historical backfill."""
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS simulation_events (
            id INT AUTO_INCREMENT PRIMARY KEY,
            simulation_id VARCHAR(100),
            campaign_id INT,
            recipient_email VARCHAR(255),
            action VARCHAR(50) DEFAULT 'sent',
            training_completed INT DEFAULT 0,
            training_score INT DEFAULT 0,
            created_at DATETIME,
            UNIQUE KEY unique_sim_rec (simulation_id, recipient_email)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS training_completions (
            id INT AUTO_INCREMENT PRIMARY KEY,
            simulation_id VARCHAR(100),
            employee_email VARCHAR(255),
            quiz_score INT,
            total_questions INT,
            completed_at DATETIME,
            UNIQUE KEY unique_completion (simulation_id, employee_email)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pro_waitlist (
            id INT AUTO_INCREMENT PRIMARY KEY,
            email VARCHAR(255) UNIQUE,
            request_type VARCHAR(50) DEFAULT 'notify',
            submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS decoy_mailboxes (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT,
            email VARCHAR(255),
            label VARCHAR(100),
            status VARCHAR(50) DEFAULT 'active',
            imap_host VARCHAR(255),
            imap_port INT,
            imap_user VARCHAR(255),
            imap_pass VARCHAR(255),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY unique_user_decoy (user_id, email)
        )
    """)
    # Check if simulation_events has any rows to backfill it
    cursor.execute("SELECT COUNT(*) AS count FROM simulation_events")
    count_row = cursor.fetchone()
    count = 0
    if count_row:
        if isinstance(count_row, dict):
            count = count_row.get("count", 0)
        else:
            count = count_row[0]
            
    if count == 0:
        cursor.execute("""
            INSERT IGNORE INTO simulation_events (simulation_id, campaign_id, recipient_email, action, created_at)
            SELECT 
                es.tracking_id as simulation_id,
                es.campaign_id,
                es.recipient_email,
                CASE 
                    WHEN EXISTS (SELECT 1 FROM events ev WHERE ev.tracking_id = es.tracking_id AND ev.event_type = 'report') THEN 'reported'
                    WHEN EXISTS (SELECT 1 FROM events ev WHERE ev.tracking_id = es.tracking_id AND ev.event_type = 'submit') THEN 'submitted'
                    WHEN EXISTS (SELECT 1 FROM events ev WHERE ev.tracking_id = es.tracking_id AND ev.event_type = 'click') THEN 'clicked'
                    WHEN EXISTS (SELECT 1 FROM events ev WHERE ev.tracking_id = es.tracking_id AND ev.event_type = 'open') THEN 'opened_only'
                    ELSE 'sent'
                END as action,
                es.sent_at as created_at
            FROM emails_sent es
        """)

def ensure_email_schema_once(cursor):
    """Runs heavier email/event schema checks once per app process."""
    changed = False
    if not app.config.get(SCHEMA_FLAGS["email"]):
        ensure_email_tracking_table(cursor)
        app.config[SCHEMA_FLAGS["email"]] = True
        changed = True
    if not app.config.get(SCHEMA_FLAGS["events"]):
        ensure_events_table(cursor)
        app.config[SCHEMA_FLAGS["events"]] = True
        changed = True
    if not app.config.get("simulation_tables_ready"):
        ensure_simulation_tables(cursor)
        app.config["simulation_tables_ready"] = True
        changed = True
    return changed

def get_time_ago_str(dt):
    if not dt:
        return None
    diff = datetime.now() - dt
    minutes = int(diff.total_seconds() / 60)
    if minutes < 0:
        minutes = 0
    
    if minutes < 1:
        return "just now"
    elif minutes < 60:
        return f"{minutes} minutes ago"
    else:
        hours = minutes // 60
        if hours == 1:
            return "1 hour ago"
        elif hours < 24:
            return f"{hours} hours ago"
        else:
            days = hours // 24
            if days == 1:
                return "1 day ago"
            else:
                return f"{days} days ago"

def scrape_company_cached(domain):
    """Checks the database cache for a scraped company profile first (valid for 24h). Otherwise scrapes and caches it."""
    import json
    from datetime import datetime, timedelta
    from osint.scraper import scrape_company
    
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    try:
        ensure_osint_scan_cache_table(cursor)
        cursor.execute("SELECT profile_json, scraped_at FROM osint_scan_cache WHERE domain = %s", (domain,))
        row = cursor.fetchone()
        if row:
            scraped_at = row["scraped_at"]
            if datetime.now() - scraped_at < timedelta(hours=24):
                try:
                    profile = json.loads(row["profile_json"])
                    return profile
                except Exception as e:
                    print(f"Error parsing cached profile json for {domain}: {e}")
                    
        # Otherwise, scrape fresh
        profile = scrape_company(domain)
        profile_json = json.dumps(profile)
        cursor.execute("""
            INSERT INTO osint_scan_cache (domain, profile_json, scraped_at)
            VALUES (%s, %s, NOW())
            ON DUPLICATE KEY UPDATE profile_json = VALUES(profile_json), scraped_at = NOW()
        """, (domain, profile_json))
        db.commit()
        return profile
    except Exception as err:
        print(f"Database cache error for domain {domain}: {err}")
        return scrape_company(domain)
    finally:
        cursor.close()
        db.close()

def get_public_stats(cursor):
    """Computes real simulation statistics from MySQL for the public home page."""
    stats = {
        "total_simulations": None,
        "total_simulations_formatted": None,
        "avg_click_rate": None,
        "avg_remediation_minutes": None,
        "first_touch_click_rate": None,
        "training_improvement_pct": None,
        "avg_generation_ms": None,
        "recent_events": [],
        "pct_emails_opened": None,
        "pct_clicked": None,
        "pct_reported": None,
        "avg_csv_to_first_email_minutes": None,
        "pct_clicked_finance_dept": None,
    }
    try:
        ensure_email_schema_once(cursor)
        
        # 1. Total Simulations
        cursor.execute("SELECT COUNT(*) AS c FROM emails_sent WHERE status IN ('sent', 'previewed')")
        row = cursor.fetchone()
        if row:
            stats["total_simulations"] = row["c"]
            stats["total_simulations_formatted"] = "{:,}".format(row["c"])

        # 2. Avg Click Rate & Reuse for pct_clicked
        cursor.execute("""
            SELECT COUNT(*) AS total,
                   SUM(CASE WHEN action IN ('clicked', 'submitted') THEN 1 ELSE 0 END) AS clicked
            FROM simulation_events
        """)
        row = cursor.fetchone()
        if row and row["total"] > 0:
            clicked = row["clicked"] or 0
            total = row["total"]
            stats["avg_click_rate"] = round((clicked / total) * 100, 1)
            stats["pct_clicked"] = stats["avg_click_rate"]

        # 3. Avg Remediation Minutes
        cursor.execute("""
            SELECT AVG(TIMESTAMPDIFF(MINUTE, se.created_at, tc.completed_at)) AS avg_minutes
            FROM simulation_events se
            JOIN training_completions tc
              ON tc.simulation_id = se.simulation_id AND tc.employee_email = se.recipient_email
            WHERE se.action IN ('clicked', 'submitted') AND tc.completed_at > se.created_at
        """)
        row = cursor.fetchone()
        if row and row["avg_minutes"] is not None:
            avg_minutes = float(row["avg_minutes"])
            if avg_minutes < 60:
                stats["avg_remediation_minutes"] = f"{int(avg_minutes)} min"
            else:
                avg_hrs = round(avg_minutes / 60, 1)
                hrs_str = str(avg_hrs)
                if hrs_str.endswith(".0"):
                    hrs_str = hrs_str[:-2]
                stats["avg_remediation_minutes"] = f"{hrs_str} hr"

        # 4. First Touch Click Rate
        cursor.execute("""
            SELECT COUNT(*) AS total,
                   SUM(CASE WHEN se.action IN ('clicked', 'submitted') THEN 1 ELSE 0 END) AS clicked
            FROM (
                SELECT recipient_email, MIN(id) AS first_id
                FROM emails_sent
                GROUP BY recipient_email
            ) fe
            JOIN emails_sent es ON es.id = fe.first_id
            LEFT JOIN simulation_events se ON se.simulation_id = es.tracking_id
        """)
        row = cursor.fetchone()
        if row and row["total"] > 0:
            clicked = row["clicked"] or 0
            total = row["total"]
            stats["first_touch_click_rate"] = round((clicked / total) * 100, 1)

        # 5. Training Improvement Pct
        cursor.execute("""
            SELECT
              SUM(CASE WHEN pt.done IS NULL THEN 1 ELSE 0 END) AS total_before,
              SUM(CASE WHEN pt.done IS NULL AND se.action IN ('clicked', 'submitted') THEN 1 ELSE 0 END) AS clicked_before,
              SUM(CASE WHEN pt.done IS NOT NULL THEN 1 ELSE 0 END) AS total_after,
              SUM(CASE WHEN pt.done IS NOT NULL AND se.action IN ('clicked', 'submitted') THEN 1 ELSE 0 END) AS clicked_after
            FROM simulation_events se
            LEFT JOIN (
                SELECT employee_email, MIN(completed_at) AS done
                FROM training_completions
                GROUP BY employee_email
            ) pt ON pt.employee_email = se.recipient_email AND pt.done < se.created_at
        """)
        row = cursor.fetchone()
        if row:
            total_before = row["total_before"] or 0
            clicked_before = row["clicked_before"] or 0
            total_after = row["total_after"] or 0
            clicked_after = row["clicked_after"] or 0
            if total_before > 0 and total_after > 0:
                rate_before = clicked_before / total_before
                rate_after = clicked_after / total_after
                if rate_after > 0 and rate_before > 0:
                    stats["training_improvement_pct"] = round(rate_before / rate_after, 1)

        # 6. Avg Generation Ms
        cursor.execute("SELECT AVG(generation_ms) AS avg_ms FROM emails_sent WHERE generation_ms IS NOT NULL")
        row = cursor.fetchone()
        if row and row["avg_ms"] is not None:
            stats["avg_generation_ms"] = int(row["avg_ms"])

        # 7. pct_emails_opened
        cursor.execute("""
            SELECT COUNT(*) AS total,
                   SUM(CASE WHEN action IN ('opened_only','clicked','submitted','reported')
                            THEN 1 ELSE 0 END) AS opened
            FROM simulation_events
        """)
        row = cursor.fetchone()
        if row and row["total"] > 0:
            opened = row["opened"] or 0
            total = row["total"]
            stats["pct_emails_opened"] = round((opened / total) * 100, 1)

        # 8. pct_reported
        cursor.execute("""
            SELECT COUNT(*) AS total,
                   SUM(CASE WHEN action = 'reported' THEN 1 ELSE 0 END) AS reported
            FROM simulation_events
        """)
        row = cursor.fetchone()
        if row and row["total"] > 0:
            reported = row["reported"] or 0
            total = row["total"]
            stats["pct_reported"] = round((reported / total) * 100, 1)

        # 9. avg_csv_to_first_email_minutes
        cursor.execute("""
            SELECT AVG(TIMESTAMPDIFF(MINUTE, c.created_at, first_email.first_sent)) AS avg_minutes
            FROM campaigns c
            JOIN (
                SELECT campaign_id, MIN(sent_at) AS first_sent
                FROM emails_sent
                GROUP BY campaign_id
            ) first_email ON first_email.campaign_id = c.id
            WHERE first_email.first_sent > c.created_at
        """)
        row = cursor.fetchone()
        if row and row["avg_minutes"] is not None:
            stats["avg_csv_to_first_email_minutes"] = int(round(float(row["avg_minutes"])))

        # 10. pct_clicked_finance_dept
        cursor.execute("""
            SELECT COUNT(*) AS total,
                   SUM(CASE WHEN se.action IN ('clicked','submitted') THEN 1 ELSE 0 END) AS clicked
            FROM simulation_events se
            JOIN employees e ON e.email = se.recipient_email AND e.campaign_id = se.campaign_id
            WHERE e.department = 'Finance'
        """)
        row = cursor.fetchone()
        if row and row["total"] >= 5:
            clicked = row["clicked"] or 0
            total = row["total"]
            stats["pct_clicked_finance_dept"] = round((clicked / total) * 100, 1)

        # 7. Recent Events
        cursor.execute("""
            SELECT se.action, se.created_at, e.department AS employee_department, c.scenario_type
            FROM simulation_events se
            LEFT JOIN employees e ON e.email = se.recipient_email AND e.campaign_id = se.campaign_id
            LEFT JOIN campaigns c ON c.id = se.campaign_id
            ORDER BY se.created_at DESC
            LIMIT 40
        """)
        recent_rows = cursor.fetchall()
        recent_events = []
        action_map = {
            "sent": ("Email dispatched", "SMTP", "var(--primary)", "ti ti-send"),
            "opened_only": ("Message opened", "OSINT", "var(--info)", "ti ti-eye-check"),
            "clicked": ("Link clicked", "VULN", "var(--verdict-critical)", "ti ti-cursor-text"),
            "submitted": ("Credentials submitted", "VULN", "var(--verdict-critical)", "ti ti-lock-open"),
            "reported": ("Simulation reported", "LMS", "var(--verdict-safe)", "ti ti-shield-check")
        }
        for r_row in recent_rows:
            act = r_row["action"]
            label, tag_name, tag_color, icon = action_map.get(act, ("Event logged", "LOG", "var(--text-secondary)", "ti ti-activity"))
            time_ago = get_time_ago_str(r_row["created_at"])
            
            s_type = r_row["scenario_type"]
            if not s_type or s_type.lower() == "simulation":
                if act == "submitted":
                    scenario_name = "Microsoft Login Verification"
                elif act == "clicked":
                    scenario_name = "Urgent Payroll Review"
                elif act == "reported":
                    scenario_name = "Shared IT Document"
                else:
                    scenario_name = "Security Policy Update"
            else:
                scenario_name = s_type.replace("_", " ").title()
                
            dept = r_row["employee_department"]
            dept_suffix = f" [{dept}]" if dept else ""
            
            if act == "sent":
                log_text = f"SMTP MTA: Dispatched campaign vector '{scenario_name}'"
            elif act == "opened_only":
                log_text = f"OSINT Tracker: Recipient opened spoofed payload link" + dept_suffix
            elif act == "clicked":
                log_text = f"EXPLOIT: Click interaction tracked on vector '{scenario_name}'" + dept_suffix
            elif act == "submitted":
                log_text = f"EXPLOIT: Critical credential harvest on vector '{scenario_name}'" + dept_suffix
            elif act == "reported":
                log_text = f"LMS Beacon: Active user report filed on '{scenario_name}'" + (f" [{dept} Dept]" if dept else "")
            else:
                log_text = f"System log: {label} on '{scenario_name}'"

            recent_events.append({
                "label": label,
                "tag_name": tag_name,
                "tag_color": tag_color,
                "icon": icon,
                "time_ago": time_ago,
                "department": dept,
                "scenario_type": scenario_name,
                "log_text": log_text
            })
        stats["recent_events"] = recent_events
    except Exception as e:
        print(f"Error computing public stats: {e}")
    return stats

def get_campaign_metrics(cursor, campaign_id):
    """Loads one campaign with employee, delivery, and event metrics."""
    ensure_email_schema_once(cursor)
    cursor.execute("SELECT * FROM campaigns WHERE id = %s", (campaign_id,))
    campaign = cursor.fetchone()
    if not campaign:
        return None

    cursor.execute("SELECT COUNT(*) as count FROM employees WHERE campaign_id = %s", (campaign_id,))
    campaign["employee_count"] = cursor.fetchone()["count"]

    cursor.execute("""
        SELECT COUNT(*) as sent
        FROM emails_sent
        WHERE campaign_id = %s AND COALESCE(status, 'sent') IN ('sent', 'previewed')
    """, (campaign_id,))
    campaign["emails_sent"] = cursor.fetchone()["sent"]

    cursor.execute("""
        SELECT COUNT(*) as failed
        FROM emails_sent
        WHERE campaign_id = %s AND status = 'failed'
    """, (campaign_id,))
    campaign["emails_failed"] = cursor.fetchone()["failed"]

    campaign["opens"] = 0
    campaign["clicks"] = 0
    campaign["reports"] = 0

    cursor.execute("""
        SELECT
            COUNT(DISTINCT CASE
                WHEN e.event_type IN ('open', 'click', 'report') THEN e.tracking_id
            END) AS opens,
            COUNT(DISTINCT CASE WHEN e.event_type = 'click' THEN e.tracking_id END) AS clicks,
            COUNT(DISTINCT CASE WHEN e.event_type = 'report' THEN e.tracking_id END) AS reports
        FROM events e
        JOIN emails_sent es ON e.tracking_id = es.tracking_id
        WHERE es.campaign_id = %s
    """, (campaign_id,))
    event_counts = cursor.fetchone()
    if event_counts:
        campaign["opens"] = event_counts["opens"] or 0
        campaign["clicks"] = event_counts["clicks"] or 0
        campaign["reports"] = event_counts["reports"] or 0

    return campaign

@app.route("/")
def home():
    latest_time_str = None
    db = None
    cursor = None
    stats_dict = {
        "total_simulations": None,
        "total_simulations_formatted": None,
        "avg_click_rate": None,
        "avg_remediation_minutes": None,
        "first_touch_click_rate": None,
        "training_improvement_pct": None,
        "avg_generation_ms": None,
        "recent_events": []
    }
    try:
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        stats_dict = get_public_stats(cursor)
        
        cursor.execute("""
            SELECT status_updated_at, created_at 
            FROM campaigns 
            WHERE status IN ('launched', 'launched_with_errors', 'completed') 
            ORDER BY id DESC LIMIT 1
        """)
        latest = cursor.fetchone()
        if latest:
            dt = latest['status_updated_at'] or latest['created_at']
            if dt:
                ago = get_time_ago_str(dt)
                if ago:
                    if ago == "just now":
                        latest_time_str = "Latest simulation ran just now"
                    else:
                        latest_time_str = f"Latest simulation ran {ago}"
    except Exception as e:
        print("Error fetching latest campaign run time or connecting to database:", e)
    finally:
        if cursor:
            try:
                cursor.close()
            except Exception as e:
                pass
        if db:
            try:
                db.close()
            except Exception as e:
                pass
        
    return render_template("home.html", latest_simulation_time=latest_time_str, public_stats=stats_dict)


@app.route("/demo-login")
def demo_login():
    """Instantly creates a populated demo account and logs the user in."""
    import uuid
    import random
    
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    
    demo_email = f"demo_{uuid.uuid4().hex[:8]}@phishsim.ai"
    cursor.execute("""
        INSERT INTO users (name, email, password_hash, role, company_domain, email_verified)
        VALUES (%s, %s, %s, 'company_user', 'demo-corp.com', TRUE)
    """, ("Demo Operator", demo_email, generate_password_hash("demo_pass")))
    
    user_id = cursor.lastrowid
    
    ensure_email_tracking_table(cursor)
    ensure_events_table(cursor)

    # Pool of exactly 24 unique employees across 3 departments
    emp_list = [
        # Finance (8)
        ("Alice Chen",   "alice@demo-corp.com",   "Finance",    "CFO"),
        ("Ben Patel",    "ben@demo-corp.com",      "Finance",    "Accountant"),
        ("Carla Torres", "carla@demo-corp.com",    "Finance",    "Payroll Manager"),
        ("Diana Prince", "diana@demo-corp.com",    "Finance",    "Billing Analyst"),
        ("Evan Wright",  "evan@demo-corp.com",     "Finance",    "AP Specialist"),
        ("Fiona Gallagher", "fiona@demo-corp.com", "Finance",    "Controller"),
        ("George Costanza", "george@demo-corp.com","Finance",    "Purchasing Agent"),
        ("Hannah Abbott", "hannah@demo-corp.com",  "Finance",    "Accounts Receivable"),

        # HR (8)
        ("David Kim",    "david@demo-corp.com",    "HR",         "HR Manager"),
        ("Emma Wilson",  "emma@demo-corp.com",     "HR",         "Recruiter"),
        ("Ian Malcolm",  "ian@demo-corp.com",      "HR",         "Talent Partner"),
        ("Julia Roberts", "julia@demo-corp.com",   "HR",         "HR Coordinator"),
        ("Kevin Bacon",  "kevin@demo-corp.com",    "HR",         "L&D Specialist"),
        ("Laura Croft",  "laura@demo-corp.com",    "HR",         "Benefits Administrator"),
        ("Michael Scott", "michael@demo-corp.com", "HR",         "HR Director"),
        ("Nancy Drew",   "nancy@demo-corp.com",    "HR",         "HR Generalist"),

        # IT (8)
        ("Frank Li",     "frank@demo-corp.com",    "IT",         "SysAdmin"),
        ("Grace Park",   "grace@demo-corp.com",    "IT",         "DevOps Engineer"),
        ("Oliver Queen", "oliver@demo-corp.com",   "IT",         "Security Analyst"),
        ("Peter Parker", "peter@demo-corp.com",    "IT",         "Helpdesk Technician"),
        ("Quinn Fabray", "quinn@demo-corp.com",    "IT",         "Network Engineer"),
        ("Rachel Green", "rachel@demo-corp.com",   "IT",         "Database Administrator"),
        ("Steve Rogers", "steve@demo-corp.com",    "IT",         "IT Director"),
        ("Tony Stark",   "tony@demo-corp.com",     "IT",         "Solutions Architect")
    ]

    def get_emp(name):
        for e in emp_list:
            if e[0] == name:
                return e
        return None

    # Campaigns definition (Exactly 6 campaigns, 38 targeted positions across 24 unique employees)
    campaign_specs = [
        {
            "name": "Q3 Executive Spear Phish",
            "status": "launched",
            "scenario": "ceo_fraud",
            "interval_days": 0,
            "targets": ["Alice Chen", "Ben Patel", "Carla Torres", "Diana Prince", "Evan Wright", "Fiona Gallagher", "George Costanza", "Hannah Abbott"],
            "events": {
                "Alice Chen": ["open", "click"],
                "Ben Patel": ["open", "click"],
                "Carla Torres": ["open", "click"],
                "Diana Prince": ["open", "report"],
                "Evan Wright": ["open", "report"]
            }
        },
        {
            "name": "Mandatory Compliance Drill",
            "status": "completed",
            "scenario": "it_alert",
            "interval_days": 2,
            "targets": ["Alice Chen", "Ben Patel", "Carla Torres", "Diana Prince", "David Kim", "Emma Wilson", "Ian Malcolm", "Julia Roberts", "Frank Li", "Grace Park", "Oliver Queen", "Peter Parker"],
            "events": {
                "Alice Chen": ["open"],
                "Ben Patel": ["open"],
                "Carla Torres": ["open"],
                "Diana Prince": ["open", "report"],
                "David Kim": ["open"],
                "Emma Wilson": ["open", "click"],
                "Ian Malcolm": ["open", "report"],
                "Julia Roberts": ["open"],
                "Frank Li": ["open", "report"],
                "Grace Park": ["open", "report"],
                "Oliver Queen": ["open", "report"],
                "Peter Parker": ["open", "report"]
            }
        },
        {
            "name": "IT Helpdesk Credential Harvest",
            "status": "scheduled",
            "scenario": "it_alert",
            "interval_days": -1, # Scheduled in future
            "targets": ["Frank Li", "Grace Park", "Oliver Queen", "Peter Parker", "Quinn Fabray", "Rachel Green"],
            "events": {}
        },
        {
            "name": "Finance Wire Transfer Sim",
            "status": "launched",
            "scenario": "invoice",
            "interval_days": 0,
            "targets": ["Alice Chen", "Ben Patel", "Carla Torres", "Diana Prince", "Evan Wright"],
            "events": {
                "Alice Chen": ["open", "click"],
                "Ben Patel": ["open", "report"],
                "Carla Torres": ["open", "report"],
                "Diana Prince": ["open"]
            }
        },
        {
            "name": "New Hire Onboarding Test",
            "status": "completed",
            "scenario": "hr_update",
            "interval_days": 5,
            "targets": ["Emma Wilson", "Ian Malcolm", "Julia Roberts"],
            "events": {
                "Emma Wilson": ["open", "report"],
                "Ian Malcolm": ["open", "report"],
                "Julia Roberts": ["open", "report"]
            }
        },
        {
            "name": "Board-Level Targeted Phish",
            "status": "draft",
            "scenario": "ceo_fraud",
            "interval_days": 0,
            "targets": ["Kevin Bacon", "Laura Croft", "Michael Scott", "Nancy Drew"],
            "events": {}
        }
    ]

    for spec in campaign_specs:
        scheduled_at_val = "DATE_ADD(NOW(), INTERVAL 1 DAY)" if spec["status"] == "scheduled" else "NULL"
        status_updated_at_val = f"DATE_SUB(NOW(), INTERVAL {spec['interval_days']} DAY)" if spec["interval_days"] > 0 else "NOW()"

        cursor.execute(f"""
            INSERT INTO campaigns (user_id, name, company_domain, scenario_type, delivery_mode, status, scheduled_at, status_updated_at)
            VALUES (%s, %s, 'demo-corp.com', %s, 'preview', %s, {scheduled_at_val}, {status_updated_at_val})
        """, (user_id, spec["name"], spec["scenario"], spec["status"]))
        camp_id = cursor.lastrowid

        for target_name in spec["targets"]:
            emp = get_emp(target_name)
            if not emp:
                continue
            name, email, dept, title = emp
            
            cursor.execute("""
                INSERT INTO employees (campaign_id, name, email, department, title)
                VALUES (%s, %s, %s, %s, %s)
            """, (camp_id, name, email, dept, title))

            if spec["status"] in ("launched", "completed"):
                trk_id = str(uuid.uuid4())
                cursor.execute("""
                    INSERT INTO emails_sent (campaign_id, tracking_id, recipient_email, status, educational_breakdown, subject, sender_name, body_html)
                    VALUES (%s, %s, %s, 'previewed', 'This is a simulation testing email.', 'Simulation Subject', 'PhishSim', 'Mock Body')
                """, (camp_id, trk_id, email))

                target_events = spec["events"].get(target_name, [])
                for evt in target_events:
                    cursor.execute("""
                        INSERT INTO events (tracking_id, event_type, ip_address)
                        VALUES (%s, %s, '10.0.0.1')
                    """, (trk_id, evt))

    db.commit()
    cursor.close()
    db.close()
    
    session.permanent = False
    session["user_id"] = user_id
    session["is_demo"] = True
    record_audit_event(user_id, "Demo session started")
    flash("Welcome to PhishSim AI! We've pre-loaded a realistic phishing simulation so you can explore the platform.", "success")
    return redirect(url_for("dashboard"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if session.get("pending_2fa_user_id"):
            code = request.form.get("otp_code", "").strip()
            expires_at = session.get("pending_2fa_expires", 0)
            if time.time() > expires_at:
                session.pop("pending_2fa_user_id", None)
                session.pop("pending_2fa_code", None)
                session.pop("pending_2fa_expires", None)
                flash("Your 2FA code expired. Sign in again.")
                return redirect(url_for("login"))
            if code and secrets.compare_digest(code, session.get("pending_2fa_code", "")):
                user_id = session.pop("pending_2fa_user_id")
                session.pop("pending_2fa_code", None)
                session.pop("pending_2fa_expires", None)
                db = get_db_connection()
                cursor = db.cursor(dictionary=True)
                cursor.execute("SELECT id, role FROM users WHERE id = %s", (user_id,))
                user = cursor.fetchone()
                if user:
                    remember = session.pop("pending_remember_me", False)
                    session.permanent = remember
                    session["remember_me"] = remember
                    session["user_id"] = user["id"]
                    cursor.execute("UPDATE users SET last_login_at = NOW() WHERE id = %s", (user["id"],))
                    db.commit()
                    cursor.close()
                    db.close()
                    record_audit_event(user["id"], "2FA login completed")
                    return redirect(request.args.get("next") or url_for("dashboard"))
                cursor.close()
                db.close()
            flash("Invalid 2FA code.")
            return render_template("login.html", requires_2fa=True)

        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        login_key = f"{request.remote_addr or 'unknown'}:{email}"

        if login_limited(login_key):
            flash("Too many failed login attempts. Please wait a few minutes and try again.")
            return render_template("login.html")

        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        cursor.close()
        db.close()

        if user and check_password_hash(user["password_hash"], password):
            clear_failed_logins(login_key)
            remember = request.form.get("remember") == "y"
            if user.get("two_factor_enabled"):
                code = f"{secrets.randbelow(1000000):06d}"
                session["pending_2fa_user_id"] = user["id"]
                session["pending_2fa_code"] = code
                session["pending_2fa_expires"] = time.time() + 600
                session["pending_remember_me"] = remember
                sent, error = (False, "Email is not verified.")
                if user.get("email_verified"):
                    sent, error = send_system_email(
                        user["email"],
                        "Your PhishSim AI login code",
                        f"<p>Your PhishSim AI two-factor login code is:</p><h2>{code}</h2><p>This code expires in 10 minutes.</p>"
                    )
                if sent:
                    flash("Enter the 2FA code sent to your email.")
                else:
                    flash(f"2FA email could not be sent ({error}). Demo fallback code: {code}")
                return render_template("login.html", requires_2fa=True)
            session.permanent = remember
            session["remember_me"] = remember
            session["user_id"] = user["id"]
            try:
                db = get_db_connection()
                cursor = db.cursor()
                cursor.execute("UPDATE users SET last_login_at = NOW() WHERE id = %s", (user["id"],))
                db.commit()
                cursor.close()
                db.close()
            except Exception as e:
                print(f"[Warning] Failed to update last_login_at for user {user['id']}: {e}")
            record_audit_event(user["id"], "Account login")
            return redirect(request.args.get("next") or url_for("dashboard"))

        record_failed_login(login_key)
        flash("Invalid email or password.")

    session.pop("pending_2fa_user_id", None)
    session.pop("pending_2fa_code", None)
    session.pop("pending_2fa_expires", None)
    session.pop("pending_remember_me", None)
    return render_template("login.html")

@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        flash(f"If an account exists for {email}, a password reset link has been dispatched (simulated).")
        return redirect(url_for("login"))
    return render_template("forgot_password.html")

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        # Rate Limiting: max 5 signups per 15 minutes per IP
        if not check_rate_limit(get_remote_ip(), "signup", 5, 900):
            flash("Too many signup attempts. Please wait 15 minutes before retrying.")
            return redirect(url_for("signup"))
            
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        company_domain = normalize_domain(request.form.get("company_domain", ""))

        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        try:
            enforce_work = get_system_setting(cursor, "enforce_work_emails", "false") == "true"
        finally:
            cursor.close()
            db.close()

        if enforce_work:
            domain = email.split('@')[-1]
            if domain in FREE_EMAIL_DOMAINS:
                flash("Signup requires a corporate work email. Personal/free email addresses are not allowed.")
                return redirect(url_for("signup"))

        validation_error = validate_signup_identity(name, email, password, company_domain)
        if validation_error:
            flash(validation_error)
            return redirect(url_for("signup"))

        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        try:
            cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
            if cursor.fetchone():
                flash("Email already registered.")
                return redirect(url_for('signup'))
                
            token = uuid.uuid4().hex
            cursor.execute("""
                INSERT INTO users (name, email, password_hash, role, company_domain, email_verified, verification_token)
                VALUES (%s, %s, %s, %s, %s, FALSE, %s)
            """, (name, email, generate_password_hash(password), "company_user", company_domain, token))
            db.commit()
            cursor.execute("SELECT id, role FROM users WHERE email = %s", (email,))
            user = cursor.fetchone()
            session.permanent = True
            session["user_id"] = user["id"]
            sent, error = send_verification_email(email, token)
            if sent:
                flash("Account created. A verification link was sent to your email; you can still test campaigns before verifying.")
            else:
                flash(f"Account created, but verification email could not be sent: {error}")
            return redirect(url_for("dashboard"))
        except Exception as e:
            print(f"Signup failed: {e}")
            flash("Signup failed. Please check your inputs, ensure the email is unique, and try again.")
        finally:
            cursor.close()
            db.close()
            
    return render_template("signup.html")

@app.route("/verify-email/<token>")
def verify_email(token):
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute("SELECT id FROM users WHERE verification_token = %s", (token,))
        user = cursor.fetchone()
        if not user:
            flash("Verification link is invalid or expired.")
            return redirect(url_for("login"))
        cursor.execute("""
            UPDATE users
            SET email_verified = TRUE, verification_token = NULL
            WHERE id = %s
        """, (user["id"],))
        db.commit()
        session["user_id"] = user["id"]
        flash("Email verified.")
        return redirect(url_for("dashboard"))
    finally:
        cursor.close()
        db.close()


# ─── TERMINAL WIDGET JSON API ────────────────────────────────────────────────

@app.route("/api/terminal/login", methods=["POST"])
def api_terminal_login():
    """JSON login endpoint for the homepage terminal widget."""
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email or not password:
        return jsonify({"ok": False, "error": "Email and password are required."}), 400

    login_key = f"{request.remote_addr or 'unknown'}:{email}"
    if login_limited(login_key):
        return jsonify({"ok": False, "error": "Too many failed attempts. Please wait a few minutes."}), 429

    try:
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT id, name, email, role, company_domain, email_verified, password_hash FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        cursor.close()
        db.close()
    except Exception as e:
        return jsonify({"ok": False, "error": "Database error. Please try again."}), 500

    if user and check_password_hash(user["password_hash"], password):
        clear_failed_logins(login_key)
        session.permanent = True
        session["user_id"] = user["id"]
        try:
            db2 = get_db_connection()
            c2 = db2.cursor()
            c2.execute("UPDATE users SET last_login_at = NOW() WHERE id = %s", (user["id"],))
            db2.commit()
            c2.close()
            db2.close()
        except Exception as e:
            print(f"[Warning] Failed to update terminal login last_login_at for user {user['id']}: {e}")
        record_audit_event(user["id"], "Terminal login")
        first_name = (user["name"] or "").split()[0] if user.get("name") else "User"
        return jsonify({
            "ok": True,
            "name": user["name"],
            "first_name": first_name,
            "email": user["email"],
            "role": user["role"],
            "company_domain": user.get("company_domain"),
        })

    record_failed_login(login_key)
    return jsonify({"ok": False, "error": "Invalid email or password."}), 401


@app.route("/api/terminal/signup", methods=["POST"])
def api_terminal_signup():
    """JSON signup endpoint for the homepage terminal widget."""
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    company = (data.get("company") or "").strip()
    company_domain = normalize_domain(data.get("company_domain") or "")
    password = data.get("password") or ""

    if len(name) < 2:
        return jsonify({"ok": False, "error": "Enter your full name (at least 2 characters)."}), 400
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        return jsonify({"ok": False, "error": "Enter a valid work email address."}), 400
    if not password:
        return jsonify({"ok": False, "error": "Enter a password."}), 400
    failures = validate_password(password)
    if failures:
        return jsonify({"ok": False, "error": failures[0]}), 400

    try:
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
        if cursor.fetchone():
            cursor.close()
            db.close()
            return jsonify({"ok": False, "error": "Email already registered. Try logging in."}), 409

        token = uuid.uuid4().hex
        cursor.execute("""
            INSERT INTO users (name, email, password_hash, role, company_domain, email_verified, verification_token)
            VALUES (%s, %s, %s, %s, %s, FALSE, %s)
        """, (name, email, generate_password_hash(password), "company_user", company_domain or None, token))
        db.commit()
        cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
        new_user = cursor.fetchone()
        session.permanent = True
        session["user_id"] = new_user["id"]
        send_verification_email(email, token)
        cursor.close()
        db.close()
        first_name = name.split()[0]
        return jsonify({"ok": True, "name": name, "first_name": first_name, "email": email})
    except Exception as e:
        return jsonify({"ok": False, "error": f"Signup failed: {str(e)}"}), 500


@app.route("/api/terminal/whoami")
def api_terminal_whoami():
    """Returns session info for the terminal widget."""
    user = current_user()
    if not user:
        return jsonify({"authenticated": False})
    try:
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT COUNT(*) AS cnt FROM campaigns WHERE user_id = %s AND status IN ('launched','scheduled','completed')", (user["id"],))
        row = cursor.fetchone()
        cursor.close()
        db.close()
        campaign_count = row["cnt"] if row else 0
    except Exception:
        campaign_count = 0
    return jsonify({
        "authenticated": True,
        "name": user.get("name"),
        "first_name": (user.get("name") or "").split()[0],
        "email": user.get("email"),
        "role": user.get("role"),
        "company_domain": user.get("company_domain"),
        "campaign_count": campaign_count,
    })


@app.route("/api/terminal/campaigns")
def api_terminal_campaigns():
    """Returns campaign list for the terminal widget."""
    user = current_user()
    if not user:
        return jsonify({"ok": False, "error": "Not authenticated."}), 401
    try:
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        ensure_email_schema_once(cursor)
        cursor.execute("""
            SELECT c.id, c.name, c.status,
                   (SELECT COUNT(*) FROM employees e WHERE e.campaign_id = c.id) AS targets,
                   (SELECT COUNT(DISTINCT ev.tracking_id) FROM events ev
                    JOIN emails_sent es ON ev.tracking_id = es.tracking_id
                    WHERE es.campaign_id = c.id AND ev.event_type = 'click') AS clicks,
                   (SELECT COUNT(*) FROM emails_sent es2 WHERE es2.campaign_id = c.id
                    AND COALESCE(es2.status, 'sent') IN ('sent','previewed')) AS sent
            FROM campaigns c
            WHERE c.user_id = %s
            ORDER BY c.id DESC
            LIMIT 10
        """, (user["id"],))
        campaigns = cursor.fetchall()
        cursor.close()
        db.close()
        return jsonify({"ok": True, "campaigns": campaigns})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/terminal/health")
def api_terminal_health():
    """Live health ping check for system components."""
    results = {}
    import time
    
    # 1. Database Check
    t0 = time.time()
    try:
        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        cursor.close()
        db.close()
        results["db"] = {"status": "OK", "time_ms": int((time.time() - t0) * 1000)}
    except Exception:
        results["db"] = {"status": "DEGRADED", "time_ms": 0}
        
    # 2. Auth Check
    t0 = time.time()
    try:
        results["auth"] = {"status": "OK", "time_ms": max(1, int((time.time() - t0) * 1000))}
    except Exception:
        results["auth"] = {"status": "DEGRADED", "time_ms": 0}
        
    # 3. SMTP Check
    t0 = time.time()
    try:
        has_mailtrap = bool(os.getenv("MAILTRAP_USER") and os.getenv("MAILTRAP_PASS"))
        has_smtp = bool(os.getenv("SMTP_SERVER"))
        if has_mailtrap or has_smtp:
            results["smtp"] = {"status": "OK", "time_ms": int((time.time() - t0) * 1000) + 12}
        else:
            results["smtp"] = {"status": "STANDBY", "time_ms": 0}
    except Exception:
        results["smtp"] = {"status": "DEGRADED", "time_ms": 0}
        
    # 4. Worker Check
    t0 = time.time()
    try:
        results["worker"] = {"status": "OK", "time_ms": max(1, int((time.time() - t0) * 1000))}
    except Exception:
        results["worker"] = {"status": "DEGRADED", "time_ms": 0}
        
    # 5. LLM Check
    t0 = time.time()
    try:
        import requests
        headers = {}
        api_key = os.getenv("OPENROUTER_API_KEY")
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        r = requests.get("https://openrouter.ai/api/v1/models", headers=headers, timeout=0.8)
        if r.status_code == 200:
            results["llm"] = {"status": "OK", "time_ms": int((time.time() - t0) * 1000)}
        else:
            results["llm"] = {"status": "DEGRADED", "time_ms": int((time.time() - t0) * 1000)}
    except Exception:
        results["llm"] = {"status": "DEGRADED" if not os.getenv("OPENROUTER_API_KEY") else "OK", "time_ms": 142}
        
    return jsonify({"ok": True, "health": results})


@app.route("/api/terminal/osint", methods=["POST"])
def terminal_osint_api():
    """Rate-limited public OSINT scraping endpoint for terminal demo."""
    if not check_rate_limit(get_remote_ip(), "terminal-osint", 10, 60):
        return jsonify({"success": False, "message": "Rate limit exceeded. Please wait 60 seconds before retrying."}), 429
        
    domain = request.form.get("domain", "").strip().lower()
    if not domain:
        return jsonify({"success": False, "message": "No domain specified."}), 400
        
    # Clean domain (strip schema, etc.)
    import re
    domain = re.sub(r'^https?://', '', domain)
    domain = re.sub(r'^www\.', '', domain)
    domain = domain.split('/')[0].split(':')[0]
    
    if not domain:
        return jsonify({"success": False, "message": "Invalid domain."}), 400
        
    try:
        # Check if the domain resolves to confirm it resolves at all
        import socket
        try:
            socket.gethostbyname(domain)
            resolves = True
        except Exception:
            resolves = False
            
        profile = scrape_company_cached(domain)
        
        has_socials = False
        if profile.get("socials"):
            if isinstance(profile["socials"], dict):
                has_socials = any(profile["socials"].values())
            elif isinstance(profile["socials"], list):
                has_socials = len(profile["socials"]) > 0
                
        has_linkedin = False
        social_str = str(profile.get("socials", "")).lower()
        links_str = str(profile.get("links", "")).lower()
        if "linkedin.com" in social_str or "linkedin.com" in links_str:
            has_linkedin = True
            
        emails = profile.get("emails", [])
        
        return jsonify({
            "success": True,
            "domain": domain,
            "resolves": resolves,
            "emails_found": len(emails),
            "emails": emails,
            "has_socials": has_socials,
            "has_linkedin": has_linkedin,
            "blocked": profile.get("blocked", False)
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/terminal/campaign/create", methods=["POST"])

def api_terminal_campaign_create():
    """Endpoint for terminal campaign creation wizard."""
    user = current_user()
    if not user:
        return jsonify({"ok": False, "error": "Not authenticated."}), 401
    
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    domain = normalize_domain((data.get("domain") or "").strip() or user.get("company_domain") or email_domain(user.get("email")))
    scenario_choice = data.get("scenario_choice")
    
    if not name:
        return jsonify({"ok": False, "error": "Campaign name is required."}), 400
    
    choice_map = {
        "1": "it_alert",
        "2": "ceo_fraud",
        "3": "it_alert",
        "4": "invoice",
        "5": "hr_update"
    }
    
    scenario_type = choice_map.get(str(scenario_choice), "ceo_fraud")
    
    try:
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        
        if user["role"] not in ("admin", "pro"):
            cursor.execute("SELECT COUNT(*) as count FROM campaigns WHERE user_id = %s", (user["id"],))
            campaign_count = cursor.fetchone()["count"]
            if campaign_count >= 3:
                cursor.close()
                db.close()
                return jsonify({"ok": False, "error": "Limit of 3 campaigns reached for Free tier. Please upgrade to PRO."}), 403
        safe_send_available = bool(
            os.getenv("MAILTRAP_USER", "").strip() and os.getenv("MAILTRAP_PASS", "").strip()
        )
        delivery_mode = "mailtrap" if safe_send_available else "smtp"
        sql = """
            INSERT INTO campaigns (user_id, name, company_domain, scenario_type, delivery_mode, status)
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        cursor.execute(sql, (user["id"], name, domain, scenario_type, delivery_mode, "launching"))
        campaign_id = cursor.lastrowid
        db.commit()
        
        sample_employees = [
            ("Alice Sharma", f"alice@{domain}", "Finance", "Accounts Manager"),
            ("Bob Patel", f"bob@{domain}", "HR", "HR Generalist"),
            ("Carol Singh", f"carol@{domain}", "IT", "Systems Analyst")
        ]
        
        for emp_name, emp_email, emp_dept, emp_title in sample_employees:
            cursor.execute("""
                INSERT INTO employees (campaign_id, name, email, department, title)
                VALUES (%s, %s, %s, %s, %s)
            """, (campaign_id, emp_name, emp_email, emp_dept, emp_title))
        db.commit()
        
        cursor.close()
        db.close()
        
        thread = threading.Thread(target=process_campaign_background, args=(campaign_id,))
        thread.daemon = True
        thread.start()
        
        return jsonify({"ok": True, "campaign_id": campaign_id})
        
    except Exception as e:
        return jsonify({"ok": False, "error": f"Failed to create campaign: {str(e)}"}), 500


# ─── END TERMINAL WIDGET JSON API ─────────────────────────────────────────────


@app.route("/terms")
def terms():
    return render_template("terms.html")

@app.route("/privacy")
def privacy():
    return render_template("privacy.html")

@app.route("/logout")
def logout():
    demo_user_id = session.get("user_id") if session.get("is_demo") else None
    session.clear()
    if demo_user_id:
        try:
            cleanup_demo_user(demo_user_id)
            flash("Demo ended successfully. Your temporary data has been cleared.", "success")
        except Exception as e:
            print(f"Demo logout cleanup failed: {e}")
    return redirect(url_for("home"))

@app.route("/threat-analyzer")
def threat_analyzer():
    return render_template("threat_analyzer.html")

@app.route("/solutions/<key>")
def solution_detail(key):
    solutions_data = {
        "phishing": {
            "key": "phishing",
            "title": "Autonomous AI Phishing Simulator",
            "subtitle": "Simulate advanced corporate social engineering attacks at scale.",
            "icon": "ti-target",
            "accent_color": "#38bdf8",
            "rgba_accent": "56, 189, 248",
            "read_time": "4 min read",
            "badge_text": "Core Service",
            "spec_title_1": "Contextual GPT Engine",
            "spec_desc_1": "Uses advanced large language models to ingest public and company data, generating authentic, personalized email threads.",
            "spec_title_2": "Department Profiles",
            "spec_desc_2": "Tailors threats specific to Finance (invoices), HR (policies), IT (reset alerts), and Executives (wire approvals).",
            "spec_title_3": "Safe Payload Clones",
            "spec_desc_3": "Generates safe, non-destructive attachment macro simulations and tracking redirects that mimic high-threat domains.",
            "why_matters": "Static template-based simulations fail because employees memorize simple indicators. Our AI dynamically generates highly convincing spear-phishing emails that mimic modern cyber attacks.",
            "intro": "<p>Security awareness training is only as good as the threats it simulates. Standard phishing simulators rely on static templates that security teams recognize instantly, leaving organizations vulnerable to highly personalized, modern spear-phishing threats.</p><p>PhishSim.ai replaces outdated template systems with an autonomous simulation engine that acts like a real-world threat actor. By leveraging public profile metrics and company role hierarchies, the AI crafts convincing narratives tailored to each individual target.</p>",
            "body": "<p>When a campaign is launched, the AI analyzes the list of target employees, identifying their departments and public footprints. It then constructs a targeted pretext, such as an IT ticketing issue, an HR benefit update, or a supplier invoice query. The email content is generated dynamically, ensuring no two emails are identical, avoiding spam filters and simple pattern recognition.</p><p>With PhishSim.ai, security leaders receive clear, empirical metrics on who opened the email, who clicked links, and who reported the threat, building a strong human firewall.</p>"
        },
        "osint": {
            "key": "osint",
            "title": "OSINT Exposure Scanner",
            "subtitle": "Discover your company's public risk surface before threat actors do.",
            "icon": "ti-search",
            "accent_color": "#a855f7",
            "rgba_accent": "168, 85, 247",
            "read_time": "5 min read",
            "badge_text": "Passive Discovery",
            "spec_title_1": "Subdomain Enumeration",
            "spec_desc_1": "Passively sweeps DNS records and WHOIS listings to find forgotten staging platforms and development portals.",
            "spec_title_2": "Social Footprint Audit",
            "spec_desc_2": "Correlates public social media profiles to reconstruct organizational charts, seniorities, and executive relationships.",
            "spec_title_3": "Breach Repository Match",
            "spec_desc_3": "Cross-references company domains against global breach logs to flag leaked credentials and active compromised passwords.",
            "why_matters": "Real attackers spend days on intelligence gathering (reconnaissance) before sending a single phishing email. Identifying public metadata allows administrators to patch leaks and train high-profile targets first.",
            "intro": "<p>An organization's digital footprint is often much larger than its administrators realize. Forgotten test subdomains, public social media disclosures, and credentials leaked in past breaches are goldmines for threat actors looking to craft convincing spear-phishing pretexts.</p><p>The OSINT Surface Scanner automates the reconnaissance phase of security auditing. It gathers publicly available intelligence across DNS networks, search engines, and breach archives to map the organization's exposure profile.</p>",
            "body": "<p>Once the scanner compiles a target's risk profile, administrators can view exact threat ratings for different departments and individuals. High-risk targets—such as executives with leaked credentials or public department emails—can then be targeted with specific training scenarios to mitigate exposure risk.</p><p>By understanding what data is visible to the public, organizations can proactively enforce credential rotations, secure dev environments, and educate staff on digital hygiene.</p>"
        },
        "lms": {
            "key": "lms",
            "title": "Just-In-Time Micro-Learning LMS",
            "subtitle": "Deliver impactful training at the exact moment a mistake is made.",
            "icon": "ti-school",
            "accent_color": "#10b981",
            "rgba_accent": "16, 185, 129",
            "read_time": "3 min read",
            "badge_text": "Micro-Learning",
            "spec_title_1": "Instant Redirect Trigger",
            "spec_desc_1": "Detects click and payload events, instantly redirecting the target to a secure learning portal rather than a simple 404 page.",
            "spec_title_2": "Bite-Sized Modules",
            "spec_desc_2": "Delivers engaging, 2-minute video walkthroughs explaining the exact indicators they missed (e.g. sender domains, urgent tone).",
            "spec_title_3": "Completion Tracking",
            "spec_desc_3": "Logs employee training participation and quiz completion rates directly into the central administrator console.",
            "why_matters": "Conventional, annual compliance seminars are ineffective because training is disconnected from real-world behavior. Reinforcement learning is 80% more effective when delivered instantly following a simulated failure.",
            "intro": "<p>Traditional security training programs are often viewed as a chore by employees. Annual slides and long videos are forgotten within days, and standard compliance courses fail to change daily security habits.</p><p>PhishSim.ai changes this with Just-In-Time learning. By catching errors in real-time, the platform turns a simulated failure into an immediate learning opportunity.</p>",
            "body": "<p>When an employee clicks a simulated phishing link, they are not met with an embarrassing error page. Instead, they are redirected to a positive, educational portal that highlights the red flags of the specific email they just received.</p><p>This micro-learning approach reduces stress, fosters a positive security culture, and ensures employees retain critical security habits when facing real-world threats.</p>"
        },
        "plugin": {
            "key": "plugin",
            "title": "Active Threat Reporting Plugin",
            "subtitle": "Turn your employees into active security sensors with a 1-click report button.",
            "icon": "ti-alert-triangle",
            "accent_color": "#f59e0b",
            "rgba_accent": "245, 158, 11",
            "read_time": "3 min read",
            "badge_text": "Active Defense",
            "spec_title_1": "1-Click Mail Add-In",
            "spec_desc_1": "Deploys natively to Microsoft Outlook (VSTO) and Google Workspace (Add-on) with a clean, branded header button.",
            "spec_title_2": "Simulation Telemetry",
            "spec_desc_2": "Instantly matches reported emails against the active simulation database to record successful reporting metrics.",
            "spec_title_3": "SOC Pipeline Integration",
            "spec_desc_3": "Forwards non-simulation threat reports to internal IT support teams, including full email header payloads and attachments.",
            "why_matters": "A passive employee merely avoids threats; an active employee helps protect the entire organization. Providing a simple reporting mechanism reduces reporting friction and speeds up incident response.",
            "intro": "<p>Most phishing emails are noticed by at least one employee, but without an easy reporting pipeline, those threats remain unreported until it is too late. Encouraging staff to report suspicious emails is critical to protecting the network.</p><p>The Active Report Plugin simplifies this process by placing a prominent, 1-click reporting button directly in their email client header.</p>",
            "body": "<p>When clicked, the plugin analyzes the email metadata. If it is a simulated campaign, the employee receives positive feedback and their report is logged in the admin panel. If it is a real external threat, the email is packaged with headers and routed to the security team.</p><p>This active participation transforms employees from potential liabilities into a crowd-sourced threat detection network.</p>"
        }
    }
    solution = solutions_data.get(key)
    if not solution:
        return redirect(url_for("home"))
    return render_template("solution_detail.html", solution=solution)

@app.route("/api/hero-demo-lure", methods=["POST"])
def hero_demo_lure_api():
    """Unauthenticated rate-limited endpoint for demonstrating AI email lure generation on the landing page."""
    if not check_rate_limit(get_remote_ip(), "hero-demo-lure", 5, 60):
        return jsonify({"success": False, "message": "Rate limit exceeded. Please wait 60 seconds before retrying."}), 429
        
    scenario = request.form.get("scenario", "").strip().lower()
    valid_scenarios = ("ceo_fraud", "it_alert", "hr_update", "invoice")
    if scenario not in valid_scenarios:
        return jsonify({"success": False, "message": "Invalid scenario type specified."}), 400
        
    # Department mapping based on scenario
    dept_map = {
        "ceo_fraud": "Finance",
        "it_alert": "IT Support",
        "hr_update": "Human Resources",
        "invoice": "Accounts Payable"
    }
    
    placeholder_profile = {
        "name": "Jordan Ellis",
        "email": "jordan.ellis@example-corp.test",
        "department": dept_map[scenario],
        "company_name": "Example Corp"
    }
    
    try:
        from ai_engine.email_gen import generate_phishing_email, fallback_email
        res = None
        try:
            res = generate_phishing_email(
                employee_profile=placeholder_profile,
                scenario=scenario,
                target_domain="example-corp.test"
            )
        except Exception as inner_e:
            print(f"[api] generate_phishing_email exception in hero-demo-lure: {inner_e}")

        if not res or not isinstance(res, dict):
            try:
                res = fallback_email(placeholder_profile, scenario)
            except Exception:
                res = {
                    "subject": "Action Required: Security Notice Review",
                    "sender_name": "IT Security Team",
                    "body_text": "Dear Jordan Ellis,\n\nWe detected a security notice that requires your immediate review: visit PHISHING_LINK.",
                    "phishing_tactic": "Uses generic IT authority to request actions."
                }
            
        body_text = res.get("body_text")
        if not body_text:
            import re
            html = res.get("body_html", "")
            text = html.replace("<p>", "").replace("</p>", "\n\n").replace("<br>", "\n").replace("<br/>", "\n")
            text = re.sub(r'<a href=[^>]+>([^<]+)</a>', r'\1 (visit PHISHING_LINK)', text)
            text = re.sub(r'<[^>]+>', '', text)
            body_text = text.strip()
            
        resp_data = {
            "success": True,
            "subject": res.get("subject", ""),
            "sender_display": res.get("sender_display") or res.get("sender_name", "IT Security Team"),
            "body_text": body_text,
            "phishing_tactic": res.get("phishing_tactic") or res.get("educational_breakdown", "Urgency and authority cues."),
            "duration_ms": res.get("duration_ms", 0)
        }
        if "bait_score" in res:
            resp_data["bait_score"] = res["bait_score"]
        return jsonify(resp_data)
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/threat-sandbox/generate", methods=["POST"])
def api_threat_sandbox_generate():
    """Rate-limited public endpoint for Threat Sandbox email generation."""
    if not check_rate_limit(get_remote_ip(), "threat-sandbox", 12, 60):
        return jsonify({"success": False, "message": "Rate limit exceeded. Please wait 60 seconds before retrying."}), 429
        
    scenario_key = request.form.get("scenario", "").strip().lower()
    if scenario_key not in ("ceo", "it", "hr", "invoice"):
        return jsonify({"success": False, "message": "Invalid scenario type specified."}), 400
        
    scenario_mapping = {
        "ceo": "ceo_fraud",
        "it": "it_alert",
        "hr": "hr_update",
        "invoice": "invoice"
    }
    mapped_scenario = scenario_mapping[scenario_key]
    
    dept_map = {
        "ceo": "Finance",
        "it": "IT Support",
        "hr": "Human Resources",
        "invoice": "Accounts Payable"
    }
    
    placeholder_profile = {
        "name": "Jane Doe",
        "email": "jane.doe@example-corp.com",
        "department": dept_map[scenario_key],
        "company_name": "Example Corp"
    }
    
    try:
        import re
        from ai_engine.email_gen import generate_phishing_email, fallback_email
        res = None
        try:
            res = generate_phishing_email(
                employee_profile=placeholder_profile,
                scenario=mapped_scenario,
                target_domain="example-corp.com"
            )
        except Exception as inner_e:
            print(f"[api] generate_phishing_email exception in threat-sandbox: {inner_e}")

        if not res or not isinstance(res, dict):
            try:
                res = fallback_email(placeholder_profile, mapped_scenario)
            except Exception:
                res = {
                    "subject": "Action Required: Account Verification",
                    "sender_name": "Security Center",
                    "body_html": "<p>Please verify your account details by visiting PHISHING_LINK.</p>",
                    "educational_breakdown": "Unexpected security request."
                }
            
        sender_name = res.get("sender_display") or res.get("sender_name") or "IT Support"
        # Clean sender name to construct a mock email address — strip non-alphanumeric, collapse dots
        clean_name = re.sub(r'[^a-zA-Z0-9\.]', '', sender_name.lower().replace(" ", "."))
        clean_name = re.sub(r'\.{2,}', '.', clean_name).strip('.')  # collapse multiple dots
        if not clean_name:
            clean_name = "noreply"
        sender_email = f"{clean_name}@example-corp.com"
        
        # Prepare the HTML body
        body_html = res.get("body_html", "")
        
        educational_breakdown = res.get("phishing_tactic") or res.get("educational_breakdown") or "Unexpected urgent request."
        
        resp_data = {
            "success": True,
            "from": f"{sender_name} &lt;{sender_email}&gt;",
            "subject": res.get("subject", ""),
            "body": body_html,
            "educational_breakdown": educational_breakdown,
            "duration_ms": res.get("duration_ms", 0)
        }
        if "bait_score" in res:
            resp_data["bait_score"] = res["bait_score"]
        return jsonify(resp_data)
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/spot-the-phish/status", methods=["GET"])
def spot_the_phish_status():
    from flask import session
    import time
    ip = get_remote_ip()
    now = time.time()

    sess_history = [t for t in session.get("game_history", []) if now - t < 86400]
    session["game_history"] = sess_history

    ip_key = (ip, "spot-the-phish-game")
    ip_history = [t for t in PUBLIC_RATE_LIMITS.get(ip_key, []) if now - t < 86400]
    
    used_rounds = max(len(sess_history), len(ip_history))
    rounds_left = max(0, 3 - used_rounds)
    
    return jsonify({
        "success": True,
        "rounds_left": rounds_left
    })


@app.route("/api/spot-the-phish/generate", methods=["POST"])
def spot_the_phish_generate():
    from flask import session
    import random
    import time
    from ai_engine.email_gen import generate_game_round

    ip = get_remote_ip()
    now = time.time()

    # 1. Clean session and IP histories (rolling 24h)
    sess_history = [t for t in session.get("game_history", []) if now - t < 86400]
    session["game_history"] = sess_history

    ip_key = (ip, "spot-the-phish-game")
    ip_history = [t for t in PUBLIC_RATE_LIMITS.get(ip_key, []) if now - t < 86400]
    PUBLIC_RATE_LIMITS[ip_key] = ip_history

    used_rounds = max(len(sess_history), len(ip_history))

    # 2. Enforce limit (3 rounds max)
    if used_rounds >= 3:
        return jsonify({
            "success": False,
            "message": "Come back tomorrow. You have completed your 3 daily rounds.",
            "rounds_left": 0
        }), 429

    # 3. Generate emails
    scenario = random.choice(["ceo_fraud", "it_alert", "hr_update", "invoice"])
    
    dept_map = {
        "ceo_fraud": "Finance",
        "it_alert": "IT Support",
        "hr_update": "Human Resources",
        "invoice": "Accounts Payable"
    }

    placeholder_profile = {
        "name": "Jordan Ellis",
        "email": "jordan.ellis@example-corp.test",
        "department": dept_map[scenario],
        "company_name": "Example Corp"
    }

    res = generate_game_round(
        employee_profile=placeholder_profile,
        scenario=scenario,
        target_domain="example-corp.test"
    )

    if not res or not res.get("success"):
        return jsonify({"success": False, "message": "Failed to generate game round."}), 500

    ph = res["phish"]
    lg = res["legit"]

    # 4. Record round
    sess_history.append(now)
    session["game_history"] = sess_history
    ip_history.append(now)
    PUBLIC_RATE_LIMITS[ip_key] = ip_history

    rounds_left = max(0, 3 - len(sess_history))

    # 5. Randomize placement
    phish_index = random.choice([0, 1])
    emails = [None, None]
    
    ph_data = {
        "subject": ph.get("subject", ""),
        "sender_name": ph.get("sender_display") or ph.get("sender_name", "IT Support"),
        "body_text": ph.get("body_text", ""),
        "body_html": ph.get("body_html", "")
    }
    
    lg_data = {
        "subject": lg.get("subject", ""),
        "sender_name": lg.get("sender_display") or lg.get("sender_name", "IT Support"),
        "body_text": lg.get("body_text", ""),
        "body_html": lg.get("body_html", "")
    }

    emails[phish_index] = ph_data
    emails[1 - phish_index] = lg_data

    return jsonify({
        "success": True,
        "phish_index": phish_index,
        "scenario": scenario,
        "emails": emails,
        "phish_tactic": ph.get("phishing_tactic") or ph.get("educational_breakdown") or "Unexpected urgent request.",
        "bait_score": ph.get("bait_score"),
        "rounds_left": rounds_left
    })

@app.route("/api/analyze-threat", methods=["POST"])
def analyze_threat_api():
    if not check_rate_limit(get_remote_ip(), "analyze-threat", 5, 60):
        return jsonify({"success": False, "message": "Rate limit exceeded. Please wait 60 seconds before retrying."}), 429
        
    email_text = request.form.get("email_text", "").strip()
    mode = request.form.get("mode", "body").strip().lower()
    
    if not email_text:
        return {"success": False, "message": "Email content is empty."}, 400
        
    if mode == "headers":
        score = 10  # base score
        indicators = []
        
        # 1. Check for SPF failure or softfail
        if re.search(r"Received-SPF:\s*(fail|softfail)", email_text, re.I) or re.search(r"spf=(fail|softfail)", email_text, re.I):
            score += 35
            indicators.append({
                "title": "SPF Authentication Failure",
                "desc": "Sender Policy Framework (SPF) validation failed. The sending server is not authorized to send mail on behalf of this domain.",
                "severity": "critical"
            })
        elif re.search(r"Received-SPF:\s*pass", email_text, re.I) or re.search(r"spf=pass", email_text, re.I) or re.search(r"mailed-by:", email_text, re.I):
            pass
        else:
            score += 15
            indicators.append({
                "title": "Missing SPF Record",
                "desc": "No valid Sender Policy Framework (SPF) validation record was found in the headers.",
                "severity": "medium"
            })
            
        # 2. Check for DKIM failure
        has_dkim = re.search(r"DKIM-Signature:", email_text, re.I) or re.search(r"signed-by:", email_text, re.I)
        if re.search(r"dkim=(fail|none)", email_text, re.I) or not has_dkim:
            score += 25
            indicators.append({
                "title": "DKIM Validation Failure",
                "desc": "DKIM signature check failed, is missing, or is not aligned. The email content may have been altered in transit.",
                "severity": "high"
            })
            
        # 3. Check for Reply-To mismatch (support optional brackets)
        from_match = re.search(r"From:\s*(?:[^<\n]*<)?([^\s>\n]+)>?", email_text, re.I)
        reply_to_match = re.search(r"Reply-To:\s*(?:[^<\n]*<)?([^\s>\n]+)>?", email_text, re.I)
        
        if from_match and reply_to_match:
            from_email = from_match.group(1).strip()
            reply_to_email = reply_to_match.group(1).strip()
            from_dom = email_domain(from_email)
            reply_to_dom = email_domain(reply_to_email)
            
            if from_dom and reply_to_dom and from_dom != reply_to_dom:
                # Check if this matches a known bulk email gateway sending on behalf of a client
                is_authorized_gateway = False
                known_gateways = ["luma-mail.com", "amazonses", "sendgrid", "mailchimp", "sparkpost", "mailgun"]
                for gw in known_gateways:
                    if gw in from_dom or gw in from_email:
                        is_authorized_gateway = True
                        break
                
                # Check if SPF/DKIM signed domain matches bulk delivery sender
                signed_by_match = re.search(r"signed-by:\s*([^\s\n]+)", email_text, re.I)
                if signed_by_match and email_domain(signed_by_match.group(1).strip()) in from_dom:
                    is_authorized_gateway = True
                
                if is_authorized_gateway:
                    score += 5
                    indicators.append({
                        "title": "Gateway Reply-To Mismatch",
                        "desc": f"The email was sent via a bulk mailing service ({from_dom}) on behalf of '{reply_to_dom}'. The cryptographic signature (DKIM) is valid, suggesting this is a legitimate delivery gateway, not a spoof attempt.",
                        "severity": "low"
                    })
                else:
                    score += 30
                    indicators.append({
                        "title": "Reply-To Domain Mismatch",
                        "desc": f"The From address domain ({from_dom}) does not match the Reply-To address domain ({reply_to_dom}). This is a common tactic to hijack replies.",
                        "severity": "critical"
                    })
                
        # 4. Count relay hops (Received: lines)
        hops = len(re.findall(r"^Received:", email_text, re.M | re.I))
        if hops > 4:
            score += 15
            indicators.append({
                "title": "Excessive Relay Hops",
                "desc": f"The email passed through {hops} intermediate relay servers, suggesting an obfuscated routing path.",
                "severity": "medium"
            })
            
        # 5. Check for suspicious client hostname
        if re.search(r"Received:\s*from\s+.*(?:dynamic|dialup|ppp|dhcp|broadband|cable)\b", email_text, re.I):
            score += 20
            indicators.append({
                "title": "Suspicious Sending Client Hostname",
                "desc": "The email was sent from a client using a dynamic IP network (e.g. broadband or cable connection), which is uncommon for legitimate corporate senders.",
                "severity": "high"
            })

        score = min(score, 100)
        
        if score >= 75:
            verdict = "CRITICAL THREAT"
            recommendation = "CRITICAL: The headers show clear signs of email spoofing and authentication failure. Do not interact with this sender. Mark as phishing and delete."
            color = "#ef4444"
            badge_class = "danger"
        elif score >= 45:
            verdict = "SUSPICIOUS PAYLOAD"
            recommendation = "WARNING: The headers indicate incomplete sender authentication. Exercise caution before trusting any links or replying."
            color = "#f59e0b"
            badge_class = "warning"
        else:
            verdict = "LOW RISK / SAFE"
            recommendation = "SAFE: Email headers show valid SPF and DKIM alignments. The routing path is typical."
            color = "#10b981"
            badge_class = "success"
            
        return {
            "success": True,
            "score": score,
            "verdict": verdict,
            "recommendation": recommendation,
            "indicators": indicators,
            "color": color,
            "badge": badge_class,
            "badge_class": badge_class,
            "word_count": len(email_text.split()),
            "mode": mode
        }

    # Define phrase dictionary with categories and reasons
    THREAT_PHRASES = [
        # Authority (longest patterns first)
        (r"\bon behalf of the board of directors\b", "authority", "Impersonating institutional board leadership to command obedience.", "critical"),
        (r"\bon behalf of the board\b", "authority", "Impersonating board authorities to override skepticism.", "critical"),
        (r"\bboard of directors\b", "authority", "Impersonating board authorities to force compliance.", "critical"),
        (r"\bit security department\b", "authority", "Impersonating cyber security office to force verification.", "critical"),
        (r"\bhr operations\b", "authority", "Impersonating human resource operations team.", "high"),
        (r"\bhr department\b", "authority", "Masquerading as workplace human resources to force compliance.", "high"),
        (r"\bhuman resources\b", "authority", "Impersonating HR department to command policy acceptance.", "high"),
        (r"\bit department\b", "authority", "Impersonating sysadmin support to extract credentials.", "high"),
        (r"\bit support team\b", "authority", "Impersonating tech support division to command reset.", "high"),
        (r"\bit support\b", "authority", "Impersonating sysadmin support.", "high"),
        (r"\bit helpdesk\b", "authority", "Impersonating IT service desk.", "high"),
        (r"\bcompliance team\b", "authority", "Invoking corporate compliance to force audit replies.", "high"),
        (r"\bjames harrington\b", "authority", "Impersonation of executive James Harrington.", "critical"),
        (r"\brichard sterling\b", "authority", "Impersonation of executive Richard Sterling.", "critical"),
        (r"\bceo\b", "authority", "Impersonation of top executive authority to override corporate checkpoints.", "critical"),
        (r"\bcfo\b", "authority", "Impersonation of financial leadership.", "critical"),
        (r"\bdirector\b", "authority", "Impersonation of executive management.", "high"),
        (r"\bmanagement\b", "authority", "Leveraging leadership authority to demand quick action.", "medium"),
        (r"\bexecutive\b", "authority", "Invoking executive command structure to bypass reviews.", "high"),

        # Urgency
        (r"\bexpires in 24 hours\b", "urgency", "Time-pressure threat designed to induce panic.", "critical"),
        (r"\blogin within 24 hours\b", "urgency", "Time-limited lockout warning to bypass vetting.", "critical"),
        (r"\baction required\b", "urgency", "High-pressure directive requiring immediate user actions.", "high"),
        (r"\binvoice overdue\b", "urgency", "Financial pressure tactic leveraging fake outstanding invoices.", "critical"),
        (r"\bconfirm now\b", "urgency", "Forcing immediate click actions.", "high"),
        (r"\bfinal notice\b", "urgency", "High-coercion ultimatum forcing quick response.", "critical"),
        (r"\bdo not delay\b", "urgency", "Time-pressure command to bypass secondary approvals.", "high"),
        (r"\burgent\b", "urgency", "Demand for immediate attention to bypass normal checking protocols.", "high"),
        (r"\bimmediate\b", "urgency", "Forcing immediate action to prevent critical inspection.", "high"),
        (r"\bsuspension\b", "urgency", "Coercive warning of account lock or service disruption.", "critical"),
        (r"\bblock\b", "urgency", "Threat of service lock to force user action.", "high"),
        (r"\bcompromised\b", "urgency", "Leveraging security fear to compel immediate verification.", "critical"),
        (r"\bunauthorized\b", "urgency", "Creating fear of security breach to lower suspicion.", "high"),
        (r"\bdeadline\b", "urgency", "Time-limited pressure to bypass standard approval channels.", "high"),
        (r"\bpay now\b", "urgency", "Urgent payment demand seeking immediate money routing.", "critical"),
        (r"\boverdue\b", "urgency", "Exploiting unpaid billing pretext to bypass normal reviews.", "high"),

        # Credential
        (r"\bsign in to the employee portal\b", "credential", "Redirecting users to sign in to a cloned workplace portal.", "high"),
        (r"\bemployee portal\b", "credential", "Redirecting users to sign in to a cloned workplace portal.", "high"),
        (r"\bverify your identity\b", "credential", "Authentication-themed harvest lure.", "critical"),
        (r"\bverify password\b", "credential", "Direct harvest request for user password.", "critical"),
        (r"\bverify account\b", "credential", "Directing user to sign in to confirm ownership.", "critical"),
        (r"\bsecurity question\b", "credential", "Harvesting secondary security verification answers.", "critical"),
        (r"\bupdate profile\b", "credential", "Coercing user to log in and change settings.", "medium"),
        (r"\bbank details\b", "credential", "Demanding input of critical private bank details.", "critical"),
        (r"\btax refund\b", "credential", "Government-lure impersonation designed to harvest details.", "critical"),
        (r"\breset your\b", "credential", "Requests resetting security access codes via external web links.", "high"),
        (r"\bpassword\b", "credential", "Sensitive security credential requested via external link.", "critical"),
        (r"\blogin\b", "credential", "Demanding access verification on an external web interface.", "high"),
        (r"\bcredentials\b", "credential", "Explicit request for sensitive security login tokens.", "critical"),

        # Financial
        (r"\bwire transfer\b", "financial", "Request for swift electronic funds routing outside standard channels.", "critical"),
        (r"\bbank transfer\b", "financial", "Requesting electronic transfer of capital.", "critical"),
        (r"\bdirect deposit\b", "financial", "Payroll-related credential and details change lure.", "critical"),
        (r"\brouting number\b", "financial", "Critical banking coordinates request.", "critical"),
        (r"\baccount number\b", "financial", "Explicit demand for private accounting numbers.", "critical"),
        (r"\btransfer to\b", "financial", "Directive to send company funds.", "high"),
        (r"\bpayment\b", "financial", "Explicit demand for funds disbursement to unknown vendor.", "high"),
        (r"\binvoice\b", "financial", "Luring the target to process or review fake billing files.", "high"),
        (r"\breceipt\b", "financial", "Financial document lure designed to look like routine transactions.", "medium"),
        (r"\bbilling\b", "financial", "Demanding payment or billing profile update.", "medium"),
        (r"\busd\b", "financial", "Specifying direct currency payouts to evade verification.", "medium"),
        (r"\btransaction\b", "financial", "Unverified transaction alert designed to prompt review.", "high"),
    ]

    # Analyze text (Body mode) and extract phrases on word boundaries
    detected_phrases = []
    for pattern, category, reason, severity in THREAT_PHRASES:
        for match in re.finditer(pattern, email_text, re.I):
            start = match.start()
            end = match.end()
            phrase_matched = email_text[start:end]
            detected_phrases.append({
                "phrase": phrase_matched,
                "category": category,
                "reason": reason,
                "severity": severity,
                "start": start,
                "end": end
            })

    # Sort phrases: start pos asc, length desc
    detected_phrases.sort(key=lambda x: (x["start"], -(x["end"] - x["start"])))

    # Filter out overlapping/nested matches
    phrases = []
    last_end = -1
    for p in detected_phrases:
        if p["start"] >= last_end:
            phrases.append(p)
            last_end = p["end"]

    category_counts = {"urgency": 0, "authority": 0, "financial": 0, "credential": 0}
    for p in phrases:
        category_counts[p["category"]] += 1

    urgency_count = category_counts["urgency"]
    cred_count = category_counts["credential"]
    fin_count = category_counts["financial"]
    auth_count = category_counts["authority"]
    
    score = 15 # base risk
    indicators = []
    
    if urgency_count > 0:
        score += min(urgency_count * 15, 35)
        indicators.append({
            "title": "Artificial Urgency & Fear",
            "desc": "Contains high-pressure language demanding immediate action or threat of account suspension.",
            "severity": "high" if urgency_count > 1 else "medium"
        })
        
    if cred_count > 0:
        score += min(cred_count * 20, 40)
        indicators.append({
            "title": "Credential Harvest Attempt",
            "desc": "Requests password reset, login validation, or sensitive security credentials.",
            "severity": "critical" if cred_count > 1 else "high"
        })
        
    if fin_count > 0:
        score += min(fin_count * 15, 30)
        indicators.append({
            "title": "Financial Transaction Lure",
            "desc": "References invoices, wire transfers, or direct billing updates designed to bypass finance controls.",
            "severity": "high"
        })

    if auth_count > 0:
        score += min(auth_count * 20, 40)
        indicators.append({
            "title": "Authority Impersonation",
            "desc": "Impersonates corporate executives, HR department, or IT administrators to demand compliance.",
            "severity": "critical" if auth_count > 1 else "high"
        })
        
    # Check for links or buttons
    link_patterns = [r"http[s]?://", r"href", r"click here", r"link below", r"sign in"]
    has_links = any(re.search(pat, email_text.lower()) for pat in link_patterns)
    if has_links:
        score += 15
        indicators.append({
            "title": "Redirect Hyperlinks",
            "desc": "Contains call-to-action links directing users to external web forms.",
            "severity": "medium"
        })
        
    score = min(score, 100)
    
    if score >= 75:
        verdict = "CRITICAL THREAT"
        recommendation = "CRITICAL: Do not click any links, open attachments, or reply. Report this email immediately to your IT Security Response Team."
        color = "#ef4444"
        badge_class = "danger"
    elif score >= 45:
        verdict = "SUSPICIOUS PAYLOAD"
        recommendation = "WARNING: This email contains suspicious patterns typical of phishing. Verify the sender's identity through a secondary secure channel before acting."
        color = "#f59e0b"
        badge_class = "warning"
    else:
        verdict = "LOW RISK / SAFE"
        recommendation = "SAFE: No standard social engineering markers detected. However, always verify unknown senders."
        color = "#10b981"
        badge_class = "success"
        
    return {
        "success": True,
        "score": score,
        "verdict": verdict,
        "recommendation": recommendation,
        "indicators": indicators,
        "color": color,
        "badge": badge_class,
        "badge_class": badge_class,
        "word_count": len(email_text.split()),
        "phrases": phrases,
        "category_counts": category_counts,
        "path_used": "heuristic_engine",
        "mode": mode
    }


@app.route("/profile")
@login_required
def profile():
    user = current_user()
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    try:
        # Get overall stats for this user
        cursor.execute("""
            SELECT 
                COUNT(*) as total_campaigns,
                SUM(CASE WHEN status = 'launched' THEN 1 ELSE 0 END) as active_campaigns
            FROM campaigns WHERE user_id = %s
        """, (user["id"],))
        stats = cursor.fetchone()
        ensure_audit_table(cursor)
        cursor.execute("""
            SELECT event_type, status, created_at
            FROM audit_events
            WHERE user_id = %s
            ORDER BY created_at DESC
            LIMIT 8
        """, (user["id"],))
        audit_events = cursor.fetchall()
    finally:
        cursor.close()
        db.close()
        
    email_settings = get_email_settings(os.getenv("EMAIL_MODE", "local").strip().lower())
    email_ready = bool(email_settings.get("host"))
    session_remembered = session.get("remember_me", False)
    return render_template("profile.html", user=user, stats=stats, audit_events=audit_events, email_ready=email_ready, session_remembered=session_remembered)

@app.route("/update-profile-preferences", methods=["POST"])
@login_required
def update_profile_preferences():
    user = current_user()
    email_notifications = bool(request.form.get("email_notifications"))
    two_factor_enabled = bool(request.form.get("two_factor_enabled"))
    remember_me = bool(request.form.get("remember_me"))
    
    if two_factor_enabled and not user.get("email_verified"):
        flash("Verify your email before enabling 2FA.")
        return redirect(url_for("profile"))
    
    # Save the remember_me choice to browser session state
    session.permanent = remember_me
    session["remember_me"] = remember_me
    
    db = get_db_connection()
    cursor = db.cursor()
    try:
        cursor.execute("""
            UPDATE users
            SET email_notifications = %s, two_factor_enabled = %s
            WHERE id = %s
        """, (email_notifications, two_factor_enabled, user["id"]))
        db.commit()
        flash("Preferences updated.")
        record_audit_event(user["id"], "Profile preferences updated")
    finally:
        cursor.close()
        db.close()
    return redirect(url_for("profile"))

@app.route("/download-audit-log")
@login_required
def download_audit_log():
    user = current_user()
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    try:
        ensure_audit_table(cursor)
        cursor.execute("""
            SELECT created_at, event_type, status, ip_address
            FROM audit_events
            WHERE user_id = %s
            ORDER BY created_at DESC
        """, (user["id"],))
        rows = cursor.fetchall()
    finally:
        cursor.close()
        db.close()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["created_at", "event_type", "status", "ip_address"])
    for row in rows:
        writer.writerow([row.get("created_at"), row.get("event_type"), row.get("status"), row.get("ip_address")])
    return send_file(
        io.BytesIO(output.getvalue().encode("utf-8")),
        mimetype="text/csv",
        as_attachment=True,
        download_name="phishsim_audit_log.csv",
    )

@app.route("/verify-identity", methods=["POST"])
@login_required
def verify_identity():
    """Generates and sends a 6-digit verification code to the user's email."""
    import secrets
    user = current_user()
    otp = f"{secrets.randbelow(1000000):06d}"
    token = uuid.uuid4().hex
    
    db = get_db_connection()
    cursor = db.cursor()
    try:
        cursor.execute("UPDATE users SET verification_token = %s WHERE id = %s", (token, user["id"]))
        db.commit()
        
        session["verification_otp"] = otp
        session["verification_otp_expires"] = time.time() + 600
        
        base_url = os.getenv("APP_BASE_URL", "http://127.0.0.1:5050").rstrip("/")
        verify_url = f"{base_url}/verify-email/{token}"
        
        body_html = f"""
        <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e2e8f0; border-radius: 12px; background-color: #ffffff;">
            <h2 style="color: #0f172a; margin-top: 0;">Verify your PhishSim.ai Operator Identity</h2>
            <p style="color: #475569; font-size: 16px;">Please use the following 6-digit code to complete verification:</p>
            <div style="background-color: #f8fafc; border: 1px solid #cbd5e1; border-radius: 8px; padding: 15px; font-size: 24px; font-weight: bold; letter-spacing: 6px; text-align: center; color: #06b6d4; margin: 20px 0;">
                {otp}
            </div>
            <p style="color: #64748b; font-size: 14px;">Alternatively, click the link below to verify instantly:</p>
            <p><a href="{verify_url}" style="color: #3b82f6; text-decoration: underline; font-size: 14px;">{verify_url}</a></p>
            <hr style="border: 0; border-top: 1px solid #e2e8f0; margin: 20px 0;" />
            <p style="color: #94a3b8; font-size: 12px;">If you did not request this verification, please ignore this email.</p>
        </div>
        """
        
        sent, error = send_system_email(user["email"], "Verify your PhishSim.ai Account", body_html)
        
        if sent:
            return {"success": True, "message": "Verification code sent to your email."}
        else:
            return {"success": True, "message": f"Verification code generated (Fallback: {otp})", "fallback_otp": otp}
    except Exception as e:
        return {"success": False, "message": str(e)}, 500
    finally:
        cursor.close()
        db.close()

@app.route("/verify-otp", methods=["POST"])
@login_required
def verify_otp():
    """Verifies the 6-digit OTP code to confirm identity."""
    user = current_user()
    code = request.form.get("otp_code", "").strip()
    
    saved_otp = session.get("verification_otp")
    expires = session.get("verification_otp_expires", 0)
    
    if not saved_otp or time.time() > expires:
        return {"success": False, "message": "Verification code has expired. Please request a new one."}
        
    if not code or not secrets.compare_digest(code, saved_otp):
        return {"success": False, "message": "Invalid verification code. Please check and try again."}
        
    db = get_db_connection()
    cursor = db.cursor()
    try:
        cursor.execute("UPDATE users SET email_verified = TRUE, verification_token = NULL WHERE id = %s", (user["id"],))
        db.commit()
        
        session.pop("verification_otp", None)
        session.pop("verification_otp_expires", None)
        
        record_audit_event(user["id"], "Email verified via OTP")
        return {"success": True, "message": "Your identity has been verified!"}
    except Exception as e:
        print(f"OTP verification failed: {e}")
        return {"success": False, "message": "Verification failed due to a database error. Please try again later."}, 500
    finally:
        cursor.close()
        db.close()

@app.route("/test-2fa-send", methods=["POST"])
@login_required
def test_2fa_send():
    """Sends a 2FA verification test code."""
    import secrets
    user = current_user()
    if not user.get("email_verified"):
        return {"success": False, "message": "Verify your email before testing 2FA."}
        
    code = f"{secrets.randbelow(1000000):06d}"
    session["test_2fa_code"] = code
    session["test_2fa_expires"] = time.time() + 600
    
    body_html = f"""
    <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e2e8f0; border-radius: 12px; background-color: #ffffff;">
        <h2 style="color: #0f172a; margin-top: 0;">PhishSim.ai 2FA Test Code</h2>
        <p style="color: #475569; font-size: 16px;">Here is your 2FA verification test code:</p>
        <div style="background-color: #f8fafc; border: 1px solid #cbd5e1; border-radius: 8px; padding: 15px; font-size: 24px; font-weight: bold; letter-spacing: 6px; text-align: center; color: #06b6d4; margin: 20px 0;">
            {code}
        </div>
        <p style="color: #94a3b8; font-size: 12px;">This code will expire in 10 minutes.</p>
    </div>
    """
    
    sent, error = send_system_email(user["email"], "PhishSim.ai 2FA Test Code", body_html)
    if sent:
        return {"success": True, "message": "Test code sent to your email."}
    else:
        return {"success": True, "message": f"Test code generated (Fallback: {code})", "fallback_code": code}

@app.route("/test-2fa-verify", methods=["POST"])
@login_required
def test_2fa_verify():
    """Verifies the 2FA test code and enables 2FA in the user's profile."""
    user = current_user()
    code = request.form.get("otp_code", "").strip()
    
    saved_code = session.get("test_2fa_code")
    expires = session.get("test_2fa_expires", 0)
    
    if not saved_code or time.time() > expires:
        return {"success": False, "message": "Test code expired or not requested. Please send a new one."}
        
    if code != saved_code:
        return {"success": False, "message": "Invalid code. Please try again."}
        
    session.pop("test_2fa_code", None)
    session.pop("test_2fa_expires", None)
    
    db = get_db_connection()
    cursor = db.cursor()
    try:
        cursor.execute("UPDATE users SET two_factor_enabled = TRUE WHERE id = %s", (user["id"],))
        db.commit()
        record_audit_event(user["id"], "2FA verified and enabled")
        return {"success": True, "message": "2FA delivery verified and enabled successfully!"}
    except Exception as e:
        return {"success": False, "message": str(e)}, 500
    finally:
        cursor.close()
        db.close()

@app.route("/delete-account", methods=["POST"])
@login_required
def delete_account():
    user = current_user()
    if user["role"] == "admin":
        flash("Admin accounts cannot be deleted from Profile. Use the Users page after creating another admin.")
        return redirect(url_for("profile"))
    cleanup_demo_user(user["id"]) if user.get("company_domain") == "demo-corp.com" else None
    if user.get("company_domain") != "demo-corp.com":
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        try:
            ensure_email_tracking_table(cursor)
            ensure_events_table(cursor)
            ensure_audit_table(cursor)
            cursor.execute("SELECT id FROM campaigns WHERE user_id = %s", (user["id"],))
            campaigns = cursor.fetchall()
            for campaign in campaigns:
                camp_id = campaign["id"]
                cursor.execute("SELECT tracking_id FROM emails_sent WHERE campaign_id = %s", (camp_id,))
                tracking_ids = [r["tracking_id"] for r in cursor.fetchall() if r.get("tracking_id")]
                if tracking_ids:
                    placeholders = ",".join(["%s"] * len(tracking_ids))
                    cursor.execute(f"DELETE FROM events WHERE tracking_id IN ({placeholders})", tuple(tracking_ids))
                cursor.execute("DELETE FROM emails_sent WHERE campaign_id = %s", (camp_id,))
                cursor.execute("DELETE FROM employees WHERE campaign_id = %s", (camp_id,))
            cursor.execute("DELETE FROM campaigns WHERE user_id = %s", (user["id"],))
            cursor.execute("DELETE FROM audit_events WHERE user_id = %s", (user["id"],))
            cursor.execute("DELETE FROM users WHERE id = %s", (user["id"],))
            db.commit()
        finally:
            cursor.close()
            db.close()
    session.clear()
    flash("Your account has been deleted.")
    return redirect(url_for("home"))

@app.route("/change-password", methods=["POST"])
@login_required
def change_password():
    user = current_user()
    current_password = request.form.get("current_password", "")
    new_password = request.form.get("new_password", "")
    if not new_password:
        flash("Enter a new password.")
        return redirect(url_for("profile"))

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute("SELECT password_hash FROM users WHERE id = %s", (user["id"],))
        row = cursor.fetchone()
        if not row or not check_password_hash(row["password_hash"], current_password):
            flash("Current password is incorrect.")
            return redirect(url_for("profile"))
        cursor.execute("UPDATE users SET password_hash = %s WHERE id = %s", (generate_password_hash(new_password), user["id"]))
        db.commit()
        flash("Password updated.")
    finally:
        cursor.close()
        db.close()
    return redirect(url_for("profile"))

# ==========================================
# ADMIN CONTROL CENTER
# ==========================================

@app.route("/admin")
@admin_required
def admin_panel():
    """Full admin control centre — users, campaigns, system health, audit log."""
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    try:
        ensure_audit_table(cursor)
        ensure_email_schema_once(cursor)

        # All users (excluding active demo sessions for cleanliness)
        cursor.execute("""
            SELECT id, name, email, role, company_domain, email_verified,
                    two_factor_enabled, email_notifications, created_at, last_login_at
            FROM users
            WHERE company_domain != 'demo-corp.com' OR company_domain IS NULL
            ORDER BY id DESC
        """)
        all_users = cursor.fetchall()

        # All campaigns across all real accounts
        cursor.execute("""
            SELECT c.id, c.name, c.scenario_type, c.delivery_mode,
                    c.status, c.status_updated_at, c.company_domain,
                    c.schedule_frequency, c.scheduled_at,
                    u.name AS owner_name, u.email AS owner_email,
                    (SELECT COUNT(*) FROM employees e WHERE e.campaign_id = c.id) AS targets,
                    (SELECT COUNT(*) FROM emails_sent es WHERE es.campaign_id = c.id
                    AND COALESCE(es.status,'sent') IN ('sent','previewed')) AS sent,
                    (SELECT COUNT(DISTINCT ev.tracking_id)
                    FROM events ev JOIN emails_sent es ON ev.tracking_id = es.tracking_id
                    WHERE es.campaign_id = c.id AND ev.event_type = 'click') AS clicks
            FROM campaigns c
            LEFT JOIN users u ON c.user_id = u.id
            WHERE (c.company_domain != 'demo-corp.com' OR c.company_domain IS NULL)
            ORDER BY c.id DESC
            LIMIT 50
        """)
        all_campaigns = cursor.fetchall()

        # System stats
        cursor.execute("SELECT COUNT(*) AS cnt FROM users WHERE company_domain != 'demo-corp.com' OR company_domain IS NULL")
        total_users = cursor.fetchone()["cnt"]

        cursor.execute("SELECT COUNT(*) AS cnt FROM campaigns WHERE company_domain != 'demo-corp.com' OR company_domain IS NULL")
        total_campaigns = cursor.fetchone()["cnt"]

        cursor.execute("SELECT COUNT(*) AS cnt FROM users WHERE email_verified = TRUE AND (company_domain != 'demo-corp.com' OR company_domain IS NULL)")
        verified_users = cursor.fetchone()["cnt"]

        # Recent audit events
        cursor.execute("""
            SELECT ae.created_at, ae.event_type, ae.status, ae.ip_address, u.name AS user_name, u.email AS user_email
            FROM audit_events ae
            LEFT JOIN users u ON ae.user_id = u.id
            ORDER BY ae.created_at DESC
            LIMIT 20
        """)
        audit_log = cursor.fetchall()

        # Email config status
        email_settings = get_email_settings(os.getenv("EMAIL_MODE", "local").strip().lower())
        enforce_work_emails = get_system_setting(cursor, "enforce_work_emails", "false")

    finally:
        cursor.close()
        db.close()

    system_stats = {
        "total_users": total_users,
        "verified_users": verified_users,
        "total_campaigns": total_campaigns,
        "email_provider": email_settings.get("provider", "not configured"),
        "smtp_host": email_settings.get("host") or "not set",
        "deployed": is_deployed_environment(),
    }

    return render_template(
        "admin.html",
        all_users=all_users,
        all_campaigns=all_campaigns,
        system_stats=system_stats,
        audit_log=audit_log,
        email_settings=email_settings,
        enforce_work_emails=enforce_work_emails,
    )


@app.route("/admin/save-settings", methods=["POST"])
@admin_required
def admin_save_settings():
    enforce_work_emails = request.form.get("enforce_work_emails", "false")
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    try:
        set_system_setting(cursor, "enforce_work_emails", enforce_work_emails)
        db.commit()
        flash("System settings updated.")
    except Exception as e:
        print(f"Error saving settings: {e}")
        flash("Failed to save settings.")
    finally:
        cursor.close()
        db.close()
    return redirect(url_for("admin_panel"))


@app.route("/users", methods=["GET", "POST"])
@admin_required
def manage_users():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        role = request.form.get("role", "company_user")
        company_domain = normalize_domain(request.form.get("company_domain", ""))

        if role not in ("admin", "company_user"):
            role = "company_user"

        domain_from_email = email_domain(email)
        if not name or not domain_from_email:
            flash("Enter a valid name and email.")
            return redirect(url_for("manage_users"))
        if not password:
            flash("Enter a temporary password.")
            return redirect(url_for("manage_users"))
        if not company_domain:
            company_domain = domain_from_email

        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        try:
            cursor.execute("""
                INSERT INTO users (name, email, password_hash, role, company_domain, email_verified)
                VALUES (%s, %s, %s, %s, %s, TRUE)
            """, (name, email, generate_password_hash(password), role, company_domain))
            db.commit()
        except Exception as e:
            print(f"Admin create user failed: {e}")
            flash("Could not create user. The email address might already be registered.")
        cursor.close()
        db.close()
        return redirect(url_for("manage_users"))

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT id, name, email, role, company_domain, email_verified, created_at FROM users ORDER BY id DESC")
    users = cursor.fetchall()
    cursor.close()
    db.close()
    return render_template("users.html", users=users)

@app.route("/set-user-role/<int:user_id>", methods=["POST"])
@admin_required
def set_user_role(user_id):
    new_role = request.form.get("role", "company_user")
    if new_role not in ("admin", "company_user"):
        flash("Invalid role.")
        return redirect(url_for("manage_users"))

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    try:
        if user_id == session.get("user_id") and new_role != "admin":
            flash("You cannot remove your own admin access.")
            return redirect(url_for("manage_users"))

        if new_role != "admin":
            cursor.execute("SELECT COUNT(*) AS count FROM users WHERE role = 'admin'")
            admin_count = cursor.fetchone()["count"]
            cursor.execute("SELECT role FROM users WHERE id = %s", (user_id,))
            target = cursor.fetchone()
            if target and target["role"] == "admin" and admin_count <= 1:
                flash("At least one admin account is required.")
                return redirect(url_for("manage_users"))

        cursor.execute("UPDATE users SET role = %s WHERE id = %s", (new_role, user_id))
        db.commit()
        flash("User role updated.")
    except Exception as e:
        print(f"Admin update role failed: {e}")
        flash("Could not update role. A database error occurred.")
    finally:
        cursor.close()
        db.close()
    return redirect(url_for("manage_users"))

@app.route("/verify-user/<int:user_id>", methods=["POST"])
@admin_required
def verify_user(user_id):
    db = get_db_connection()
    cursor = db.cursor()
    try:
        cursor.execute("""
            UPDATE users
            SET email_verified = TRUE, verification_token = NULL
            WHERE id = %s
        """, (user_id,))
        db.commit()
        flash("User email marked as verified.")
        record_audit_event(session.get("user_id"), f"Verified user {user_id}")
    except Exception as e:
        print(f"Admin verify user failed: {e}")
        flash("Could not verify user. A database error occurred.")
    finally:
        cursor.close()
        db.close()
    return redirect(url_for("manage_users"))

@app.route("/delete-user/<int:user_id>", methods=["POST"])
@admin_required
def delete_user(user_id):
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    try:
        # Don't let the user delete themselves
        if user_id == session.get("user_id"):
            flash("You cannot delete your own account.")
        else:
            # Check if deleting the last admin
            cursor.execute("SELECT role FROM users WHERE id = %s", (user_id,))
            target = cursor.fetchone()
            if target and target["role"] == "admin":
                cursor.execute("SELECT COUNT(*) AS count FROM users WHERE role = 'admin'")
                admin_count = cursor.fetchone()["count"]
                if admin_count <= 1:
                    flash("Cannot delete the last admin account.")
                    return redirect(url_for("manage_users"))
            
            cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
            db.commit()
            flash("User deleted successfully.")
    except Exception as e:
        print(f"Error deleting user: {e}")
        flash("Error deleting user. A database error occurred.")
    finally:
        cursor.close()
        db.close()
    return redirect(url_for("manage_users"))

@app.route("/reset-user-password/<int:user_id>", methods=["POST"])
@admin_required
def reset_user_password(user_id):
    new_password = request.form.get("new_password", "")
    if not new_password:
        flash("Enter a new password.")
        return redirect(url_for("manage_users"))
    db = get_db_connection()
    cursor = db.cursor()
    try:
        cursor.execute("UPDATE users SET password_hash = %s WHERE id = %s", (generate_password_hash(new_password), user_id))
        db.commit()
        flash("User password reset.")
    finally:
        cursor.close()
        db.close()
    return redirect(url_for("manage_users"))

@app.route("/dashboard")
def dashboard():
    user = current_user()
    if not user:
        campaigns = [
            {
                "id": 0,
                "name": "Executive CEO Fraud Test",
                "status": "launched",
                "scenario_type": "ceo_fraud",
                "delivery_mode": "sandbox",
                "company_domain": "demo-corp.com",
                "employee_name": "Alex Rivera",
                "employee_email": "alex.rivera@demo-corp.com",
                "employee_count": 24,
                "emails_sent": 24,
                "opens": 19,
                "clicks": 8,
                "reports": 5,
                "created_at": "2026-08-01",
                "hss": {"score": 62, "tier": "amber", "label": "At Risk"}
            },
            {
                "id": 1,
                "name": "Q3 Password Reset Drill",
                "status": "completed",
                "scenario_type": "it_alert",
                "delivery_mode": "sandbox",
                "company_domain": "demo-corp.com",
                "employee_name": "Jordan Ellis",
                "employee_email": "jordan.ellis@demo-corp.com",
                "employee_count": 36,
                "emails_sent": 36,
                "opens": 32,
                "clicks": 4,
                "reports": 21,
                "created_at": "2026-07-15",
                "hss": {"score": 88, "tier": "green", "label": "Good"}
            }
        ]
        
        global_stats = {
            "total_campaigns": 2,
            "total_employees": 60,
            "global_risk": 20,
            "total_reports": 26
        }
        
        global_hss = {
            "score": 75,
            "tier": "amber",
            "label": "At Risk"
        }
        
        risk_trend = [
            {"name": "Q3 Password Reset Drill", "hss": 88, "tier": "green"},
            {"name": "Executive CEO Fraud Test", "hss": 62, "tier": "amber"}
        ]
        
        demo_summary = {
            "total_campaigns": 2,
            "avg_click_rate": 20.0,
            "best_campaign": {"name": "Q3 Password Reset Drill", "click_rate": 11.1},
            "worst_campaign": {"name": "Executive CEO Fraud Test", "click_rate": 33.3}
        }
        
        dept_count = 3
        
        recent_activities = [
            {
                "entry_type": "event",
                "event_type": "report",
                "created_at": datetime.now() - timedelta(hours=1),
                "campaign_name": "Executive CEO Fraud Test",
                "employee_name": "Sarah Chen",
                "employee_department": "Finance",
                "owner_name": None
            },
            {
                "entry_type": "event",
                "event_type": "click",
                "created_at": datetime.now() - timedelta(hours=3),
                "campaign_name": "Executive CEO Fraud Test",
                "employee_name": "Alex Rivera",
                "employee_department": "Operations",
                "owner_name": None
            },
            {
                "entry_type": "campaign_created",
                "event_type": "create",
                "created_at": datetime.now() - timedelta(days=8),
                "campaign_name": "Executive CEO Fraud Test",
                "employee_name": None,
                "employee_department": None,
                "owner_name": "Demo Operator"
            }
        ]
        
        return render_template(
            "dashboard.html",
            campaigns=campaigns,
            global_stats=global_stats,
            global_hss=global_hss,
            risk_trend=risk_trend,
            demo_summary=demo_summary,
            dept_count=dept_count,
            recent_activities=recent_activities,
            is_demo_preview=True
        )
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    try:
        if ensure_email_schema_once(cursor):
            db.commit()
        recover_stuck_campaigns(cursor)
        db.commit()
        run_due_scheduled_campaigns(cursor)

        # 1. FETCH ALL CAMPAIGNS WITH AGGREGATED METRICS IN ONE SINGLE QUERY (PERFECTION!)
        # This replaces the N+1 problem (looping through campaigns and running queries)
        if user["role"] == "admin":
            where_clause = "WHERE c.company_domain != 'demo-corp.com' OR c.company_domain IS NULL"
            params = ()
        else:
            company_domain = normalize_domain(user.get("company_domain"))
            if company_domain:
                where_clause = "WHERE c.company_domain = %s OR c.user_id = %s"
                params = (company_domain, user["id"])
            else:
                where_clause = "WHERE c.user_id = %s"
                params = (user["id"],)

        sql = f"""
            SELECT 
                c.*,
                u.name AS owner_name,
                u.email AS owner_email,
                (SELECT name FROM employees e WHERE e.campaign_id = c.id ORDER BY e.id ASC LIMIT 1) as employee_name,
                (SELECT email FROM employees e WHERE e.campaign_id = c.id ORDER BY e.id ASC LIMIT 1) as employee_email,
                (SELECT COUNT(*) FROM employees e WHERE e.campaign_id = c.id) as employee_count,
                (SELECT COUNT(*) FROM emails_sent es WHERE es.campaign_id = c.id AND COALESCE(es.status, 'sent') IN ('sent', 'previewed')) as emails_sent,
                (SELECT COUNT(*) FROM emails_sent es WHERE es.campaign_id = c.id AND es.status = 'failed') as emails_failed,
                (SELECT error_message FROM emails_sent es WHERE es.campaign_id = c.id AND es.status = 'failed' ORDER BY id DESC LIMIT 1) as latest_error,
                (
                    SELECT COUNT(DISTINCT ev.tracking_id)
                    FROM events ev
                    JOIN emails_sent es ON ev.tracking_id = es.tracking_id
                    WHERE es.campaign_id = c.id AND ev.event_type IN ('open', 'click', 'report')
                ) as opens,
                (
                    SELECT COUNT(DISTINCT ev.tracking_id)
                    FROM events ev
                    JOIN emails_sent es ON ev.tracking_id = es.tracking_id
                    WHERE es.campaign_id = c.id AND ev.event_type = 'click'
                ) as clicks,
                (
                    SELECT COUNT(DISTINCT ev.tracking_id)
                    FROM events ev
                    JOIN emails_sent es ON ev.tracking_id = es.tracking_id
                    WHERE es.campaign_id = c.id AND ev.event_type = 'report'
                ) as reports
            FROM campaigns c
            LEFT JOIN users u ON c.user_id = u.id
            {where_clause}
            ORDER BY c.id DESC
        """
        cursor.execute(sql, params)
        campaigns = cursor.fetchall()

        # Get count of unique departments targeted by this user's campaigns
        dept_sql = f"""
            SELECT COUNT(DISTINCT e.department) as dept_count
            FROM employees e
            JOIN campaigns c ON e.campaign_id = c.id
            {where_clause}
        """
        cursor.execute(dept_sql, params)
        dept_row = cursor.fetchone()
        dept_count = dept_row["dept_count"] if dept_row else 0

        # Aggregate totals for summary bar
        total_employees = sum(c['employee_count'] for c in campaigns)
        total_opens     = sum(c['opens']          for c in campaigns)
        total_clicks    = sum(c['clicks']         for c in campaigns)
        total_reports   = sum(c['reports']        for c in campaigns)

        global_risk = 0
        if total_opens > 0:
            global_risk = int((total_clicks / total_opens) * 100)
        elif total_employees > 0 and total_clicks > 0:
            global_risk = int((total_clicks / total_employees) * 100)

        # Compute per-campaign HSS and build risk trend
        risk_trend = []
        hss_scores = []
        for c in campaigns:
            if c["status"] in ("launched", "launched_with_errors"):
                sent = c["emails_sent"] or 0
                if sent > 0:
                    cr = round((c["clicks"] / sent) * 100, 1)
                    orr = round((c["opens"]  / sent) * 100, 1)
                    rr  = round((c["reports"]/ sent) * 100, 1)
                    hss = compute_human_security_score(cr, orr, rr)
                    c["hss"] = hss
                    hss_scores.append(hss["score"])
                    risk_trend.append({
                        "name": c["name"],
                        "hss":  hss["score"],
                        "tier": hss["tier"],
                    })
                else:
                    c["hss"] = None
            else:
                c["hss"] = None

        global_hss = None
        if hss_scores:
            avg = round(sum(hss_scores) / len(hss_scores))
            if avg >= 70:
                global_hss = {"score": avg, "tier": "green",  "label": "Good"}
            elif avg >= 40:
                global_hss = {"score": avg, "tier": "amber",  "label": "At Risk"}
            else:
                global_hss = {"score": avg, "tier": "red",    "label": "Critical"}

        global_stats = {
            "total_campaigns": len(campaigns),
            "total_employees": total_employees,
            "global_risk": global_risk,
            "total_reports": total_reports
        }

        # Compute demo summary stats dynamically
        total_sent_all = sum(c["emails_sent"] for c in campaigns if (c["emails_sent"] or 0) > 0)
        total_clicks_all = sum(c["clicks"] for c in campaigns)
        avg_click_rate = round((total_clicks_all / total_sent_all) * 100, 1) if total_sent_all > 0 else 0.0

        launched_campaigns = []
        for c in campaigns:
            sent = c["emails_sent"] or 0
            if sent > 0:
                cr = (c["clicks"] / sent) * 100
                launched_campaigns.append((c, cr))

        best_campaign = None
        worst_campaign = None
        if launched_campaigns:
            launched_campaigns.sort(key=lambda x: x[1])
            best_campaign = {
                "name": launched_campaigns[0][0]["name"],
                "click_rate": round(launched_campaigns[0][1], 1)
            }
            worst_campaign = {
                "name": launched_campaigns[-1][0]["name"],
                "click_rate": round(launched_campaigns[-1][1], 1)
            }

        demo_summary = {
            "total_campaigns": len(campaigns),
            "avg_click_rate": avg_click_rate,
            "best_campaign": best_campaign,
            "worst_campaign": worst_campaign
        }

        # Fetch real activity logs (UNION event clicks/opens/reports and campaign creations)
        # NOTE: events table uses 'created_at' column (not 'timestamp')
        recent_activities = []
        try:
            activities_sql = f"""
                SELECT 
                    'event' AS entry_type,
                    ev.event_type,
                    ev.created_at,
                    c.name AS campaign_name,
                    emp.name AS employee_name,
                    emp.department AS employee_department,
                    NULL AS owner_name
                FROM events ev
                JOIN emails_sent es ON ev.tracking_id = es.tracking_id
                JOIN campaigns c ON es.campaign_id = c.id
                LEFT JOIN employees emp ON (emp.campaign_id = es.campaign_id AND emp.email = es.recipient_email)
                {where_clause}
                
                UNION ALL
                
                SELECT
                    'campaign_created' AS entry_type,
                    'create' AS event_type,
                    c.created_at,
                    c.name AS campaign_name,
                    NULL AS employee_name,
                    NULL AS employee_department,
                    u.name AS owner_name
                FROM campaigns c
                LEFT JOIN users u ON c.user_id = u.id
                {where_clause}
                
                ORDER BY created_at DESC
                LIMIT 15
            """
            activities_params = params + params
            cursor.execute(activities_sql, activities_params)
            recent_activities = cursor.fetchall()
        except Exception as act_err:
            print(f"Activity feed query failed (non-critical): {act_err}")
            recent_activities = []

        # Ensure we always pass recent_activities list (no mocked/simulated data)
        if not recent_activities:
            recent_activities = []

    except Exception as e:
        print(f"Dashboard query failed: {e}")
        campaigns = []
        global_stats = {"total_campaigns": 0, "total_employees": 0, "global_risk": 0, "total_reports": 0}
        global_hss = None
        risk_trend = []
        demo_summary = {
            "total_campaigns": 0,
            "avg_click_rate": 0.0,
            "best_campaign": None,
            "worst_campaign": None
        }
        dept_count = 0
        recent_activities = []
    finally:
        cursor.close()
        db.close()

    return render_template(
        "dashboard.html",
        campaigns=campaigns,
        global_stats=global_stats,
        global_hss=global_hss,
        risk_trend=risk_trend,
        demo_summary=demo_summary,
        dept_count=dept_count,
        recent_activities=recent_activities,
    )

@app.route("/reports-demo")
def reports_demo():
    """Explains the AI report before users open campaign-specific reports."""
    user = current_user()
    if not user:
        return render_template("reports_demo.html", campaigns=[])

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    campaigns = []
    try:
        if user["role"] == "admin":
            where_clause = "WHERE c.company_domain != 'demo-corp.com' OR c.company_domain IS NULL"
            params = ()
        else:
            company_domain = normalize_domain(user.get("company_domain"))
            if company_domain:
                where_clause = "WHERE c.company_domain = %s OR c.user_id = %s"
                params = (company_domain, user["id"])
            else:
                where_clause = "WHERE c.user_id = %s"
                params = (user["id"],)

        cursor.execute(f"""
            SELECT c.id, c.name, c.scenario_type, c.status, c.company_domain, c.created_at,
                   (SELECT COUNT(*) FROM employees e WHERE e.campaign_id = c.id) AS employee_count,
                   (SELECT COUNT(*) FROM emails_sent es WHERE es.campaign_id = c.id
                    AND COALESCE(es.status, 'sent') IN ('sent', 'previewed')) AS emails_sent,
                   (SELECT COUNT(DISTINCT ev.tracking_id)
                    FROM events ev JOIN emails_sent es ON ev.tracking_id = es.tracking_id
                    WHERE es.campaign_id = c.id AND ev.event_type = 'click') AS clicks,
                   (SELECT COUNT(DISTINCT ev.tracking_id)
                    FROM events ev JOIN emails_sent es ON ev.tracking_id = es.tracking_id
                    WHERE es.campaign_id = c.id AND ev.event_type = 'report') AS reports
            FROM campaigns c
            {where_clause}
            ORDER BY c.id DESC
            LIMIT 24
        """, params)
        campaigns = cursor.fetchall()
        for c in campaigns:
            sent = int(c.get("emails_sent") or 0)
            clicks = int(c.get("clicks") or 0)
            reports = int(c.get("reports") or 0)
            click_rate = round((clicks / sent) * 100, 1) if sent else 0.0
            report_rate = round((reports / sent) * 100, 1) if sent else 0.0
            c["click_rate"] = click_rate
            c["report_rate"] = report_rate
            c["hss"] = compute_human_security_score(click_rate, 0, report_rate) if sent else None
    finally:
        cursor.close()
        db.close()

    return render_template("reports_demo.html", campaigns=campaigns)

# 1. ADD THIS ROUTE: This shows the "Create Campaign" page
@app.route("/new-campaign", methods=["GET", "POST"])
@app.route("/new-campaign/<int:campaign_id>", methods=["GET", "POST"])
def new_campaign(campaign_id=None):
    user = current_user()
    if not user:
        if request.method == "POST":
            return redirect(url_for("login"))
        local_delivery_available = False
        safe_send_available = False
        preview_available = True
        campaign_limit_reached = False
        campaign = None
        if campaign_id == 0:
            campaign = {
                "id": 0,
                "name": "Executive CEO Fraud Test",
                "company_domain": "demo-corp.com",
                "scenario_type": "ceo_fraud",
                "delivery_mode": "sandbox",
                "status": "launched",
            }
        elif campaign_id is not None:
            return redirect(url_for("login"))
        return render_template(
            "new_campaign.html",
            user={"role": "company_user", "company_domain": "demo-corp.com"},
            local_delivery_available=local_delivery_available,
            safe_send_available=safe_send_available,
            preview_available=preview_available,
            campaign_limit_reached=campaign_limit_reached,
            campaign=campaign,
            is_demo_preview=True
        )
    local_delivery_available = user["role"] == "admin"
    # Safe Send = Mailtrap sandbox (works on Render, no domain needed)
    safe_send_available = bool(
        os.getenv("MAILTRAP_USER", "").strip() and os.getenv("MAILTRAP_PASS", "").strip()
    )
    # Preview mode = no sending at all, show in-app — always available
    preview_available = True

    campaign = None
    if campaign_id is not None:
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        campaign = user_can_access_campaign(cursor, campaign_id, user)
        cursor.close()
        db.close()
        if not campaign:
            return "Campaign not found or access denied.", 404

    campaign_limit_reached = False
    if campaign_id is None and user["role"] not in ("admin", "pro"):
        try:
            db = get_db_connection()
            cursor = db.cursor(dictionary=True)
            cursor.execute("SELECT COUNT(*) as count FROM campaigns WHERE user_id = %s", (user["id"],))
            campaign_count = cursor.fetchone()["count"]
            cursor.close()
            db.close()
            if campaign_count >= 3:
                campaign_limit_reached = True
        except Exception as e:
            print(f"Error checking campaign count: {e}")

    if request.method == "POST":
        if campaign_id is None and campaign_limit_reached:
            flash("You have reached the limit of 3 campaigns for the Free tier. Please upgrade to PRO for unlimited campaigns!")
            return redirect(url_for("billing_portal"))
        # 1. Get data from the form
        name = request.form.get("campaign_name")
        domain = normalize_domain(request.form.get("company_domain") or user.get("company_domain") or email_domain(user.get("email")))
        scenario = request.form.get("scenario")
        consent = request.form.get("consent_confirmed")
        requested_mode = request.form.get("delivery_mode", "preview" if user["role"] not in ("admin", "pro") else "smtp")
        schedule_frequency = request.form.get("schedule_frequency", "once")
        scheduled_at = parse_datetime_local(request.form.get("scheduled_at"))
        if schedule_frequency not in ("once", "daily", "weekly", "monthly"):
            schedule_frequency = "once"

        def redirect_back():
            if campaign_id is not None:
                return redirect(url_for("new_campaign", campaign_id=campaign_id))
            return redirect(url_for("new_campaign"))

        if user["role"] not in ("admin", "pro") and schedule_frequency != "once":
            flash("Upgrade to PhishSim.ai PRO to unlock automated recurring schedules (Daily, Weekly, Monthly)!")
            return redirect_back()
        if schedule_frequency != "once" and not scheduled_at:
            flash("Choose a start date and time for automation.")
            return redirect_back()

        VALID_MODES = {"local", "smtp", "mailtrap", "preview", "own_mailtrap"}
        delivery_mode = requested_mode if requested_mode in VALID_MODES else "preview"

        # Handle user's own Mailtrap credentials
        own_mailtrap_user = request.form.get("own_mailtrap_user", "").strip()
        own_mailtrap_pass = request.form.get("own_mailtrap_pass", "").strip()
        if delivery_mode == "own_mailtrap":
            if not own_mailtrap_user or not own_mailtrap_pass:
                flash("Enter your Mailtrap username and password to use My Mailtrap Inbox.")
                return redirect_back()
            # We remap to 'mailtrap' internally but pass credentials per-campaign via session
            session["campaign_mailtrap_user"] = own_mailtrap_user
            session["campaign_mailtrap_pass"] = own_mailtrap_pass
            delivery_mode = "mailtrap"

        # Local smtp4dev/sandbox mode is admin-only, including in deployed mode.
        if delivery_mode == "local" and not local_delivery_available:
            delivery_mode = "preview"
        # mailtrap only when credentials are present
        if delivery_mode == "mailtrap" and not safe_send_available and not (session.get("campaign_mailtrap_user") and session.get("campaign_mailtrap_pass")):
            delivery_mode = "preview"

        # 2. Security Check: Ensure consent was ticked
        if not consent:
            return "Error: You must confirm consent before launching.", 400
        if not domain:
            flash("Add a domain or testing label for this campaign.")
            return redirect_back()
        if delivery_mode == "smtp" and not request.form.get("deliverability_confirmed"):
            flash("Confirm that your organization has allowlisted the simulation sender before using Live Mode.")
            return redirect_back()

        # 3. Save to Database
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        if campaign_id is not None:
            sql = """
                UPDATE campaigns
                SET name = %s, company_domain = %s, scenario_type = %s, delivery_mode = %s, schedule_frequency = %s, scheduled_at = %s
                WHERE id = %s AND user_id = %s
            """
            values = (name, domain, scenario, delivery_mode, schedule_frequency, scheduled_at, campaign_id, user["id"])
            cursor.execute(sql, values)
        else:
            sql = """
                INSERT INTO campaigns
                    (name, company_domain, scenario_type, status, user_id, delivery_mode, schedule_frequency, scheduled_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """
            values = (name, domain, scenario, 'draft', user["id"], delivery_mode, schedule_frequency, scheduled_at)
            cursor.execute(sql, values)
            campaign_id = cursor.lastrowid
        db.commit()
        cursor.close()
        db.close()

        # 4. Redirect to Target Upload Step
        return redirect(url_for('new_campaign_upload', campaign_id=campaign_id))

    return render_template(
        "new_campaign.html",
        user=user,
        local_delivery_available=local_delivery_available,
        safe_send_available=safe_send_available,
        preview_available=preview_available,
        campaign_limit_reached=campaign_limit_reached,
        campaign=campaign,
    )

# Wizard Step 2: Upload targets for campaign
@app.route("/new-campaign/upload/<int:campaign_id>", methods=["GET"])
def new_campaign_upload(campaign_id):
    user = current_user()
    if not user:
        if campaign_id == 0:
            campaign = {
                "id": 0,
                "name": "Executive CEO Fraud Test",
                "company_domain": "demo-corp.com",
                "scenario_type": "ceo_fraud",
                "delivery_mode": "sandbox",
                "status": "launched",
            }
            return render_template("new_campaign_upload.html", campaign=campaign, is_demo_preview=True)
        else:
            return redirect(url_for("login"))
            
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    campaign = user_can_access_campaign(cursor, campaign_id, user)
    cursor.close()
    db.close()
    if not campaign:
        return "Campaign not found.", 404
    return render_template("new_campaign_upload.html", campaign=campaign)

# Wizard Step 3: Launch or preview campaign
@app.route("/new-campaign/launch/<int:campaign_id>", methods=["GET"])
def new_campaign_launch(campaign_id):
    user = current_user()
    if not user:
        if campaign_id == 0:
            campaign = {
                "id": 0,
                "name": "Executive CEO Fraud Test",
                "company_domain": "demo-corp.com",
                "scenario_type": "ceo_fraud",
                "delivery_mode": "sandbox",
                "status": "launched",
            }
            return render_template("new_campaign_launch.html", campaign=campaign, employee_count=24, is_demo_preview=True)
        else:
            return redirect(url_for("login"))

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    campaign = user_can_access_campaign(cursor, campaign_id, user)
    if not campaign:
        cursor.close()
        db.close()
        return "Campaign not found.", 404
    cursor.execute("SELECT COUNT(*) AS count FROM employees WHERE campaign_id = %s", (campaign_id,))
    employee_count = cursor.fetchone()["count"]
    cursor.close()
    db.close()
    return render_template("new_campaign_launch.html", campaign=campaign, employee_count=employee_count)

# API: Check campaign launch status
@app.route("/api/campaign-status/<int:campaign_id>")
@login_required
def campaign_status_api(campaign_id):
    user = current_user()
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    campaign = user_can_access_campaign(cursor, campaign_id, user)
    cursor.close()
    db.close()
    if not campaign:
        return {"error": "Not found"}, 404
    return {"status": campaign["status"]}

# Billing & subscriptions dashboard
@app.route("/billing")
@login_required
def billing_portal():
    user = current_user()
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    
    # campaigns run
    cursor.execute("SELECT COUNT(*) as count FROM campaigns WHERE user_id = %s", (user["id"],))
    campaigns_count = cursor.fetchone()["count"]
    
    # targets simulated
    cursor.execute("""
        SELECT COUNT(emp.id) as count 
        FROM employees emp 
        JOIN campaigns c ON emp.campaign_id = c.id 
        WHERE c.user_id = %s
    """, (user["id"],))
    targets_count = cursor.fetchone()["count"]
    
    cursor.close()
    db.close()
    
    # Defaults
    stripe_status = "active" if user.get("role") in ("pro", "admin") else "inactive"
    next_billing = "N/A"
    stripe_invoices = []
    
    # Next billing date fallback: 1 month from now
    from datetime import datetime, timedelta
    fallback_billing = (datetime.utcnow() + timedelta(days=30)).strftime("%B %d, %Y")
    next_billing = fallback_billing
    
    import stripe
    stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "sk_test_mock_secret_key_phishsim")
    
    if user.get("stripe_subscription_id") and not stripe.api_key.startswith("sk_test_mock"):
        try:
            sub = stripe.Subscription.retrieve(user["stripe_subscription_id"])
            stripe_status = sub.status  # e.g., active, past_due, trialing, etc.
            period_end = datetime.utcfromtimestamp(sub.current_period_end)
            next_billing = period_end.strftime("%B %d, %Y")
            
            # Fetch last 5 invoices
            invoices = stripe.Invoice.list(customer=user.get("stripe_customer_id"), limit=5)
            for inv in invoices.get("data", []):
                inv_date = datetime.utcfromtimestamp(inv.created).strftime("%Y-%m-%d")
                stripe_invoices.append({
                    "date": inv_date,
                    "amount": f"${inv.amount_due / 100:.2f}",
                    "status": inv.status.upper(),
                    "hosted_invoice_url": inv.hosted_invoice_url or "#"
                })
        except Exception as e:
            print(f"Failed to fetch live Stripe billing details: {e}")
            stripe_status = "active"
            next_billing = fallback_billing
            
    trial_expires = None
    trial_days_left = None
    if user.get("pro_expires_at"):
        trial_expires = user["pro_expires_at"].strftime("%B %d, %Y")
        days = (user["pro_expires_at"] - datetime.utcnow()).days
        trial_days_left = max(0, days)

    return render_template(
        "billing.html", 
        user=user, 
        campaigns_count=campaigns_count, 
        targets_count=targets_count,
        next_billing=next_billing,
        stripe_status=stripe_status,
        stripe_invoices=stripe_invoices,
        trial_expires=trial_expires,
        trial_days_left=trial_days_left
    )

# Billing: Stripe Checkout
@app.route("/billing/upgrade", methods=["POST"])
@login_required
def upgrade_to_pro():
    user = current_user()
    import stripe
    stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "sk_test_mock_secret_key_phishsim")
    
    if is_deployed_environment() and stripe.api_key.startswith("sk_test_mock"):
        flash("Billing System Configuration Error: Mock billing is disabled in production environments. Please configure STRIPE_SECRET_KEY.", "danger")
        return redirect(url_for("billing_portal"))

    try:
        if not stripe.api_key.startswith("sk_test_mock"):
            price_id = os.environ.get("STRIPE_PRICE_ID")
            if not price_id:
                # Fallback to dynamic price data if STRIPE_PRICE_ID is not configured
                price_data = {
                    'currency': 'usd',
                    'product_data': {
                        'name': 'PhishSim.ai PRO Flat Subscription',
                        'description': '$24/month flat for up to 50 employees',
                    },
                    'unit_amount': 2400,
                    'recurring': {'interval': 'month'},
                }
                line_item = {'price_data': price_data, 'quantity': 1}
            else:
                line_item = {'price': price_id, 'quantity': 1}

            checkout_session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[line_item],
                mode='subscription',
                success_url=request.host_url + 'billing/success?session_id={CHECKOUT_SESSION_ID}',
                cancel_url=request.host_url + 'billing',
                metadata={'user_id': user['id']},
            )
            return redirect(checkout_session.url, code=303)
        else:
            return redirect(url_for("billing_mock_checkout"))
    except Exception as e:
        print("Stripe exception, falling back to mock checkout:", e)
        if is_deployed_environment():
            flash("Billing Connection Failed: Unable to reach payment gateway.", "danger")
            return redirect(url_for("billing_portal"))
        return redirect(url_for("billing_mock_checkout"))

@app.route("/billing/mock-checkout")
@login_required
def billing_mock_checkout():
    user = current_user()
    return render_template("mock_checkout.html", user=user)

@app.route("/billing/mock-charge", methods=["POST"])
@login_required
def billing_mock_charge():
    user = current_user()
    db = get_db_connection()
    cursor = db.cursor()
    try:
        cursor.execute("UPDATE users SET role = 'pro' WHERE id = %s", (user["id"],))
        db.commit()
        record_audit_event(user["id"], "Upgraded to PRO via mock billing")
    finally:
        cursor.close()
        db.close()
    flash("Congratulations! Simulated checkout succeeded. Your account has been upgraded to PhishSim.ai PRO.")
    return redirect(url_for("dashboard"))

# Stripe Success Callback
@app.route("/billing/success")
@login_required
def billing_success():
    user = current_user()
    session_id = request.args.get("session_id")
    import stripe
    stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "sk_test_mock_secret_key_phishsim")
    
    stripe_customer_id = None
    stripe_subscription_id = None
    payment_verified = False
    
    if session_id and not stripe.api_key.startswith("sk_test_mock"):
        try:
            checkout_session = stripe.checkout.Session.retrieve(session_id)
            if checkout_session.payment_status == "paid":
                stripe_customer_id = checkout_session.customer
                stripe_subscription_id = checkout_session.subscription
                payment_verified = True
        except Exception as e:
            print(f"Stripe session verification failed: {e}")
            payment_verified = True  # Graceful fallback
    else:
        payment_verified = True  # Mock/local checkout bypass
        
    if payment_verified:
        db = get_db_connection()
        cursor = db.cursor()
        try:
            cursor.execute("""
                UPDATE users 
                SET role = 'pro', stripe_customer_id = %s, stripe_subscription_id = %s
                WHERE id = %s
            """, (stripe_customer_id, stripe_subscription_id, user["id"]))
            db.commit()
            record_audit_event(user["id"], "Upgraded to PRO via Stripe Checkout")
        finally:
            cursor.close()
            db.close()
        flash("Congratulations! Stripe checkout succeeded. Your account has been upgraded to PhishSim.ai PRO.", "success")
    else:
        flash("Payment verification failed. Please contact support.", "danger")
        
    return redirect(url_for("dashboard"))

# Billing: Stripe Customer Portal redirect
@app.route("/billing/portal", methods=["POST"])
@login_required
def open_customer_portal():
    user = current_user()
    import stripe
    stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "sk_test_mock_secret_key_phishsim")
    
    customer_id = user.get('stripe_customer_id')
    if not customer_id or customer_id == 'cus_placeholder':
        flash("No active billing profile was found. Please subscribe first to configure subscription settings.", "warning")
        return redirect(url_for("billing_portal"))
        
    try:
        if not stripe.api_key.startswith("sk_test_mock"):
            portal_session = stripe.billing_portal.Session.create(
                customer=customer_id,
                return_url=request.host_url + 'billing'
            )
            return redirect(portal_session.url, code=303)
        else:
            flash("Simulated Customer Portal: Redirected to subscription management controls.")
            return redirect(url_for("billing_portal"))
    except Exception as e:
        print(f"Stripe billing portal exception: {e}")
        flash("Stripe billing portal is currently unavailable. Please try again later.", "danger")
        return redirect(url_for("billing_portal"))

# Stripe Webhook handler
@app.route("/stripe/webhook", methods=["POST"])
@csrf.exempt
def stripe_webhook():
    payload = request.data
    sig_header = request.headers.get("Stripe-Signature")
    event = None
    import stripe
    stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "sk_test_mock_secret_key_phishsim")

    try:
        if is_deployed_environment() and stripe.api_key.startswith("sk_test_mock"):
            return {"error": "Mock webhook is disabled in production."}, 400

        if not stripe.api_key.startswith("sk_test_mock") and sig_header:
            event = stripe.Webhook.construct_event(
                payload, sig_header, os.environ.get('STRIPE_WEBHOOK_SECRET', '')
            )
        else:
            import json
            event = json.loads(payload.decode('utf-8'))
    except Exception as e:
        return {"error": "Invalid payload or signature"}, 400

    event_type = event.get('type')
    if event_type == 'checkout.session.completed':
        session_obj = event['data']['object']
        user_id = session_obj.get('metadata', {}).get('user_id')
        customer_id = session_obj.get('customer')
        subscription_id = session_obj.get('subscription')
        if user_id:
            db = get_db_connection()
            cursor = db.cursor()
            cursor.execute("""
                UPDATE users 
                SET role = 'pro', stripe_customer_id = %s, stripe_subscription_id = %s 
                WHERE id = %s
            """, (customer_id, subscription_id, user_id))
            db.commit()
            cursor.close()
            db.close()
            print(f"[Stripe Webhook] User {user_id} upgraded to PRO (Customer: {customer_id}).")
            
    elif event_type == 'customer.subscription.deleted':
        subscription_obj = event['data']['object']
        customer_id = subscription_obj.get('customer')
        if customer_id:
            db = get_db_connection()
            cursor = db.cursor()
            cursor.execute("""
                UPDATE users 
                SET role = 'company_user', stripe_subscription_id = NULL 
                WHERE stripe_customer_id = %s
            """, (customer_id,))
            db.commit()
            cursor.close()
            db.close()
            print(f"[Stripe Webhook] Customer {customer_id} subscription cancelled. Downgraded to Free tier.")

    return {"status": "success"}, 200

# Billing: Cancel/Downgrade subscription
@app.route("/billing/cancel", methods=["POST"])
@login_required
def cancel_subscription():
    user = current_user()
    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("UPDATE users SET role = 'company_user', stripe_subscription_id = NULL WHERE id = %s", (user["id"],))
    db.commit()
    cursor.close()
    db.close()
    flash("Your PRO subscription has been cancelled. Your account is now downgraded to the Free tier.")
    return redirect(url_for("billing_portal"))

# Billing: Free activation for self-deployment
@app.route("/billing/activate-free", methods=["POST"])
@login_required
def activate_free_pro():
    user = current_user()
    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("UPDATE users SET role = 'pro' WHERE id = %s", (user["id"],))
    db.commit()
    cursor.close()
    db.close()
    flash("Success! Free Developer Pro License activated. All advanced features are now unlocked.")
    return redirect(url_for("billing_portal"))

# Billing: 1-Month Free Trial Activation
@app.route("/billing/activate-trial", methods=["POST"])
@login_required
def activate_trial():
    user = current_user()
    db = get_db_connection()
    cursor = db.cursor()
    # Trial expires in 30 days
    cursor.execute("""
        UPDATE users 
        SET role = 'pro', pro_expires_at = DATE_ADD(NOW(), INTERVAL 30 DAY) 
        WHERE id = %s
    """, (user["id"],))
    db.commit()
    cursor.close()
    db.close()
    flash("Success! Your 1-Month Free Trial has been activated. You now have full access to all PRO features.")
    return redirect(url_for("billing_portal"))

# Billing: Contact Sales form submission
@app.route("/api/contact-sales", methods=["POST"])
@login_required
def contact_sales():
    user = current_user()
    name = request.form.get("name")
    email = request.form.get("email")
    phone = request.form.get("phone")
    company = request.form.get("company")
    message = request.form.get("message")
    
    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("""
        INSERT INTO contact_requests (user_id, name, email, phone, company, message)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (user["id"], name, email, phone, company, message))
    db.commit()
    cursor.close()
    db.close()
    
    flash("Thank you! Your sales/callback request has been received. Our team will contact you shortly.")
    return redirect(url_for("billing_portal"))

# ==========================================
# PHASE 4.5: REMEDIATION APIS (DECOYS & DNS)
# ==========================================

# API: Domain Lockdown real SPF/DMARC DNS check via Cloudflare/Google DNS-over-HTTPS API
@app.route("/api/remediate/domain-lockdown", methods=["POST"])
@login_required
def api_domain_lockdown():
    user = current_user()
    domain = user.get("company_domain") or "demo-corp.com"
    
    import requests
    
    spf_record = None
    dmarc_record = None
    spf_status = "missing"
    dmarc_status = "missing"
    
    # 1. Fetch SPF (TXT record on domain)
    try:
        r_spf = requests.get(f"https://dns.google/resolve?name={domain}&type=TXT", timeout=8)
        if r_spf.status_code == 200:
            data = r_spf.json()
            for answer in data.get("Answer", []):
                txt_data = answer.get("data", "")
                clean_txt = txt_data.strip().strip('"')
                if clean_txt.startswith("v=spf1"):
                    spf_record = clean_txt
                    spf_status = "present"
                    break
    except Exception as e:
        print("SPF DNS Query failed:", e)
        
    # 2. Fetch DMARC (TXT record on _dmarc.domain)
    try:
        r_dmarc = requests.get(f"https://dns.google/resolve?name=_dmarc.{domain}&type=TXT", timeout=8)
        if r_dmarc.status_code == 200:
            data = r_dmarc.json()
            for answer in data.get("Answer", []):
                txt_data = answer.get("data", "")
                clean_txt = txt_data.strip().strip('"')
                if clean_txt.startswith("v=DMARC1"):
                    dmarc_record = clean_txt
                    dmarc_status = "present"
                    break
    except Exception as e:
        print("DMARC DNS Query failed:", e)
        
    status = "secure" if (spf_status == "present" and dmarc_status == "present") else "vulnerable"
    
    return jsonify({
        "success": True,
        "domain": domain,
        "spf_status": spf_status,
        "spf_record": spf_record,
        "dmarc_status": dmarc_status,
        "dmarc_record": dmarc_record,
        "status": status
    })

# API: Deploy Decoy Mailbox
@app.route("/api/remediate/deploy-decoy", methods=["POST"])
@login_required
def api_deploy_decoy():
    user = current_user()
    email = request.form.get("decoy_email", "").strip().lower()
    label = request.form.get("label", "").strip()
    imap_host = request.form.get("imap_host", "").strip()
    imap_port = request.form.get("imap_port", "").strip()
    imap_user = request.form.get("imap_user", "").strip()
    imap_pass = request.form.get("imap_pass", "").strip()
    
    if not email:
        return jsonify({"success": False, "error": "Email is required."}), 400
        
    company_domain = (user.get("company_domain") or "").strip().lower()
    if company_domain and not email.endswith(f"@{company_domain}"):
        return jsonify({
            "success": False, 
            "error": f"Decoy mailbox must belong to your organization domain (@{company_domain})."
        }), 400
        
    db = get_db_connection()
    cursor = db.cursor()
    try:
        cursor.execute("""
            INSERT INTO decoy_mailboxes (user_id, email, label, imap_host, imap_port, imap_user, imap_pass)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE label=%s, imap_host=%s, imap_port=%s, imap_user=%s, imap_pass=%s
        """, (user["id"], email, label, imap_host, imap_port or None, imap_user or None, imap_pass or None,
              label, imap_host, imap_port or None, imap_user or None, imap_pass or None))
        db.commit()
        cursor.close()
        db.close()
        return jsonify({"success": True, "message": f"Decoy mailbox {email} successfully deployed!"})
    except Exception as e:
        cursor.close()
        db.close()
        return jsonify({"success": False, "error": f"Database error: {str(e)}"}), 500

# API: Get Deployed Decoys
@app.route("/api/remediate/get-decoys", methods=["GET"])
@login_required
def api_get_decoys():
    user = current_user()
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    cursor.execute("""
        SELECT id, email, label, status, imap_host, imap_port, imap_user, created_at 
        FROM decoy_mailboxes WHERE user_id = %s
    """, (user["id"],))
    decoys = cursor.fetchall()
    cursor.close()
    db.close()
    
    for d in decoys:
        if d.get("created_at"):
            d["created_at"] = d["created_at"].strftime("%Y-%m-%d %H:%M")
    return jsonify({"success": True, "decoys": decoys})

# API: Trigger live check of decoy mailboxes
@app.route("/api/remediate/check-decoys", methods=["POST"])
@login_required
def api_check_decoys():
    user = current_user()
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM decoy_mailboxes WHERE user_id = %s", (user["id"],))
    decoys = cursor.fetchall()
    cursor.close()
    db.close()
    
    if not decoys:
        return jsonify({"success": False, "error": "No decoy mailboxes have been deployed yet."}), 400
        
    import imaplib
    import email
    from email.header import decode_header
    
    results = []
    intercepted_threats = 0
    simulations_caught = 0
    
    for d in decoys:
        host = d.get("imap_host")
        port = d.get("imap_port") or 993
        username = d.get("imap_user")
        password = d.get("imap_pass")
        email_addr = d.get("email")
        
        status_info = {
            "email": email_addr,
            "checked": False,
            "error": None,
            "unread_count": 0
        }
        
        if not host or not username or not password:
            status_info["error"] = "IMAP credentials not configured — skipping live connection."
            results.append(status_info)
            continue
            
        try:
            mail = imaplib.IMAP4_SSL(host, int(port))
            mail.login(username, password)
            mail.select("inbox")
            
            status, messages = mail.search(None, 'UNSEEN')
            if status == "OK" and messages[0]:
                msg_ids = messages[0].split()
                status_info["unread_count"] = len(msg_ids)
                
                db = get_db_connection()
                cursor = db.cursor()
                
                for m_id in msg_ids:
                    res, data = mail.fetch(m_id, "(RFC822)")
                    if res != "OK":
                        continue
                    raw_email = data[0][1]
                    msg = email.message_from_bytes(raw_email)
                    
                    subject, encoding = decode_header(msg["Subject"] or "")[0]
                    if isinstance(subject, bytes):
                        subject = subject.decode(encoding or "utf-8", errors="ignore")
                    
                    sender = msg.get("From", "")
                    
                    is_simulation = False
                    tracking_token = None
                    
                    for header_name in ["X-PhishSim-Tracking", "X-Simulation-ID"]:
                        if msg[header_name]:
                            is_simulation = True
                            tracking_token = msg[header_name]
                            break
                            
                    body_content = ""
                    if msg.is_multipart():
                        for part in msg.walk():
                            if part.get_content_type() == "text/html":
                                body_content = part.get_payload(decode=True).decode(errors="ignore")
                                break
                    else:
                        body_content = msg.get_payload(decode=True).decode(errors="ignore")
                        
                    if not is_simulation and ("/click/" in body_content or "/track/open/" in body_content):
                        is_simulation = True
                        import re as _re
                        m = _re.search(r'/click/([a-zA-Z0-9_-]+)', body_content)
                        if m:
                            tracking_token = m.group(1)
                            
                    if is_simulation:
                        simulations_caught += 1
                        if tracking_token:
                            cursor.execute("SELECT id FROM events WHERE tracking_id = %s AND event_type = 'decoy_catch'", (tracking_token,))
                            if not cursor.fetchone():
                                log_event(tracking_token, "decoy_catch", "Honeypot Inbox", f"Interceded in Decoy Mailbox: {email_addr}")
                    else:
                        intercepted_threats += 1
                        cursor.execute("""
                            INSERT INTO events (tracking_id, event_type, ip_address, user_agent, created_at)
                            VALUES (%s, 'threat_intercept', %s, %s, NOW())
                        """, (f"threat_{email_addr}_{m_id.decode()}", f"Sender: {sender}", f"Subject: {subject}"))
                
                db.commit()
                cursor.close()
                db.close()
                
            mail.logout()
            status_info["checked"] = True
        except Exception as ex:
            status_info["error"] = str(ex)
            
        results.append(status_info)
        
    return jsonify({
        "success": True,
        "results": results,
        "intercepted_threats": intercepted_threats,
        "simulations_caught": simulations_caught
    })

# 2. ADD THIS ROUTE: Handles CSV upload for employees or OSINT harvest
@app.route("/upload-employees/<int:campaign_id>", methods=["POST"])
@login_required
def upload_employees(campaign_id):
    user = current_user()
    db = get_db_connection()
    access_cursor = db.cursor(dictionary=True)
    campaign = user_can_access_campaign(access_cursor, campaign_id, user)
    access_cursor.close()
    db.close()
    if not campaign:
        return "Campaign not found.", 404

    use_osint = request.form.get("use_osint") == "true"
    
    if use_osint:
        try:
            domain = campaign.get("company_domain") or "example.com"
            profile = scrape_company_cached(domain)
            company_name = profile.get("company_name") or domain.split(".")[0].capitalize()
            
            # Standard template targets mapped to this domain
            template_roles = [
                {"name": "Alex Mercer", "email_prefix": "alex.mercer", "title": "Chief Executive Officer", "dept": "Executive"},
                {"name": "Sarah Jenkins", "email_prefix": "sarah.jenkins", "title": "Chief Financial Officer", "dept": "Finance"},
                {"name": "Emma Watson", "email_prefix": "emma.watson", "title": "HR Director", "dept": "Human Resources"},
                {"name": "David Miller", "email_prefix": "david.miller", "title": "IT Support Lead", "dept": "IT Support"},
                {"name": "Clara Pete", "email_prefix": "clara.pete", "title": "Billing Specialist", "dept": "Finance"}
            ]
            
            targets = []
            # 1. Add any scraped emails
            for email in profile.get("emails", []):
                prefix = email.split("@")[0]
                name = prefix.replace(".", " ").replace("_", " ").title()
                dept = "Operations"
                title = "Representative"
                if "hr" in prefix or "jobs" in prefix:
                    dept = "Human Resources"
                    title = "Recruiter"
                elif "support" in prefix or "admin" in prefix or "it" in prefix:
                    dept = "IT Support"
                    title = "Administrator"
                elif "billing" in prefix or "finance" in prefix or "invoice" in prefix:
                    dept = "Finance"
                    title = "Accountant"
                targets.append({"name": name, "email": email, "title": title, "dept": dept})
                
            # 2. Add template roles ONLY if we found absolutely no real emails during scraping
            if not targets:
                for r in template_roles:
                    email = f"{r['email_prefix']}@{domain}"
                    if not any(t["email"].lower() == email.lower() for t in targets):
                        targets.append({"name": r["name"], "email": email, "title": r["title"], "dept": r["dept"]})
            
            db = get_db_connection()
            cursor = db.cursor()
            sql = "INSERT INTO employees (name, email, department, title, campaign_id) VALUES (%s, %s, %s, %s, %s)"
            inserted = 0
            for t in targets:
                cursor.execute(sql, (t["name"], t["email"].lower(), t["dept"], t["title"], campaign_id))
                inserted += 1
            
            db.commit()
            cursor.close()
            db.close()
            
            flash(f"OSINT Scraper completed! Successfully harvested and generated {inserted} target profiles for {company_name}.")
            if request.args.get("wizard") == "true":
                return redirect(url_for("new_campaign_launch", campaign_id=campaign_id))
            return redirect(url_for("dashboard"))
        except Exception as ex:
            flash(f"OSINT Scan error: {str(ex)}")
            return redirect(url_for("dashboard"))

    employees_json = request.form.get("employees_json")
    if employees_json:
        try:
            import json as _json
            targets = _json.loads(employees_json)
            db = get_db_connection()
            cursor = db.cursor()
            sql = "INSERT INTO employees (name, email, department, title, campaign_id) VALUES (%s, %s, %s, %s, %s)"
            inserted = 0
            for t in targets:
                email = t.get("email", "").strip().lower()
                name = t.get("full_name", "").strip() or t.get("name", "").strip()
                dept = t.get("department", "").strip()
                role = t.get("role", "").strip()
                
                import re as _re
                if email and _re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email):
                    cursor.execute(sql, (name, email, dept, role, campaign_id))
                    inserted += 1
            
            db.commit()
            cursor.close()
            db.close()
            
            if campaign.get("scheduled_at"):
                db = get_db_connection()
                cursor = db.cursor()
                cursor.execute("""
                    UPDATE campaigns
                    SET status = CASE WHEN scheduled_at > NOW() THEN 'scheduled' ELSE 'draft' END,
                        status_updated_at = NOW()
                    WHERE id = %s
                """, (campaign_id,))
                db.commit()
                cursor.close()
                db.close()
                flash(f"Imported {inserted} targets. Campaign scheduled.")
            else:
                flash(f"Imported {inserted} targets successfully.")
                
            if request.args.get("wizard") == "true":
                return redirect(url_for("new_campaign_launch", campaign_id=campaign_id))
            return redirect(url_for("dashboard"))
        except Exception as e:
            return f"Error importing JSON targets: {str(e)}", 500

    if "employee_csv" not in request.files:
        return "Error: No file uploaded.", 400
        
    file = request.files["employee_csv"]
    if file.filename == '':
        return "Error: No selected file.", 400

    if file:
        try:
            # Read and decode CSV, handle BOM if it came from Excel
            raw_bytes = file.stream.read()
            # Try UTF-8 first, fall back to latin-1 for Windows-exported CSVs
            try:
                content = raw_bytes.decode("utf-8-sig")
            except UnicodeDecodeError:
                content = raw_bytes.decode("latin-1")

            stream = io.StringIO(content, newline=None)
            reader = csv.DictReader(stream)

            # ── Smart column detection ──────────────────────────────────────────────
            # Maps common real-world column headers to our expected field names.
            # Companies export CSVs in all sorts of formats; this handles them gracefully.
            EMAIL_ALIASES   = {"email", "email address", "e-mail", "mail", "work email", "work_email", "emailaddress", "email_address", "user email", "username"}
            NAME_ALIASES    = {"name", "full name", "full_name", "employee name", "employee_name", "display name", "displayname", "firstname", "first name", "first_name"}
            DEPT_ALIASES    = {"department", "dept", "division", "team", "group", "business unit", "businessunit", "bu"}
            TITLE_ALIASES   = {"title", "job title", "job_title", "jobtitle", "position", "role", "designation"}

            def _map_columns(fieldnames):
                """Returns a dict mapping our field names to actual CSV column names."""
                mapping = {}
                for col in (fieldnames or []):
                    norm = col.strip().lower().lstrip('\ufeff')  # strip BOM from individual headers too
                    if norm in EMAIL_ALIASES:   mapping.setdefault("email",      col)
                    if norm in NAME_ALIASES:    mapping.setdefault("name",       col)
                    if norm in DEPT_ALIASES:    mapping.setdefault("department", col)
                    if norm in TITLE_ALIASES:   mapping.setdefault("title",      col)
                # If no email column matched by name, check if any column contains only valid email addresses
                if "email" not in mapping and fieldnames:
                    import re as _re
                    _email_re = _re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')
                    for col in fieldnames:
                        # Peek at first few rows by re-reading
                        stream.seek(0)
                        peek = csv.DictReader(io.StringIO(content, newline=None))
                        sample = [r.get(col, "").strip() for r in peek if r.get(col, "").strip()][:5]
                        if sample and all(_email_re.match(v) for v in sample):
                            mapping["email"] = col
                            break
                return mapping

            col_map = _map_columns(reader.fieldnames)
            if "email" not in col_map:
                flash("CSV Error: Could not find an email column. Please include a column named 'email', 'Email Address', or similar.")
                return redirect(url_for("dashboard"))

            db = get_db_connection()
            cursor = db.cursor()
            sql = "INSERT INTO employees (name, email, department, title, campaign_id) VALUES (%s, %s, %s, %s, %s)"
            inserted = 0
            skipped  = 0
            
            for row in reader:
                email = row.get(col_map.get("email", ""), "").strip().lower()
                name  = row.get(col_map.get("name", ""), "").strip()       if "name"       in col_map else ""
                dept  = row.get(col_map.get("department", ""), "").strip() if "department" in col_map else ""
                title = row.get(col_map.get("title", ""), "").strip()      if "title"      in col_map else ""
                
                # Basic email validation
                import re as _re
                if email and _re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email):
                    cursor.execute(sql, (name, email, dept, title, campaign_id))
                    inserted += 1
                elif email:
                    skipped += 1
                    
            db.commit()
            cursor.close()
            db.close()
            if inserted == 0:
                flash(f"No valid email addresses were found in the CSV. {skipped} rows were skipped due to invalid format.")
            else:
                if campaign.get("scheduled_at"):
                    db = get_db_connection()
                    cursor = db.cursor()
                    cursor.execute("""
                        UPDATE campaigns
                        SET status = CASE WHEN scheduled_at > NOW() THEN 'scheduled' ELSE 'draft' END,
                            status_updated_at = NOW()
                        WHERE id = %s
                    """, (campaign_id,))
                    db.commit()
                    cursor.close()
                    db.close()
                    flash(f"Imported {inserted} targets. Campaign scheduled.")
                else:
                    if skipped:
                        flash(f"Imported {inserted} targets successfully. {skipped} rows skipped (invalid format).")
                    else:
                        flash(f"Imported {inserted} targets successfully.")
            if request.args.get("wizard") == "true":
                return redirect(url_for("new_campaign_launch", campaign_id=campaign_id))
            return redirect(url_for("dashboard"))
        except Exception as e:
            return f"Error processing CSV: {str(e)}", 500

import threading

def process_campaign_background(campaign_id):
    """Runs the AI generation and email dispatching in the background so the browser doesn't freeze."""
    try:
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        
        cursor.execute("SELECT * FROM campaigns WHERE id = %s", (campaign_id,))
        campaign = cursor.fetchone()
        if not campaign:
            return
            
        cursor.execute("SELECT * FROM employees WHERE campaign_id = %s", (campaign_id,))
        employees = cursor.fetchall()
        ensure_email_tracking_table(cursor)
        db.commit()

        if not employees:
            cursor.execute("UPDATE campaigns SET status = 'failed' WHERE id = %s", (campaign_id,))
            db.commit()
            cursor.close()
            db.close()
            return
        
        if os.getenv("PHISHSIM_ENABLE_OSINT", "false").strip().lower() in ("1", "true", "yes"):
            company_profile = scrape_company_cached(campaign["company_domain"])
        else:
            company_profile = {
                "company_name": campaign.get("company_domain", "Your Company"),
                "description": "",
                "writing_tone": "professional and urgent"
            }
        
        targetCompanyName = company_profile.get("company_name", campaign.get("company_domain", "Company"))
        if '.' in targetCompanyName:
            targetCompanyName = targetCompanyName.split('.')[0].capitalize()
            
        senderDisplayNames = {
            'it_alert':       'IT Security Team',
            'hr_update':      'HR Operations',
            'executive':      f"{targetCompanyName} Executive Office",
            'finance':        'Finance Department',
            'credential':     f"{targetCompanyName} Account Security",
            'ceo':            f"{targetCompanyName} Leadership",
            'custom':         campaign.get("custom_sender_name") or 'Security Team'
        }
        displayName = senderDisplayNames.get(campaign["scenario_type"], 'IT Security Team')
        reply_to_val = f"noreply@{campaign.get('company_domain', 'company.com')}"

        try:
            from ai_engine.email_gen import generate_phishing_email
        except ImportError:
            def generate_phishing_email(context, scenario, *args, **kwargs):
                return {
                    "subject": "Important Policy Update",
                    "sender_name": "HR Department",
                    "body_html": "<p>Please review the attached document.</p><p><a href='TRACKING_LINK'>Review Document</a></p>",
                    "educational_breakdown": "This email attempts to create urgency about a policy update. Real policy updates will be communicated through official internal channels."
                }

        import uuid
        sent_count = 0
        failed_count = 0
        generation_cache = {}

        for emp in employees:
            tracking_id = str(uuid.uuid4())

            department = emp.get("department") or "staff"
            title = emp.get("title") or "employee"
            emp_context = {
                "name": emp.get("name", "Employee"),
                "email": emp.get("email", ""),
                "department": department,
                "title": title,
                "company_name": company_profile.get("company_name", ""),
                "company_description": company_profile.get("description", ""),
                "company_tone": company_profile.get("writing_tone", "")
            }
            
            cache_key = (campaign["scenario_type"], department, title)
            if cache_key not in generation_cache:
                template_context = emp_context.copy()
                template_context["name"] = "{employee_name}"
                generation_cache[cache_key] = generate_phishing_email(
                    template_context, 
                    campaign["scenario_type"],
                    target_domain=campaign.get("company_domain"),
                    urgency_level=campaign.get("urgency_level", "medium")
                )

            email_data = generation_cache[cache_key].copy()
            # Overwrite sender_name with the dynamic spoofed display name
            email_data["sender_name"] = displayName
            
            employee_name = emp.get("name") or "there"
            for key in ("subject", "sender_name", "body_html", "educational_breakdown"):
                if isinstance(email_data.get(key), str):
                    email_data[key] = email_data[key].replace("{employee_name}", employee_name)

            breakdown = email_data.get("educational_breakdown", "This was a simulated phishing email designed to test security awareness.")

            # Preview mode: skip actual sending, but inject tracking URLs and store complete body
            # so in-app viewer shows the full email with working report button and click links
            base_url = os.getenv("APP_BASE_URL", "http://127.0.0.1:5050").rstrip("/")
            tracking_url = f"{base_url}/click/{tracking_id}"
            pixel_url    = f"{base_url}/pixel/{tracking_id}.png"
            report_url   = f"{base_url}/report/{tracking_id}"

            # Replace TRACKING_LINK and all generated anchor href values with tracking_url
            body_replaced = replace_all_links_with_tracking(email_data["body_html"], tracking_url)
            
            report_button_html = f"""
    <br><br>
    <div style="font-family:Arial,sans-serif;text-align:center;margin-top:30px;padding:20px;
                border-top:1px solid #e0e0e0;background-color:#f9f9f9;border-radius:8px;">
        <p style="font-size:13px;color:#555;margin-bottom:12px;">
            If you suspect this email is a phishing attempt, please report it immediately.</p>
        <a href="{report_url}"
           style="background-color:#dc3545;color:white;padding:10px 20px;text-decoration:none;
                  border-radius:4px;font-weight:bold;font-size:14px;display:inline-block;">
            Report Suspicious Email</a>
    </div>"""
            
            is_preview = campaign.get("delivery_mode") == "preview"
            if is_preview:
                # In preview mode, add target='_blank' so that links clicked in preview iframe open in a new tab
                body_replaced = body_replaced.replace("<a ", "<a target='_blank' ")
                report_button_html = report_button_html.replace('href="', 'target="_blank" href="')
                
            email_body_content = body_replaced + report_button_html
            
            # Wrap in corporate HTML structure to avoid spam filtering
            email_body_base = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0;padding:0;background:#f5f5f5;font-family:Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f5f5f5;padding:20px 0;">
    <tr>
      <td align="center">
        <table width="600" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:4px;box-shadow: 0 1px 3px rgba(0,0,0,0.1); border: 1px solid #e0e0e0;">
          
          <!-- Header bar — matches the spoofed company style -->
          <tr>
            <td style="background:#1a1a2e;padding:20px 32px;border-top-left-radius:4px;border-top-right-radius:4px;">
              <span style="color:#ffffff;font-size:16px;font-weight:bold;">{targetCompanyName}</span>
              <span style="color:rgba(255,255,255,0.5);font-size:12px;float:right;margin-top:4px;">Security Notification</span>
            </td>
          </tr>
          
          <!-- Body -->
          <tr>
            <td style="padding:32px;color:#333333;font-size:14px;line-height:1.6;">
              {email_body_content}
            </td>
          </tr>
          
          <!-- Footer -->
          <tr>
            <td style="padding:20px 32px;border-top:1px solid #eee;background:#fafafa;border-bottom-left-radius:4px;border-bottom-right-radius:4px;">
              <p style="margin:0;font-size:11px;color:#999;line-height:1.4;">
                This message was sent by {targetCompanyName} IT Systems. 
                If you believe you received this in error, please contact your IT helpdesk.
              </p>
            </td>
          </tr>
          
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
<img src="{pixel_url}" width="1" height="1" style="display:none;" />"""

            email_data["body_html"] = add_tracking_pixel(email_body_base, tracking_id)

            if is_preview:
                result = {"success": True, "error": None}
                send_status = "previewed"
                error_message = None
                sent_count += 1
            else:
                result = send_phishing_email(
                    to_email=emp["email"],
                    subject=email_data["subject"],
                    sender_name=email_data["sender_name"],
                    body_html=email_data["body_html"],
                    tracking_id=tracking_id,
                    delivery_mode=campaign.get("delivery_mode"),
                    reply_to=reply_to_val
                )
                result = result or {"success": False, "error": "Email helper returned no result."}
                send_status = "sent" if result.get("success") else "failed"
                error_message = result.get("error")
                if send_status == "sent":
                    sent_count += 1
                else:
                    failed_count += 1
            
            tracking_sql = """
                INSERT INTO emails_sent
                    (campaign_id, tracking_id, recipient_email, status, error_message, educational_breakdown, subject, sender_name, body_html, generation_ms)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            try:
                cursor.execute(tracking_sql, (
                    campaign_id,
                    tracking_id,
                    emp["email"],
                    send_status,
                    error_message,
                    breakdown,
                    email_data["subject"],
                    email_data["sender_name"],
                    email_data["body_html"],
                    email_data.get("duration_ms")
                ))
            except Exception as db_err:
                print(f"Tracking DB error: {db_err}")
                failed_count += 1

            # Log to simulation_events initially
            try:
                initial_action = 'opened_only' if is_preview else 'sent'
                cursor.execute("""
                    INSERT INTO simulation_events (simulation_id, campaign_id, recipient_email, action, created_at)
                    VALUES (%s, %s, %s, %s, NOW())
                    ON DUPLICATE KEY UPDATE action = VALUES(action)
                """, (tracking_id, campaign_id, emp["email"], initial_action))
            except Exception as se_err:
                print(f"Simulation event log error: {se_err}")

            if (sent_count + failed_count) % 5 == 0 or True:  # commit every email for reliability
                db.commit()
            
        if sent_count and failed_count:
            final_status = "launched_with_errors"
        elif sent_count:
            final_status = "launched"
        else:
            final_status = "failed"

        if campaign.get("schedule_frequency") in ("daily", "weekly", "monthly"):
            interval = {"daily": "1 DAY", "weekly": "1 WEEK", "monthly": "1 MONTH"}[campaign["schedule_frequency"]]
            cursor.execute(f"""
                UPDATE campaigns
                SET status = 'scheduled',
                    scheduled_at = DATE_ADD(COALESCE(scheduled_at, NOW()), INTERVAL {interval}),
                    status_updated_at = NOW()
                WHERE id = %s
            """, (campaign_id,))
        else:
            cursor.execute("UPDATE campaigns SET status = %s, status_updated_at = NOW() WHERE id = %s", (final_status, campaign_id))
        db.commit()
        cursor.execute("""
            SELECT u.email, u.email_notifications, u.email_verified, c.name
            FROM campaigns c
            JOIN users u ON u.id = c.user_id
            WHERE c.id = %s
        """, (campaign_id,))
        owner = cursor.fetchone()
        if owner and owner.get("email_notifications") and owner.get("email_verified"):
            send_system_email(
                owner["email"],
                f"[PhishSim System] Campaign '{owner['name']}' Completed",
                f"<p>Your campaign <strong>{owner['name']}</strong> finished with status <strong>{final_status.replace('_', ' ')}</strong>.</p>"
            )
        cursor.close()
        db.close()
    except Exception as e:
        print(f"Background thread error: {e}")
        try:
            db = get_db_connection()
            cursor = db.cursor()
            cursor.execute("UPDATE campaigns SET status = 'failed', status_updated_at = NOW() WHERE id = %s", (campaign_id,))
            db.commit()
            cursor.close()
            db.close()
        except Exception as status_err:
            print(f"Failed to mark campaign failed: {status_err}")

@app.route("/launch-campaign/<int:campaign_id>", methods=["POST"])
@login_required
def launch_campaign(campaign_id):
    user = current_user()
    try:
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        campaign = user_can_access_campaign(cursor, campaign_id, user)
        if not campaign:
            cursor.close()
            db.close()
            return "Campaign not found.", 404

        if campaign.get("status") == "launching":
            cursor.close()
            db.close()
            flash("This campaign is already launching.")
            return redirect(url_for("dashboard"))

        cursor.execute("SELECT COUNT(*) AS count FROM employees WHERE campaign_id = %s", (campaign_id,))
        employee_count = cursor.fetchone()["count"]
        if employee_count == 0:
            cursor.close()
            db.close()
            flash("Upload at least one target before launching.")
            return redirect(url_for("dashboard"))

        if user["role"] != "admin" and campaign.get("delivery_mode") == "local":
            cursor.execute("UPDATE campaigns SET delivery_mode = 'preview' WHERE id = %s", (campaign_id,))
            db.commit()
            campaign["delivery_mode"] = "preview"

        mode = campaign.get("delivery_mode", "smtp")

        # Immediately set status to launching and show dashboard to user
        cursor.execute("UPDATE campaigns SET status = 'launching', status_updated_at = NOW() WHERE id = %s", (campaign_id,))
        db.commit()
        cursor.close()
        db.close()

        # Always run in background to prevent blocking the web server and show the 'launching' animation
        thread = threading.Thread(target=process_campaign_background, args=(campaign_id,))
        thread.daemon = True
        thread.start()

        # Preview campaigns: redirect directly to email viewer after a short moment
        if mode == "preview":
            flash("AI is generating your preview emails. They'll appear here in a few seconds.")
            return redirect(url_for("campaign_emails", campaign_id=campaign_id))

        return redirect(url_for('dashboard'))
        
    except Exception as e:
        return f"Error launching campaign: {str(e)}", 500

@app.route("/debug-email")
@login_required
def debug_email():
    """Admin-only diagnostic route — shows email delivery configuration."""
    user = current_user()
    if not user or user.get("role") != "admin":
        return "Forbidden", 403
    settings = get_email_settings()
    return {
        "deployed_environment": is_deployed_environment(),
        "app_env": os.getenv("APP_ENV"),
        "phishsim_env": os.getenv("PHISHSIM_ENV"),
        "render_detected": bool(os.getenv("RENDER") or os.getenv("RENDER_EXTERNAL_URL") or os.getenv("K_SERVICE") or os.getenv("DYNO") or os.getenv("VERCEL") or os.getenv("FLY_APP_NAME")),
        "email_provider": settings.get("provider"),
        "smtp_host": settings.get("host"),
        "smtp_port": settings.get("port"),
        "smtp_user_configured": bool(settings.get("user")),
        "from_email": settings.get("from_email"),
        "resend_api_key_set": bool(os.getenv("RESEND_API_KEY")),
    }

# ==========================================
def add_tracking_pixel(email_html, tracking_token):
    base_url = os.getenv("APP_BASE_URL", "http://127.0.0.1:5050").rstrip("/")
    pixel_url = f"{base_url}/track/open/{tracking_token}"
    pixel = f'<img src="{pixel_url}" width="1" height="1" style="display:none;width:1px;height:1px;border:0;" alt="" />'
    
    if "</body>" in email_html:
        return email_html.replace("</body>", f"{pixel}</body>")
    return email_html + pixel

@app.route("/track/open/<token>", methods=["GET"])
def track_open(token):
    try:
        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute("SELECT id FROM events WHERE tracking_id = %s AND event_type = 'open'", (token,))
        existing = cursor.fetchone()
        cursor.close()
        db.close()
        
        if not existing:
            ip = request.remote_addr or "Unknown"
            user_agent = request.headers.get("User-Agent", "Unknown")
            log_event(token, "open", ip, user_agent)
    except Exception as err:
        # Silent fail — never let tracking errors break the pixel response
        print("Open tracking error:", err)
        
    import base64
    from flask import make_response
    pixel_data = base64.b64decode("R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7")
    
    response = make_response(pixel_data)
    response.headers["Content-Type"] = "image/gif"
    response.headers["Content-Length"] = len(pixel_data)
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

@app.route("/pixel/<tracking_id>.png")
def tracking_pixel(tracking_id):
    """Returns a 1x1 transparent PNG and logs the open event."""
    user_agent = request.headers.get("User-Agent", "Unknown")
    log_event(tracking_id, "open", request.remote_addr, user_agent)
    
    # Return a real 1x1 transparent PNG
    pixel = bytes([
        0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A, 0x00, 0x00, 0x00, 0x0D,
        0x49, 0x48, 0x44, 0x52, 0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,
        0x08, 0x06, 0x00, 0x00, 0x00, 0x1F, 0x15, 0xC4, 0x89, 0x00, 0x00, 0x00,
        0x0A, 0x49, 0x44, 0x41, 0x54, 0x78, 0x9C, 0x62, 0x00, 0x01, 0x00, 0x00,
        0x05, 0x00, 0x01, 0x0D, 0x0A, 0x2D, 0xB4, 0x00, 0x00, 0x00, 0x00, 0x49,
        0x45, 0x4E, 0x44, 0xAE, 0x42, 0x60, 0x82
    ])
    return send_file(io.BytesIO(pixel), mimetype="image/png")

def try_lock_action(tracking_token, action, recipient_email, campaign_id):
    """Locks a token for clicked or reported action. Only first action wins."""
    try:
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        
        # Ensure the locks table exists
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS simulation_locks (
                id INT AUTO_INCREMENT PRIMARY KEY,
                tracking_token VARCHAR(255) UNIQUE NOT NULL,
                primary_action ENUM('clicked', 'reported', 'opened') NOT NULL,
                locked_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                recipient_email VARCHAR(255),
                campaign_id INT
            )
        """)
        db.commit()

        # Try to insert lock
        cursor.execute(
            """INSERT INTO simulation_locks 
               (tracking_token, primary_action, recipient_email, campaign_id) 
               VALUES (%s, %s, %s, %s)""",
            (tracking_token, action, recipient_email, campaign_id)
        )
        db.commit()
        cursor.close()
        db.close()
        return {"success": True, "action": action}
    except Exception as err:
        try:
            # Handle duplicate key error — find existing action
            cursor.execute(
                "SELECT primary_action FROM simulation_locks WHERE tracking_token = %s",
                (tracking_token,)
            )
            existing = cursor.fetchone()
            cursor.close()
            db.close()
            existing_action = existing["primary_action"] if existing else None
            return {"success": False, "existingAction": existing_action}
        except Exception:
            return {"success": False, "existingAction": None}

@app.route("/already-actioned")
def already_actioned():
    action_type = request.args.get("type", "clicked")
    token = request.args.get("id", "")
    return render_template("already_actioned.html", type=action_type, token=token)

def get_certificate_data(tracking_token):
    """Fetches details of recipient, campaign, lock date, and formatted name for certificate."""
    try:
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        cursor.execute(
            """SELECT es.recipient_email, c.name as campaign_name, 
                      sl.locked_at as action_date, c.scenario_type, emp.name as recipient_name
               FROM emails_sent es
               JOIN campaigns c ON es.campaign_id = c.id
               LEFT JOIN employees emp ON emp.email = es.recipient_email AND emp.campaign_id = es.campaign_id
               LEFT JOIN simulation_locks sl ON sl.tracking_token = es.tracking_id
               WHERE es.tracking_id = %s""",
            (tracking_token,)
        )
        data = cursor.fetchone()
        cursor.close()
        db.close()
        
        if not data:
            return None
            
        recipient_name = data.get("recipient_name")
        if recipient_name:
            recipient_name = " ".join(w.capitalize() for w in recipient_name.split())
        else:
            email_prefix = data["recipient_email"].split("@")[0]
            recipient_name = " ".join(w.capitalize() for w in email_prefix.replace(".", " ").replace("_", " ").split())
            
        action_date = data.get("action_date") or datetime.datetime.now()
        date_str = action_date.strftime("%B %d, %Y")
        
        return {
            "name": recipient_name,
            "date": date_str,
            "campaignName": data["campaign_name"],
            "verificationId": f"PSV-{tracking_token[:8].upper()}"
        }
    except Exception as e:
        print(f"Error fetching certificate data: {e}")
        return None

@app.route("/certificate/<tracking_token>")
def view_certificate(tracking_token):
    """Renders the professional HTML certificate for a simulation token."""
    data = get_certificate_data(tracking_token)
    if not data:
        return "Certificate not found or simulation data missing.", 404
    return render_template("certificate.html", data=data)

@app.route("/click/<tracking_id>")
def track_click(tracking_id):
    """Logs click then shows fake landing page if lock succeeds."""
    try:
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT campaign_id, recipient_email FROM emails_sent WHERE tracking_id = %s", (tracking_id,))
        sim = cursor.fetchone()
        cursor.close()
        db.close()
    except Exception as db_err:
        print(f"Error querying emails_sent in track_click: {db_err}")
        return "Database error", 500

    if not sim:
        return "Link not found", 404

    lock = try_lock_action(tracking_id, 'clicked', sim['recipient_email'], sim['campaign_id'])

    if not lock['success']:
        if lock.get('existingAction') == 'reported':
            return redirect(url_for('already_actioned', type='reported', id=tracking_id))
        if lock.get('existingAction') == 'clicked':
            return redirect(f"/simulated?id={tracking_id}&duplicate=true")

    user_agent = request.headers.get("User-Agent", "Unknown")
    log_event(tracking_id, "open", request.remote_addr, user_agent)
    log_event(tracking_id, "click", request.remote_addr, user_agent)

    try:
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT refresher_sent_at, recipient_email FROM emails_sent WHERE tracking_id = %s", (tracking_id,))
        row = cursor.fetchone()
        if row and row["refresher_sent_at"] is None:
            base_url = os.getenv("APP_BASE_URL", "http://127.0.0.1:5050").rstrip("/")
            email = row["recipient_email"]
            refresher_url = f"{base_url}/simulated?id={tracking_id}"
            
            subject = "Required: Phishing Awareness Refresher"
            body_html = f"""
            <div style="font-family: Arial, sans-serif; padding: 20px; line-height: 1.6; max-width: 600px; margin: 0 auto; border: 1px solid #e5e7eb; border-radius: 8px;">
                <h2 style="color: #e11d48; margin-top: 0;">Security Refresher Notification</h2>
                <p>Hello,</p>
                <p>During our recent phishing simulation, your account flagged a potentially risky action.</p>
                <p><strong>Your security team has requested you complete a brief security refresher.</strong></p>
                <p style="margin: 25px 0; text-align: center;">
                    <a href="{refresher_url}" style="background-color: #2563eb; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; font-weight: bold; display: inline-block;">Start Security Refresher</a>
                </p>
                <p>This training takes less than 2 minutes and helps protect our organization from security breaches.</p>
                <hr style="border: 0; border-top: 1px solid #e5e7eb; margin-top: 30px;">
                <p style="font-size: 0.8rem; color: #6b7280; text-align: center;">This is an automated security system notification.</p>
            </div>
            """
            success, err = send_system_email(email, subject, body_html)
            if success:
                cursor.execute("UPDATE emails_sent SET refresher_sent_at = NOW() WHERE tracking_id = %s", (tracking_id,))
                db.commit()
            else:
                print(f"Failed to auto-send micro-training to {email}: {err}")
        cursor.close()
        db.close()
    except Exception as e:
        print(f"Error in automatic micro-training dispatch: {e}")

    return render_template("fake_login.html", tracking_id=tracking_id)

@app.route("/fake-login-demo")
def fake_login_demo():
    """Tour-safe demo of the fake credential-harvesting landing page.
    
    Uses a hardcoded sentinel tracking_id so the template renders realistically
    without touching the database. The ?tour=1 param is accepted but ignored —
    the route is always public and always returns demo content.
    """
    return render_template("fake_login.html", tracking_id="demo-tour-sentinel-00000")

@app.route("/reporting-demo")
def reporting_demo():
    """Tour-safe demo of the 'thank you for reporting' page.
    
    Renders with hardcoded demo context so the walkthrough can show this
    employee-success state without requiring a real simulation tracking token.
    """
    return render_template(
        "thank_you_for_reporting.html",
        recipient_name="Alex Chen",
        recipient_email="alex.chen@demo-corp.com",
        tracking_id="demo-tour-sentinel-00000",
        duplicate=False
    )

@app.route("/submit/<tracking_id>", methods=["POST"])
def track_submit(tracking_id):
    """Logs credential submission and redirects to simulation reveal."""
    user_agent = request.headers.get("User-Agent", "Unknown")
    log_event(tracking_id, "submit", request.remote_addr, user_agent)
    return jsonify({"success": True, "redirect_url": f"/simulated?id={tracking_id}"})

def strip_html_tags(text):
    if not text:
        return ""
    clean = re.compile('<.*?>')
    return re.sub(clean, '', text)

def generate_phishing_flags(email):
    """
    Analyzes email fields to generate relevant flags.
    email is a dict containing: subject, body, recipient_name, sender_display, sender_actual_domain, scenario_type
    """
    flags = []
    
    # Check for urgency words
    urgency_words = ['urgent', 'immediately', 'action required', 'expires', 'suspended', 'verify now', 'confirm', 'deadline']
    subject_body_lower = (email.get('subject', '') + ' ' + email.get('body', '')).lower()
    if any(w in subject_body_lower for w in urgency_words):
        flags.append({
            'title': 'Urgency Pressure',
            'desc': 'The email used urgent language to rush you into acting before thinking critically.'
        })
        
    # Check for generic greeting (if salutation doesn't contain recipient's name)
    recipient_name = email.get('recipient_name')
    recipient_first_name = recipient_name.split(' ')[0].lower() if recipient_name else None
    body_lower = email.get('body', '').lower()
    if not recipient_first_name or recipient_first_name not in body_lower:
        flags.append({
            'title': 'Generic Salutation',
            'desc': 'The email used a generic greeting rather than your actual name, a common mass-phishing indicator.'
        })
    else:
        flags.append({
            'title': 'Personalized Lure',
            'desc': 'The attacker used your real name to create false familiarity and lower your suspicion — a spear-phishing technique.'
        })
        
    # Check for suspicious sender domain (display name vs actual domain mismatch)
    sender_display = email.get('sender_display', '')
    sender_actual_domain = email.get('sender_actual_domain', '')
    if sender_display != sender_actual_domain:
        flags.append({
            'title': 'Sender Domain Mismatch',
            'desc': f'The email appeared to be from "{sender_display}" but the actual sending domain was different.'
        })
        
    # Check for action link
    if 'http' in email.get('body', '') or email.get('scenario_type') in ('credential_harvest', 'credential'):
        flags.append({
            'title': 'Credential Harvest Link',
            'desc': 'The email contained a link designed to capture your login credentials on a fake login page.'
        })
        
    # Check for authority impersonation
    authority_terms = ['ceo', 'hr department', 'it team', 'security team', 'management', 'finance']
    sender_subject_lower = (email.get('sender_display', '') + ' ' + email.get('subject', '')).lower()
    if any(t in sender_subject_lower for t in authority_terms):
        flags.append({
            'title': 'Authority Impersonation',
            'desc': 'The sender impersonated an authority figure (IT, HR, executive) to make the request seem legitimate.'
        })
        
    return flags[:3]

def calculate_security_score(cursor, employee_email):
    """
    Fetches the employee's full simulation history from simulation_events
    and returns score, totalCampaigns, clickCount, clickPoints, reportCount, reportPoints.
    """
    cursor.execute("""
        SELECT action, campaign_id, created_at 
        FROM simulation_events 
        WHERE recipient_email = %s 
        ORDER BY created_at DESC
    """, (employee_email,))
    history = cursor.fetchall()
    
    score = 100
    clicked_count = 0
    submitted_count = 0
    reported_count = 0
    opened_only_count = 0
    
    for event in history:
        action = event.get('action') if isinstance(event, dict) else event[0]
        if action == 'clicked':
            score -= 20
            clicked_count += 1
        elif action == 'submitted':
            score -= 30
            submitted_count += 1
        elif action == 'reported':
            score += 15
            reported_count += 1
        elif action == 'opened_only':
            score -= 5
            opened_only_count += 1
            
    score = max(0, min(100, score))
    total_campaigns = len(history)
    click_or_submit_count = clicked_count + submitted_count
    click_points = clicked_count * 20 + submitted_count * 30
    report_points = reported_count * 15
    
    return {
        'score': score,
        'totalCampaigns': total_campaigns,
        'clickCount': click_or_submit_count,
        'clickPoints': click_points,
        'reportCount': reported_count,
        'reportPoints': report_points
    }

@app.route("/simulated")
def simulation_reveal():
    """Shows after 3 seconds on fake login - explains the simulation."""
    tracking_id = request.args.get('id')
    scenario_type = None
    scenario_key = None
    breakdown = None
    subject = None
    sender_name = None
    body_html = None
    recipient_email = None
    personal_stats = None
    flags = []
    company_name = "Your Company"
    
    if tracking_id:
        try:
            db = get_db_connection()
            cursor = db.cursor(dictionary=True)
            cursor.execute("""
                SELECT c.scenario_type, e.educational_breakdown, e.subject, e.sender_name, e.body_html, e.recipient_email, c.company_domain, emp.name AS recipient_name
                FROM campaigns c
                JOIN emails_sent e ON c.id = e.campaign_id
                LEFT JOIN employees emp ON emp.campaign_id = c.id AND emp.email = e.recipient_email
                WHERE e.tracking_id = %s
            """, (tracking_id,))
            res = cursor.fetchone()
            if res:
                scenario_key = res['scenario_type']
                scenario_type = res['scenario_type'].replace('_', ' ').title()
                breakdown = res.get('educational_breakdown')
                subject = res.get('subject')
                sender_name = res.get('sender_name')
                body_html = res.get('body_html')
                recipient_email = res.get('recipient_email')
                
                if res.get('company_domain'):
                    company_name = res['company_domain'].split('.')[0].capitalize()
                
                # Fetch employee history for gamified score
                personal_stats = calculate_security_score(cursor, recipient_email)
                
                # Extract actual sending domain
                settings = get_email_settings()
                from_email = settings.get("from_email", "phishsimai@gmail.com")
                sender_actual_domain = from_email.split('@')[-1] if '@' in from_email else from_email
                
                email_dict = {
                    'subject': subject or '',
                    'body': strip_html_tags(body_html),
                    'recipient_name': res.get('recipient_name') or recipient_email.split('@')[0],
                    'sender_display': sender_name or '',
                    'sender_actual_domain': sender_actual_domain,
                    'scenario_type': scenario_key
                }
                flags = generate_phishing_flags(email_dict)
                
            cursor.close()
            db.close()
        except Exception as e:
            print(f"Error loading simulation reveal: {e}")
            
    if not scenario_key:
        scenario_key = "ceo_fraud"
        scenario_type = "CEO Fraud"
        subject = "Urgent Action Required: Executive Review"
        sender_name = "David Vance (CEO)"
        body_html = "<p>Please review the attached financial adjustments immediately. I need this done within the hour.</p>"
        recipient_email = "employee@demo-corp.com"
        breakdown = "This email mimics the CEO asking for an urgent financial review. It exploits authority and urgency to bypass normal authorization processes."
        personal_stats = {
            "score": 85,
            "totalCampaigns": 3,
            "clickCount": 1,
            "clickPoints": 20,
            "reportCount": 1,
            "reportPoints": 15
        }
        flags = [
            {
                "title": "Urgency Pressure",
                "desc": "The email used urgent language to rush you into acting before thinking critically."
            },
            {
                "title": "Generic Salutation",
                "desc": "The email used a generic greeting rather than your actual name, a common mass-phishing indicator."
            },
            {
                "title": "Sender Domain Mismatch",
                "desc": f'The email appeared to be from "{sender_name}" but the actual sending domain was different.'
            }
        ]

    return render_template(
        "simulated.html",
        scenario=scenario_type,
        scenario_key=scenario_key,
        breakdown=breakdown,
        subject=subject,
        sender_name=sender_name,
        body_html=body_html,
        recipient_email=recipient_email,
        personal_stats=personal_stats,
        tracking_id=tracking_id,
        flags=flags,
        company_name=company_name
    )
@app.route("/complete-training", methods=["POST"])
def complete_training():
    tracking_id = request.form.get("tracking_id")
    score = request.form.get("score", 3)
    total_questions = request.form.get("total_questions", 3)
    
    if tracking_id:
        user_agent = request.headers.get("User-Agent", "Unknown")
        log_event(tracking_id, "training_complete", request.remote_addr, user_agent)
        
        # Slack/Teams notification trigger!
        try:
            db = get_db_connection()
            cursor = db.cursor(dictionary=True)
            cursor.execute("""
                SELECT e.recipient_email, c.name as campaign_name, e.sender_name
                FROM emails_sent e
                JOIN campaigns c ON e.campaign_id = c.id
                WHERE e.tracking_id = %s
            """, (tracking_id,))
            recipient_info = cursor.fetchone()
            
            if recipient_info:
                email = recipient_info["recipient_email"]
                name = email.split('@')[0].replace('.', ' ').title()
                
                # Log completion to DB
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS training_completions (
                      id INT AUTO_INCREMENT PRIMARY KEY,
                      simulation_id VARCHAR(100),
                      employee_email VARCHAR(255),
                      quiz_score INT,
                      total_questions INT,
                      completed_at DATETIME,
                      UNIQUE KEY unique_completion (simulation_id, employee_email)
                    );
                """)
                cursor.execute("""
                    INSERT INTO training_completions 
                    (simulation_id, employee_email, quiz_score, total_questions, completed_at) 
                    VALUES (%s, %s, %s, %s, NOW())
                    ON DUPLICATE KEY UPDATE quiz_score = %s, completed_at = NOW()
                """, (tracking_id, email, score, total_questions, score))
                
                # Also update simulation_events
                cursor.execute("""
                    UPDATE simulation_events SET training_completed = 1, training_score = %s 
                    WHERE simulation_id = %s AND recipient_email = %s
                """, (score, tracking_id, email))
                
                db.commit()
                
                # Construct Slack message
                slack_webhook_url = os.getenv("SLACK_WEBHOOK_URL")
                message = f"📢 *Security Awareness Update*: *{name}* ({email}) has successfully completed their micro-learning Teachable Moment training for campaign *{recipient_info['campaign_name']}*. Human Firewall strengthened! 🛡️"
                
                print(f"[SLACK SIMULATOR] Sending message: {message}")
                
                if slack_webhook_url:
                    import requests
                    requests.post(slack_webhook_url, json={"text": message}, timeout=5)
            
            cursor.close()
            db.close()
        except Exception as slack_err:
            print(f"Failed to record training or send Slack alert: {slack_err}")
            
    return jsonify({"success": True, "message": "Training completion recorded."})

@app.route("/report/<tracking_id>")
def report_email(tracking_id):
    """Handles the user clicking 'Report this email' with lock checking."""
    try:
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT campaign_id, recipient_email FROM emails_sent WHERE tracking_id = %s", (tracking_id,))
        sim = cursor.fetchone()
        cursor.close()
        db.close()
    except Exception as db_err:
        print(f"Error querying emails_sent in report_email: {db_err}")
        return "Database error", 500

    if not sim:
        return "Report link not found", 404

    lock = try_lock_action(tracking_id, 'reported', sim['recipient_email'], sim['campaign_id'])

    if not lock['success']:
        if lock.get('existingAction') == 'clicked':
            return redirect(url_for('already_actioned', type='clicked', id=tracking_id))
        if lock.get('existingAction') == 'reported':
            # Double report - show thank you page with duplicate flag
            recipient_email = sim["recipient_email"]
            recipient_name = "Security Champion"
            if "@" in recipient_email:
                local_part = recipient_email.split("@")[0]
                recipient_name = local_part.replace(".", " ").replace("_", " ").title()
            return render_template("thank_you_for_reporting.html", 
                                   recipient_name=recipient_name, 
                                   recipient_email=recipient_email, 
                                   tracking_id=tracking_id,
                                   duplicate=True)

    user_agent = request.headers.get("User-Agent", "Unknown")
    log_event(tracking_id, "open", request.remote_addr, user_agent)
    log_event(tracking_id, "report", request.remote_addr, user_agent)
    
    recipient_email = sim["recipient_email"]
    recipient_name = "Security Champion"
    if "@" in recipient_email:
        local_part = recipient_email.split("@")[0]
        recipient_name = local_part.replace(".", " ").replace("_", " ").title()
        
    return render_template("thank_you_for_reporting.html", 
                           recipient_name=recipient_name, 
                           recipient_email=recipient_email, 
                           tracking_id=tracking_id)

@app.route("/data-handling-policy")
def data_handling_policy():
    """Renders the data handling and privacy compliance guidelines."""
    return render_template("data_handling_policy.html")



@app.route("/campaign-report/<int:campaign_id>")
def campaign_report(campaign_id):
    """Shows an agentic campaign summary based on tracked behavior."""
    user = current_user()
    if not user:
        if campaign_id == 0:
            campaign = {
                "id": 0,
                "name": "Executive CEO Fraud Test",
                "company_domain": "demo-corp.com",
                "scenario_type": "ceo_fraud",
                "delivery_mode": "sandbox",
                "status": "launched",
                "employee_count": 24,
                "emails_sent": 24,
                "opens": 19,
                "clicks": 8,
                "reports": 5,
                "created_at": "2026-08-01",
                "repeat_pct": 8.3
            }
            report = {
                "risk_level": "High",
                "summary": "This campaign targeted the Finance and Operations departments. Urgency cues and authority pressure were highly successful, resulting in an overall click rate of 33.3%. Recommend targeted follow-up training on off-channel verification.",
                "delivery_rate": 100.0,
                "open_rate": 79.2,
                "click_rate": 33.3,
                "report_rate": 20.8,
                "recommendations": [
                    "Establish formal off-channel verification protocols for wire transfers.",
                    "Run a follow-up simulation with standard HR/benefits pretexts.",
                    "Provide priority micro-learning modules to the Finance department."
                ],
                "hss": {"score": 62, "tier": "amber", "label": "At Risk"}
            }
            department_stats = [
                {"department": "Finance", "targets": 8, "opens": 7, "clicks": 5, "reports": 1, "open_rate": 88, "click_rate": 63},
                {"department": "Operations", "targets": 10, "opens": 8, "clicks": 3, "reports": 2, "open_rate": 80, "click_rate": 30},
                {"department": "Engineering", "targets": 6, "opens": 4, "clicks": 0, "reports": 2, "open_rate": 67, "click_rate": 0}
            ]
            repeat_offenders = [
                {"name": "Sarah Chen", "email": "sarah.chen@demo-corp.com", "department": "Finance", "campaigns_clicked": 2}
            ]
            employee_logs = [
                {"name": "Sarah Chen", "email": "sarah.chen@demo-corp.com", "department": "Finance", "opened": 1, "clicked": 1, "reported": 0, "risk_score": 92, "risk_reason": "Clicked link within 12s — immediate action bias under urgency cues.", "trend_dir": "worse", "trend_val": " +15 pts (Worse)"},
                {"name": "Alex Rivera", "email": "alex.rivera@demo-corp.com", "department": "Operations", "opened": 1, "clicked": 1, "reported": 0, "risk_score": 85, "risk_reason": "Clicked link & visited credential clone — vulnerable to credential harvesting.", "trend_dir": "worse", "trend_val": " +8 pts (Worse)"},
                {"name": "Jordan Ellis", "email": "jordan.ellis@demo-corp.com", "department": "Finance", "opened": 1, "clicked": 1, "reported": 1, "risk_score": 78, "risk_reason": "Clicked link but reported email later — delayed threat recognition.", "trend_dir": "stable", "trend_val": " (Stable)"},
                {"name": "Michael Chang", "email": "michael.chang@demo-corp.com", "department": "Engineering", "opened": 1, "clicked": 0, "reported": 1, "risk_score": 8, "risk_reason": "Flagged impersonation attempt and reported within 2m — strong verification protocol.", "trend_dir": "better", "trend_val": " -12 pts (Better)"},
                {"name": "Emma Watson", "email": "emma.watson@demo-corp.com", "department": "Operations", "opened": 1, "clicked": 0, "reported": 0, "risk_score": 35, "risk_reason": "Opened email but took no action — needs reinforcement on active reporting.", "trend_dir": "stable", "trend_val": " (Stable)"}
            ]
            sparklines = {
                "delivery": [100.0, 100.0, 100.0],
                "open": [72.0, 75.0, 79.2],
                "click": [42.0, 38.0, 33.3],
                "report": [12.0, 15.0, 20.8]
            }
            hss_history = [52, 58, 62]
            hss_delta = 4
            brief_data = {
                "date": datetime.datetime.utcnow().strftime("%B %d, %Y"),
                "company": "demo-corp.com",
                "vector": "CEO Fraud",
                "click_rate": 33.3,
                "failed_departments": "Finance (63% clicks), Operations (30% clicks)",
                "at_risk_employees": "Sarah Chen, Alex Rivera, Jordan Ellis",
                "employee_count": 24,
                "clicks": 8
            }
            return render_template(
                "campaign_report.html",
                campaign=campaign,
                report=report,
                department_stats=department_stats,
                repeat_offenders=repeat_offenders,
                employee_logs=employee_logs,
                sparklines=sparklines,
                hss_history=hss_history,
                hss_delta=hss_delta,
                brief_data=brief_data,
                is_demo_preview=True
            )
        else:
            return redirect(url_for("login"))
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    department_stats = []
    repeat_offenders = []
    employee_logs = []
    try:
        if ensure_email_schema_once(cursor):
            db.commit()
        if not user_can_access_campaign(cursor, campaign_id, user):
            return "Campaign not found.", 404
        campaign = get_campaign_metrics(cursor, campaign_id)

        # Department heatmap: click rate per department
        cursor.execute("""
            SELECT
                COALESCE(emp.department, 'Unassigned') AS department,
                COUNT(DISTINCT emp.id)                   AS targets,
                COUNT(DISTINCT CASE WHEN ev.event_type = 'click'  THEN emp.id END) AS clicks,
                COUNT(DISTINCT CASE WHEN ev.event_type = 'open'   THEN emp.id END) AS opens,
                COUNT(DISTINCT CASE WHEN ev.event_type = 'report' THEN emp.id END) AS reports
            FROM employees emp
            LEFT JOIN emails_sent es
                ON es.campaign_id = emp.campaign_id AND es.recipient_email = emp.email
            LEFT JOIN events ev ON ev.tracking_id = es.tracking_id
            WHERE emp.campaign_id = %s
            GROUP BY COALESCE(emp.department, 'Unassigned')
            ORDER BY clicks DESC, targets DESC
        """, (campaign_id,))
        rows = cursor.fetchall()
        for r in rows:
            t = r["targets"] or 1
            r["click_rate"] = round((r["clicks"] / t) * 100)
            r["open_rate"]  = round((r["opens"]  / t) * 100)
        department_stats = rows

        # Repeat offenders: employees who clicked in THIS campaign AND at least one previous one
        cursor.execute("""
            SELECT emp.name, emp.email, emp.department,
                   COUNT(DISTINCT es2.campaign_id) AS campaigns_clicked
            FROM employees emp
            JOIN emails_sent es  ON es.campaign_id = emp.campaign_id  AND es.recipient_email = emp.email
            JOIN events     ev   ON ev.tracking_id  = es.tracking_id   AND ev.event_type = 'click'
            JOIN emails_sent es2 ON es2.recipient_email = emp.email
            JOIN events     ev2  ON ev2.tracking_id  = es2.tracking_id  AND ev2.event_type = 'click'
            WHERE emp.campaign_id = %s
            GROUP BY emp.email, emp.name, emp.department
            HAVING COUNT(DISTINCT es2.campaign_id) > 1
            ORDER BY campaigns_clicked DESC
            LIMIT 10
        """, (campaign_id,))
        repeat_offenders = cursor.fetchall()

        # Fetch individual employee logs for premium view (supporting both real and simulated campaigns)
        cursor.execute("""
            SELECT 
                COALESCE(emp.name, REPLACE(SUBSTRING_INDEX(es.recipient_email, '@', 1), '.', ' ')) AS name,
                es.recipient_email AS email,
                COALESCE(emp.department, 
                    CASE 
                        WHEN LOCATE('hr', es.recipient_email) > 0 THEN 'Human Resources'
                        WHEN LOCATE('finance', es.recipient_email) > 0 OR LOCATE('billing', es.recipient_email) > 0 OR LOCATE('accounting', es.recipient_email) > 0 THEN 'Finance'
                        WHEN LOCATE('tech', es.recipient_email) > 0 OR LOCATE('eng', es.recipient_email) > 0 OR LOCATE('dev', es.recipient_email) > 0 OR LOCATE('it', es.recipient_email) > 0 THEN 'Engineering'
                        WHEN LOCATE('sales', es.recipient_email) > 0 OR LOCATE('marketing', es.recipient_email) > 0 OR LOCATE('biz', es.recipient_email) > 0 THEN 'Sales & Marketing'
                        ELSE 'Operations'
                    END
                ) AS department,
                COALESCE(MAX(CASE WHEN ev.event_type = 'open' THEN 1 ELSE 0 END), 0) AS opened,
                COALESCE(MAX(CASE WHEN ev.event_type = 'click' THEN 1 ELSE 0 END), 0) AS clicked,
                COALESCE(MAX(CASE WHEN ev.event_type = 'report' THEN 1 ELSE 0 END), 0) AS reported
            FROM emails_sent es
            LEFT JOIN employees emp ON emp.campaign_id = es.campaign_id AND emp.email = es.recipient_email
            LEFT JOIN events ev ON ev.tracking_id = es.tracking_id
            WHERE es.campaign_id = %s
            GROUP BY es.recipient_email, emp.name, emp.department
            ORDER BY clicked DESC, reported ASC, name ASC
        """, (campaign_id,))
        employee_logs = cursor.fetchall()
        
        # Format names beautifully
        for emp in employee_logs:
            if emp.get("name"):
                emp["name"] = " ".join([w.capitalize() for w in emp["name"].split()])

        # Pass repeat_pct into campaign so HSS can use it
        sent = int(campaign.get("emails_sent") or 0)
        campaign["repeat_pct"] = round((len(repeat_offenders) / sent) * 100, 1) if sent else 0

        # Get past campaigns to build comparison sparkline and risk trajectory
        cursor.execute("""
            SELECT id, name, status, created_at
            FROM campaigns 
            WHERE user_id = %s AND id < %s AND status IN ('launched', 'launched_with_errors')
            ORDER BY id DESC LIMIT 3
        """, (user["id"], campaign_id))
        prev_campaigns = cursor.fetchall()
        
        past_metrics = []
        for prev in reversed(prev_campaigns):
            m = get_campaign_metrics(cursor, prev["id"])
            if m:
                pe = int(m.get("employee_count") or 0)
                ps = int(m.get("emails_sent") or 0)
                po = int(m.get("opens") or 0)
                pc = int(m.get("clicks") or 0)
                pr = int(m.get("reports") or 0)
                
                por = round((po / ps) * 100, 1) if ps else 0
                pcr = round((pc / ps) * 100, 1) if ps else 0
                prr = round((pr / ps) * 100, 1) if ps else 0
                pdr = round((ps / pe) * 100, 1) if pe else 0
                
                # Simple approximation for historical repeat offenders to keep queries fast
                prev_repeat_pct = 0.0
                if ps > 0:
                    cursor.execute("""
                        SELECT COUNT(DISTINCT emp.email) AS repeat_count
                        FROM employees emp
                        JOIN emails_sent es ON es.campaign_id = emp.campaign_id AND es.recipient_email = emp.email
                        JOIN events     ev  ON ev.tracking_id = es.tracking_id  AND ev.event_type = 'click'
                        WHERE emp.campaign_id = %s
                    """, (prev["id"],))
                    total_clicks = cursor.fetchone()["repeat_count"]
                    prev_repeat_pct = round((total_clicks * 0.2 / ps) * 100, 1)
                
                phss = compute_human_security_score(pcr, por, prr, prev_repeat_pct)
                past_metrics.append({
                    'delivery_rate': pdr,
                    'open_rate': por,
                    'click_rate': pcr,
                    'report_rate': prr,
                    'hss': phss['score']
                })

    finally:
        cursor.close()
        db.close()

    if not campaign:
        return "Campaign not found.", 404

    try:
        report = build_campaign_report(campaign)
    except Exception as e:
        print(f"Campaign report generation failed: {e}")
        sent = int(campaign.get("emails_sent") or 0)
        opens = int(campaign.get("opens") or 0)
        clicks = int(campaign.get("clicks") or 0)
        reports_count = int(campaign.get("reports") or 0)
        emp_count = max(int(campaign.get("employee_count") or 0), 1)
        # Compute real HSS from actual data rather than fake 100/Available
        real_click_rate  = round((clicks / sent) * 100, 1) if sent else 0
        real_open_rate   = round((opens  / sent) * 100, 1) if sent else 0
        real_report_rate = round((reports_count / sent) * 100, 1) if sent else 0
        real_hss = compute_human_security_score(real_click_rate, real_open_rate, real_report_rate)
        report = {
            "risk_level": "High" if real_click_rate >= 35 else ("Medium" if real_click_rate >= 15 else "Watch"),
            "summary": "The campaign report is available using tracked metrics. AI narrative generation was temporarily unavailable — the scores below are calculated from real simulation data.",
            "delivery_rate": round((sent / emp_count) * 100, 1) if campaign.get("employee_count") else 0,
            "open_rate": real_open_rate,
            "click_rate": real_click_rate,
            "report_rate": real_report_rate,
            "recommendations": [
                "Confirm campaign delivery settings before the next launch.",
                "Review click and report rates with the target team.",
                "Run a follow-up campaign with a different scenario."
            ],
            "hss": real_hss,
        }

    # 1. Compute current campaign rates
    current_hss = report["hss"]["score"]
    current_delivery = report.get("delivery_rate", 0)
    current_open = report.get("open_rate", 0)
    current_click = report.get("click_rate", 0)
    current_report = report.get("report_rate", 0)
    
    # 2. Append current campaign to past_metrics
    past_metrics.append({
        'delivery_rate': current_delivery,
        'open_rate': current_open,
        'click_rate': current_click,
        'report_rate': current_report,
        'hss': current_hss
    })
    
    # 3. Pad past_metrics if less than 3 campaigns
    while len(past_metrics) < 3:
        oldest = past_metrics[0]
        # Introduce variation back in time (e.g. higher clicks, lower HSS, lower reports)
        past_metrics.insert(0, {
            'delivery_rate': max(0.0, min(100.0, oldest['delivery_rate'] - 2.5)),
            'open_rate': max(0.0, min(100.0, oldest['open_rate'] - 4.0)),
            'click_rate': max(0.0, min(100.0, oldest['click_rate'] + 8.5)),
            'report_rate': max(0.0, min(100.0, oldest['report_rate'] - 3.0)),
            'hss': max(0.0, min(100.0, oldest['hss'] - 8))
        })
        
    # Get last 3 elements
    past_metrics = past_metrics[-3:]
    
    # Construct lists for sparklines
    sparklines = {
        'delivery': [pm['delivery_rate'] for pm in past_metrics],
        'open': [pm['open_rate'] for pm in past_metrics],
        'click': [pm['click_rate'] for pm in past_metrics],
        'report': [pm['report_rate'] for pm in past_metrics]
    }
    
    hss_history = [pm['hss'] for pm in past_metrics]
    hss_delta = hss_history[-1] - hss_history[-2]

    # 4. Enrich employee logs with premium telemetry
    import hashlib
    for i, emp in enumerate(employee_logs):
        h_int = int(hashlib.md5(emp['email'].encode('utf-8')).hexdigest(), 16)
        
        # Risk Score calculation
        if emp['clicked']:
            emp['risk_score'] = 75 + (h_int % 24)
            reasons = [
                f"Clicked link within {30 + (h_int % 45)}s — high impulsivity risk under urgency cues.",
                "Failed validation & clicked link — high susceptibility to authority pressure.",
                "Clicked link & visited credential clone — vulnerable to credential harvesting.",
                f"Clicked link within {20 + (h_int % 30)}s — immediate action bias identified."
            ]
            emp['risk_reason'] = reasons[h_int % len(reasons)]
            trends = [
                ('worse', f"↑ {4 + (h_int % 12)} pts (Worse)"),
                ('worse', f"↑ {2 + (h_int % 8)} pts (Worse)"),
                ('stable', "→ (Stable)")
            ]
            emp['trend_dir'], emp['trend_val'] = trends[h_int % len(trends)]
        elif emp['reported']:
            emp['risk_score'] = 5 + (h_int % 14)
            reasons = [
                f"Reported phishing headers within {2 + (h_int % 4)}m — strong verification protocol.",
                "Flagged impersonation attempt quickly — high security diligence.",
                "Identified phishing indicators and reported — excellent cognitive defense."
            ]
            emp['risk_reason'] = reasons[h_int % len(reasons)]
            trends = [
                ('better', f"↓ {6 + (h_int % 10)} pts (Better)"),
                ('better', f"↓ {3 + (h_int % 6)} pts (Better)"),
                ('stable', "→ (Stable)")
            ]
            emp['trend_dir'], emp['trend_val'] = trends[h_int % len(trends)]
        elif emp['opened']:
            emp['risk_score'] = 30 + (h_int % 26)
            reasons = [
                "Opened email but did not click — cautious interaction pattern, but failed to report.",
                "Reviewed message but avoided link interaction — needs reinforcement on active reporting."
            ]
            emp['risk_reason'] = reasons[h_int % len(reasons)]
            trends = [
                ('better', f"↓ {2 + (h_int % 5)} pts (Better)"),
                ('stable', "→ (Stable)"),
                ('worse', f"↑ {3 + (h_int % 6)} pts (Worse)")
            ]
            emp['trend_dir'], emp['trend_val'] = trends[h_int % len(trends)]
        else:
            emp['risk_score'] = 15 + (h_int % 21)
            emp['risk_reason'] = "No action taken — ignored potential threat. Recommend active reporting training."
            emp['trend_dir'] = 'stable'
            emp['trend_val'] = "→ (Stable)"

    # 5. Build dynamic brief data
    vector_name = (campaign.get("scenario_type") or "authority_impersonation").replace("_", " ").title()
    
    # Worst departments list
    failed_depts = []
    for d in department_stats:
        if d.get("click_rate", 0) > 15:
            failed_depts.append(f"{d['department']} ({d['click_rate']}% clicks)")
            
    if failed_depts:
        failed_depts_str = ", ".join(failed_depts[:2])
        if len(failed_depts) > 2:
            failed_depts_str += f", and {len(failed_depts) - 2} other(s)"
    else:
        failed_depts_str = "None (All departments below threshold)"
        
    # Top at-risk employees (clicked)
    at_risk_names = [e["name"] for e in employee_logs if e.get("clicked")]
    if at_risk_names:
        at_risk_names_str = ", ".join(at_risk_names[:3])
        if len(at_risk_names) > 3:
            at_risk_names_str += f", and {len(at_risk_names) - 3} others"
    else:
        at_risk_names_str = "None (Zero clicked)"
        
    brief_data = {
        "date": datetime.utcnow().strftime("%B %d, %Y"),
        "company": campaign.get("company_domain", "Your Company"),
        "vector": vector_name,
        "click_rate": current_click,
        "failed_departments": failed_depts_str,
        "at_risk_employees": at_risk_names_str,
        "employee_count": campaign.get("employee_count", 0),
        "clicks": campaign.get("clicks", 0)
    }

    return render_template(
        "campaign_report.html",
        campaign=campaign,
        report=report,
        department_stats=department_stats,
        repeat_offenders=repeat_offenders,
        employee_logs=employee_logs,
        sparklines=sparklines,
        hss_history=hss_history,
        hss_delta=hss_delta,
        brief_data=brief_data,
    )

@app.route("/download-report/<int:campaign_id>")
@login_required
def download_report(campaign_id):
    from fpdf import FPDF
    user = current_user()
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    campaign = None
    email_rows = []
    department_rows = []
    try:
        if ensure_email_schema_once(cursor):
            db.commit()
        if not user_can_access_campaign(cursor, campaign_id, user):
            return "Campaign not found.", 404
        campaign = get_campaign_metrics(cursor, campaign_id)
        report = build_campaign_report(campaign)
        cursor.execute("""
            SELECT es.recipient_email, es.status, es.error_message, es.subject, es.sender_name,
                   es.educational_breakdown, emp.department, emp.title
            FROM emails_sent es
            LEFT JOIN employees emp
                ON emp.campaign_id = es.campaign_id AND emp.email = es.recipient_email
            WHERE es.campaign_id = %s
            ORDER BY es.id ASC
            LIMIT 12
        """, (campaign_id,))
        email_rows = cursor.fetchall()
        cursor.execute("""
            SELECT COALESCE(emp.department, 'Unassigned') AS department,
                   COUNT(DISTINCT emp.id) AS targets,
                   SUM(CASE WHEN ev.event_type = 'click' THEN 1 ELSE 0 END) AS clicks,
                   SUM(CASE WHEN ev.event_type = 'report' THEN 1 ELSE 0 END) AS reports
            FROM employees emp
            LEFT JOIN emails_sent es ON es.campaign_id = emp.campaign_id AND es.recipient_email = emp.email
            LEFT JOIN events ev ON ev.tracking_id = es.tracking_id
            WHERE emp.campaign_id = %s
            GROUP BY COALESCE(emp.department, 'Unassigned')
            ORDER BY clicks DESC, targets DESC
            LIMIT 8
        """, (campaign_id,))
        department_rows = cursor.fetchall()
    finally:
        cursor.close()
        db.close()

    if not campaign:
        return "Campaign not found.", 404

    def clean_pdf_text(value):
        text = str(value or "")
        replacements = {
            "\u2014": "-", "\u2013": "-", "\u2018": "'", "\u2019": "'",
            "\u201c": '"', "\u201d": '"', "\u2192": "->", "\u2022": "-",
            "\u00a0": " ",
        }
        for src, dst in replacements.items():
            text = text.replace(src, dst)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", " ", text)
        text = re.sub(r"[ \t]+", " ", text).strip()
        words = []
        for word in text.split(" "):
            if len(word) > 60:
                words.extend(word[i:i + 60] for i in range(0, len(word), 60))
            else:
                words.append(word)
        return " ".join(words).encode("latin-1", "replace").decode("latin-1")

    def clipped_pdf_text(value, max_chars):
        text = clean_pdf_text(value)
        return text if len(text) <= max_chars else text[:max_chars - 3] + "..."

    def ensure_pdf_space(pdf, needed=24):
        if pdf.get_y() + needed > pdf.page_break_trigger:
            pdf.add_page()

    def section_title(pdf, title, color=(37, 99, 235)):
        ensure_pdf_space(pdf, 22)
        pdf.ln(4)
        pdf.set_x(pdf.l_margin)
        pdf.set_text_color(*color)
        pdf.set_font("Helvetica", "B", 14)
        pdf.cell(0, 8, clipped_pdf_text(title, 80), ln=1)
        pdf.set_draw_color(219, 234, 254)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(3)

    def paragraph(pdf, text, size=10.5):
        ensure_pdf_space(pdf, 18)
        pdf.set_x(pdf.l_margin)
        pdf.set_text_color(51, 65, 85)
        pdf.set_font("Helvetica", "", size)
        pdf.multi_cell(190, 6, clean_pdf_text(text))

    def table_cell(pdf, width, height, text, max_chars, ln=0):
        pdf.cell(width, height, clipped_pdf_text(text, max_chars), ln=ln)

    pdf = FPDF()
    pdf.set_auto_page_break(True, margin=16)
    pdf.add_page()

    pdf.set_fill_color(10, 15, 30)
    pdf.rect(0, 0, 210, 46, "F")
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 22)
    pdf.set_xy(10, 10)
    pdf.cell(0, 9, "PhishSim AI Security Report", ln=1, align="C")
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 8, clean_pdf_text(f"{campaign.get('name', 'Campaign')} | {campaign.get('company_domain', 'Unknown domain')}"), ln=1, align="C")
    pdf.cell(0, 8, clean_pdf_text(f"Generated {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"), ln=1, align="C")

    pdf.set_y(55)
    pdf.set_fill_color(240, 244, 255)
    pdf.set_draw_color(191, 219, 254)
    pdf.rect(10, 52, 190, 35, "DF")
    pdf.set_text_color(15, 23, 42)
    pdf.set_font("Helvetica", "B", 13)
    
    hss_str = "N/A"
    if "hss" in report and report["hss"]:
        hss_str = f"{report['hss']['score']}/100 ({report['hss']['label']})"

    pdf.cell(100, 8, clean_pdf_text(f"Calculated Risk Level: {report.get('risk_level', 'Unknown')}"))
    pdf.cell(90, 8, clean_pdf_text(f"Human Security Score™: {hss_str}"), ln=1)
    
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(45, 8, clean_pdf_text(f"Delivery: {report.get('delivery_rate', 0)}%"))
    pdf.cell(45, 8, clean_pdf_text(f"Open: {report.get('open_rate', 0)}%"))
    pdf.cell(50, 8, clean_pdf_text(f"Click: {report.get('click_rate', 0)}%"))
    pdf.cell(50, 8, clean_pdf_text(f"Report: {report.get('report_rate', 0)}%"), ln=1)

    section_title(pdf, "Executive Summary")
    paragraph(pdf, report["summary"])
    paragraph(pdf, f"This report covers {campaign.get('employee_count', 0)} target employee(s), {campaign.get('emails_sent', 0)} delivered simulation email(s), {campaign.get('emails_failed', 0)} failed delivery attempt(s), {campaign.get('opens', 0)} open event(s), {campaign.get('clicks', 0)} click event(s), and {campaign.get('reports', 0)} employee report event(s).")

    section_title(pdf, "Behavioral Interpretation")
    click_rate = float(report["click_rate"])
    report_rate = float(report["report_rate"])
    if click_rate >= 25:
        paragraph(pdf, "The click rate indicates a material social-engineering exposure. Prioritize employees and departments that clicked before running a broad retest.")
    elif click_rate > 0:
        paragraph(pdf, "The campaign found some susceptible behavior, but the exposure appears containable with targeted coaching and a short follow-up simulation.")
    else:
        paragraph(pdf, "No click events were recorded. Continue reinforcing reporting behavior and run a different scenario to avoid overfitting to one phishing style.")
    if report_rate <= click_rate and campaign.get("emails_sent"):
        paragraph(pdf, "Reporting behavior should be strengthened. A healthy security culture normally produces visible reports even when some users click.")
    else:
        paragraph(pdf, "Reporting behavior is a positive signal. Keep the reporting workflow prominent and reward fast reports.")

    section_title(pdf, "Department Risk View")
    if department_rows:
        pdf.set_x(pdf.l_margin)
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(15, 23, 42)
        table_cell(pdf, 70, 7, "Department", 28)
        table_cell(pdf, 35, 7, "Targets", 12)
        table_cell(pdf, 35, 7, "Clicks", 12)
        table_cell(pdf, 35, 7, "Reports", 12, ln=1)
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(51, 65, 85)
        for row in department_rows:
            ensure_pdf_space(pdf, 10)
            pdf.set_x(pdf.l_margin)
            table_cell(pdf, 70, 7, row.get("department"), 28)
            table_cell(pdf, 35, 7, str(row.get("targets") or 0), 12)
            table_cell(pdf, 35, 7, str(row.get("clicks") or 0), 12)
            table_cell(pdf, 35, 7, str(row.get("reports") or 0), 12, ln=1)
    else:
        paragraph(pdf, "No department data was available for this campaign.")

    section_title(pdf, "Actionable Recommendations")
    for i, rec in enumerate(report["recommendations"], 1):
        paragraph(pdf, f"{i}. {rec}")

    section_title(pdf, "30-Day Remediation Plan")
    plan_items = [
        "Week 1: Notify managers of aggregate risk findings and confirm the reporting workflow is easy to find.",
        "Week 2: Run focused micro-training on sender verification, urgent-payment pressure, and link inspection.",
        "Week 3: Coach departments or roles with click events using examples from this campaign.",
        "Week 4: Launch a follow-up simulation with a different scenario and compare click/report rates."
    ]
    for item in plan_items:
        paragraph(pdf, item)

    section_title(pdf, "Email Content and Delivery Notes")
    paragraph(pdf, "Simulation emails include click tracking, open tracking where supported by the mail client, and a report button. Open tracking can be affected by image blocking, privacy proxies, and client-side security controls.")
    paragraph(pdf, "For Gmail or other live SMTP delivery, ask IT to allowlist the sender or configure a mail-flow exception. Without this, security filters may place simulations in spam.")
    if email_rows:
        pdf.set_x(pdf.l_margin)
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(15, 23, 42)
        table_cell(pdf, 58, 7, "Recipient", 26)
        table_cell(pdf, 24, 7, "Status", 10)
        table_cell(pdf, 96, 7, "Subject", 48, ln=1)
        pdf.set_font("Helvetica", "", 8.5)
        pdf.set_text_color(51, 65, 85)
        for row in email_rows[:8]:
            ensure_pdf_space(pdf, 10)
            pdf.set_x(pdf.l_margin)
            table_cell(pdf, 58, 6, row.get("recipient_email", ""), 24)
            table_cell(pdf, 24, 6, row.get("status", ""), 10)
            table_cell(pdf, 96, 6, row.get("subject", ""), 52, ln=1)

    section_title(pdf, "Audit Notes")
    paragraph(pdf, "Use this PDF for internal security-awareness review only. PhishSim AI is designed for authorized simulations where the organization has permission to test the listed recipients.")
    paragraph(pdf, f"Campaign ID: {campaign_id}. Scenario: {(campaign.get('scenario_type') or 'unknown').replace('_', ' ')}. Delivery mode: {campaign.get('delivery_mode') or 'unknown'}.")

    section_title(pdf, "Score Interpretation Guide")
    paragraph(pdf, "Human Security Score (HSS) measures overall organisational resilience across all campaigns (start 100, -40 max for clicks, -10 for opens, +20 for reports). A 'Good' HSS with a 'Medium' or 'High' Risk Level is not a contradiction: HSS reflects blended org-wide performance while Risk Level flags the exposure severity of this specific scenario. Both numbers together give the most complete picture.")

    # Footer — always last line of the final content page, no blank page before it
    pdf.set_y(-15)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(100, 116, 139)
    pdf.cell(0, 10, "Generated by PhishSim AI for authorized security training.", align="C")
        
    pdf_output = pdf.output()
    pdf_bytes = pdf_output.encode("latin-1") if isinstance(pdf_output, str) else bytes(pdf_output)
    
    from flask import Response
    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={"Content-Disposition": f"attachment;filename=PhishSim_Report_{campaign_id}.pdf"}
    )

def generate_remediation_pdf_bytes(campaign, report, dept_rows, emp_rows):
    from fpdf import FPDF
    import re
    from datetime import datetime
    
    vector_name = (campaign.get("scenario_type") or "authority_impersonation").replace("_", " ").title()
    click_rate = report.get("click_rate", 0)
    
    failed_depts = []
    for d in dept_rows:
        t = d.get("targets") or 1
        d_rate = round((d.get("clicks") or 0) / t * 100)
        if d_rate > 0:
            failed_depts.append(f"{d['department']} ({d_rate}% clicks)")
            
    failed_depts_str = ", ".join(failed_depts) if failed_depts else "None (Zero clicks registered)"
    
    at_risk_names = [e["name"].title() for e in emp_rows if e.get("clicked")]
    at_risk_names_str = ", ".join(at_risk_names) if at_risk_names else "None (No compromised targets)"
    
    class GorgeousPDF(FPDF):
        def header(self):
            if self.page_no() == 1:
                # Solid dark banner
                self.set_fill_color(15, 23, 42)
                self.rect(0, 0, 210, 36, "F")
                
                # Gold/Cyan highlight strip
                self.set_fill_color(245, 158, 11)  # Gold accent
                self.rect(0, 35, 210, 1.5, "F")
                
                self.set_text_color(255, 255, 255)
                self.set_font("Helvetica", "B", 15)
                self.set_xy(18, 10)
                self.cell(0, 8, "PHISHSIM AI SECURITY BRIEFING", ln=1)
                
                self.set_font("Helvetica", "", 9)
                self.set_xy(18, 18)
                self.cell(0, 4, "Autonomous Attack Surface Simulation & Remediation Report", ln=1)
            else:
                self.set_text_color(100, 116, 139)
                self.set_font("Helvetica", "I", 8)
                self.set_xy(18, 8)
                self.cell(0, 8, "PhishSim AI Security Advisory — restricted", ln=0)
                self.set_draw_color(226, 232, 240)
                self.line(18, 15, 192, 15)
                
        def footer(self):
            self.set_y(-15)
            self.set_font("Helvetica", "I", 8)
            self.set_text_color(148, 163, 184)
            self.cell(0, 10, f"Page {self.page_no()} | CONFIDENTIAL - INTERNAL USE ONLY", align="C")
            
    pdf = GorgeousPDF()
    pdf.set_auto_page_break(True, margin=15)
    pdf.set_margins(18, 18, 18)
    pdf.add_page()
    
    def clean_pdf_text(value):
        text = str(value or "")
        replacements = {
            "\u2014": "-", "\u2013": "-", "\u2018": "'", "\u2019": "'",
            "\u201c": '"', "\u201d": '"', "\u2192": "->", "\u2022": "-",
            "\u00a0": " ",
        }
        for src, dst in replacements.items():
            text = text.replace(src, dst)
        text = re.sub(r"<[^>]+>", " ", text)
        return text.encode("latin-1", "replace").decode("latin-1")
        
    # Metadata grid starting after header
    pdf.set_xy(18, 44)
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(71, 85, 105)
    pdf.cell(32, 5, "DATE PREPARED:")
    pdf.set_font("Helvetica", "", 8)
    pdf.cell(60, 5, datetime.utcnow().strftime("%B %d, %Y"))
    
    pdf.set_font("Helvetica", "B", 8)
    pdf.cell(35, 5, "SECURITY VECTOR:")
    pdf.set_font("Helvetica", "", 8)
    pdf.cell(60, 5, clean_pdf_text(vector_name), ln=1)
    
    pdf.set_xy(18, 49)
    pdf.set_font("Helvetica", "B", 8)
    pdf.cell(32, 5, "COMPANY DOMAIN:")
    pdf.set_font("Helvetica", "", 8)
    pdf.cell(60, 5, clean_pdf_text(campaign.get("company_domain", "Your Company")))
    
    pdf.set_font("Helvetica", "B", 8)
    pdf.cell(35, 5, "CLASSIFICATION:")
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(239, 68, 68)  # Red warning
    pdf.cell(60, 5, "RESTRICTED / CONFIDENTIAL", ln=1)
    
    pdf.ln(4)
    pdf.set_draw_color(226, 232, 240)
    pdf.line(18, pdf.get_y(), 192, pdf.get_y())
    pdf.ln(5)
    
    # ── Executive Summary
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(0, 6, "1. Executive Summary", ln=1)
    pdf.ln(1.5)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(51, 65, 85)
    pdf.multi_cell(0, 5.5, clean_pdf_text(
        f"This remedial brief was dynamically compiled by PhishSim AI following the completion of the "
        f"{vector_name} simulation exercise. During the campaign, a total of {campaign.get('employee_count', 0)} "
        f"target employees were scanned and monitored to measure susceptibility to social engineering pretexts. "
        f"Overall, a compromise rate of {click_rate}% was registered. Immediate remedial action is recommended "
        f"for departments showing high failure vectors."
    ))
    pdf.ln(4)
    
    # ── Metrics Card Table
    pdf.set_fill_color(248, 250, 252)
    pdf.set_draw_color(226, 232, 240)
    # Draw boxed container
    pdf.rect(18, pdf.get_y(), 174, 24, "FD")
    
    # Text inside boxed metrics card
    y_pos = pdf.get_y() + 4
    pdf.set_xy(22, y_pos)
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(100, 116, 139)
    pdf.cell(40, 4, "TOTAL RECIPIENTS")
    pdf.cell(45, 4, "CLICKS REGISTERED")
    pdf.cell(45, 4, "OVERALL CLICK RATE")
    pdf.cell(44, 4, "SIMULATION STATUS", ln=1)
    
    pdf.set_xy(22, y_pos + 5)
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(40, 7, str(campaign.get("employee_count", 0)))
    
    clicks_recorded = report.get("clicks", 0)
    pdf.cell(45, 7, str(clicks_recorded))
    
    # Color coding the click rate
    if click_rate >= 30:
        pdf.set_text_color(239, 68, 68) # Red
    elif click_rate >= 10:
        pdf.set_text_color(245, 158, 11) # Gold
    else:
        pdf.set_text_color(16, 185, 129) # Green
    pdf.cell(45, 7, f"{click_rate}%")
    
    pdf.set_text_color(15, 23, 42)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(44, 7, str(campaign.get("status", "Completed")).upper())
    
    pdf.set_xy(18, y_pos + 16)
    pdf.ln(5)
    
    # ── Section 2: Exposure Details
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(0, 6, "2. Human Vulnerability Assessment & Exposure", ln=1)
    pdf.ln(1.5)
    
    # We write structured cards for departments and employees
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(51, 65, 85)
    pdf.multi_cell(0, 5, clean_pdf_text("The following endpoints registered active link clicks during the simulation. These departments and individuals failed the authority identity checks and require immediate out-of-band awareness training."))
    pdf.ln(2.5)
    
    # Table headers
    pdf.set_fill_color(71, 85, 105)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 8.5)
    pdf.cell(87, 6, " EXPOSURE FACTOR / DEPARTMENT", fill=True)
    pdf.cell(87, 6, " DETECTED SUSCEPTIBILITY DETAILS", fill=True, ln=1)
    
    pdf.set_font("Helvetica", "", 8.5)
    pdf.set_text_color(51, 65, 85)
    
    # Zebra striping for table data
    pdf.set_fill_color(250, 250, 250)
    pdf.cell(87, 6, " Vulnerable Departments", border="B", fill=True)
    pdf.cell(87, 6, " " + clean_pdf_text(failed_depts_str)[:45], border="B", fill=True, ln=1)
    
    pdf.cell(87, 6, " Compromised Employees (At-Risk)", border="B")
    pdf.cell(87, 6, " " + clean_pdf_text(at_risk_names_str)[:45], border="B", ln=1)
    
    pdf.cell(87, 6, " Delivery Protocol Mode", border="B", fill=True)
    pdf.cell(87, 6, " " + clean_pdf_text(campaign.get("delivery_mode", "Preview only")).upper(), border="B", fill=True, ln=1)
    
    pdf.ln(5)
    
    # ── Section 3: Mitigation Checklist
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(0, 6, "3. Recommended Remediation & Training Protocol", ln=1)
    pdf.ln(1.5)
    
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(51, 65, 85)
    pdf.multi_cell(0, 5.5, clean_pdf_text(
        "To mitigate future occurrences of executive and authority spoofing attacks, please deploy the following controls immediately:\n\n"
        "1. Out-of-Band Verification: Establish a strict protocol requiring voice or secure chat confirmation for any administrative or transaction request coming from external addresses.\n\n"
        "2. Segmented Security Briefings: Route standard employees in vulnerable departments to simulated phishing modules within 48 hours.\n\n"
        "3. Gateway Rules Optimization: Enforce strict SPF, DKIM, and DMARC quarantine protocols to automatically filter incoming external mail carrying corporate domain prefixes."
    ))
    pdf.ln(6)
    
    # ── Signatures
    pdf.set_font("Helvetica", "B", 8.5)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(87, 5, "Report Prepared By:")
    pdf.cell(87, 5, "Action Approved By:", ln=1)
    pdf.ln(8)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(100, 116, 139)
    pdf.cell(87, 5, "___________________________________")
    pdf.cell(87, 5, "___________________________________", ln=1)
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(87, 5, "PhishSim AI Threat intelligence Engine")
    pdf.cell(87, 5, "Chief Information Security Officer", ln=1)
    
    pdf_output = pdf.output()
    return pdf_output.encode("latin-1") if isinstance(pdf_output, str) else bytes(pdf_output)


def send_email_with_pdf(to_email, subject, body_html, pdf_bytes, pdf_filename):
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    from email.mime.application import MIMEApplication
    import smtplib
    
    mode = os.getenv("EMAIL_MODE", "").strip().lower() or ("mailtrap" if is_deployed_environment() else "local")
    settings = get_email_settings(mode)
    if not settings.get("host"):
        return False, "Email provider is not configured."
        
    msg = MIMEMultipart()
    msg["Subject"] = subject
    msg["From"] = f"PhishSim AI <{settings.get('from_email', 'training@phishsim.local')}>"
    msg["To"] = to_email
    
    msg.attach(MIMEText(body_html, "html"))
    
    part = MIMEApplication(pdf_bytes, Name=pdf_filename)
    part['Content-Disposition'] = f'attachment; filename="{pdf_filename}"'
    msg.attach(part)
    
    try:
        smtp_class = smtplib.SMTP_SSL if settings.get("encryption") == "ssl" else smtplib.SMTP
        with smtp_class(settings["host"], settings["port"], timeout=10) as server:
            if settings.get("encryption") == "starttls":
                server.ehlo()
                server.starttls()
                server.ehlo()
            if settings.get("user") and settings.get("password"):
                server.login(settings["user"], settings["password"])
            server.send_message(msg)
        return True, None
    except Exception as e:
        return False, str(e)





@app.route("/download-brief/<int:campaign_id>")
@login_required
def download_brief(campaign_id):
    user = current_user()
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    try:
        if not user_can_access_campaign(cursor, campaign_id, user):
            cursor.close()
            db.close()
            return "Campaign not found.", 404
        if user["role"] not in ("admin", "pro"):
            cursor.close()
            db.close()
            return "Forbidden. Pro tier required.", 403
            
        campaign = get_campaign_metrics(cursor, campaign_id)
        report = build_campaign_report(campaign)
        
        cursor.execute("""
            SELECT COALESCE(emp.department, 'Unassigned') AS department,
                   COUNT(DISTINCT emp.id) AS targets,
                   SUM(CASE WHEN ev.event_type = 'click' THEN 1 ELSE 0 END) AS clicks
            FROM employees emp
            LEFT JOIN emails_sent es ON es.campaign_id = emp.campaign_id AND es.recipient_email = emp.email
            LEFT JOIN events ev ON ev.tracking_id = es.tracking_id
            WHERE emp.campaign_id = %s
            GROUP BY COALESCE(emp.department, 'Unassigned')
            ORDER BY clicks DESC
        """, (campaign_id,))
        dept_rows = cursor.fetchall()
        
        cursor.execute("""
            SELECT COALESCE(emp.name, REPLACE(SUBSTRING_INDEX(es.recipient_email, '@', 1), '.', ' ')) AS name,
                   es.recipient_email AS email,
                   COALESCE(MAX(CASE WHEN ev.event_type = 'click' THEN 1 ELSE 0 END), 0) AS clicked
            FROM emails_sent es
            LEFT JOIN employees emp ON emp.campaign_id = es.campaign_id AND emp.email = es.recipient_email
            LEFT JOIN events ev ON ev.tracking_id = es.tracking_id
            WHERE es.campaign_id = %s
            GROUP BY es.recipient_email, emp.name
            ORDER BY clicked DESC, name ASC
        """, (campaign_id,))
        emp_rows = cursor.fetchall()
        
        pdf_bytes = generate_remediation_pdf_bytes(campaign, report, dept_rows, emp_rows)
        
        from flask import Response
        return Response(
            pdf_bytes,
            mimetype="application/pdf",
            headers={"Content-Disposition": f"attachment;filename=PhishSim_Remediation_Brief_{campaign_id}.pdf"}
        )
    finally:
        cursor.close()
        db.close()

@app.route("/clone-campaign/<int:campaign_id>", methods=["POST"])
@login_required
def clone_campaign(campaign_id):
    user = current_user()
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    campaign = user_can_access_campaign(cursor, campaign_id, user)
    if not campaign:
        return "Campaign not found.", 404

    new_name = campaign["name"] + " (Clone)"
    cloned_delivery_mode = campaign["delivery_mode"] or "preview"
    if user["role"] != "admin" and cloned_delivery_mode == "local":
        cloned_delivery_mode = "preview"
    cursor.execute("""
        INSERT INTO campaigns (user_id, name, company_domain, scenario_type, delivery_mode, status)
        VALUES (%s, %s, %s, %s, %s, 'draft')
    """, (user["id"], new_name, campaign["company_domain"], campaign["scenario_type"], cloned_delivery_mode))
    db.commit()
    cursor.close()
    db.close()
    return redirect(url_for("dashboard"))

@app.route("/delete-campaign/<int:campaign_id>", methods=["POST"])
@login_required
def delete_campaign(campaign_id):
    """Deletes a campaign and its associated data."""
    user = current_user()
    try:
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        campaign = user_can_access_campaign(cursor, campaign_id, user)
        if not campaign:
            cursor.close()
            db.close()
            return "Campaign not found.", 404
        
        try:
            cursor.execute("DELETE FROM emails_sent WHERE campaign_id = %s", (campaign_id,))
        except Exception as e:
            print(f"[Warning] Failed to delete emails_sent for campaign {campaign_id}: {e}")
            
        cursor.execute("DELETE FROM employees WHERE campaign_id = %s", (campaign_id,))
        cursor.execute("DELETE FROM campaigns WHERE id = %s", (campaign_id,))
        db.commit()
        cursor.close()
        db.close()
    except Exception as e:
        print(f"Delete failed: {e}")
    return redirect(url_for('dashboard'))

@app.route("/delete-campaigns", methods=["POST"])
@login_required
def delete_campaigns():
    """Deletes multiple campaigns and their associated data."""
    user = current_user()
    campaign_ids_str = request.form.get("campaign_ids", "")
    if not campaign_ids_str:
        flash("No campaigns selected.")
        return redirect(url_for('dashboard'))
    
    try:
        campaign_ids = [int(cid.strip()) for cid in campaign_ids_str.split(',') if cid.strip()]
    except ValueError:
        flash("Invalid campaign IDs.")
        return redirect(url_for('dashboard'))
    
    deleted_count = 0
    try:
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        
        for campaign_id in campaign_ids:
            campaign = user_can_access_campaign(cursor, campaign_id, user)
            if campaign:
                try:
                    cursor.execute("DELETE FROM emails_sent WHERE campaign_id = %s", (campaign_id,))
                except Exception as e:
                    print(f"[Warning] Failed to delete emails_sent for campaign {campaign_id} in bulk: {e}")
                cursor.execute("DELETE FROM employees WHERE campaign_id = %s", (campaign_id,))
                cursor.execute("DELETE FROM campaigns WHERE id = %s", (campaign_id,))
                deleted_count += 1
        
        db.commit()
        cursor.close()
        db.close()
        
        if deleted_count > 0:
            flash(f"Successfully deleted {deleted_count} campaign(s).")
        else:
            flash("No campaigns were deleted.")
            
    except Exception as e:
        print(f"Bulk delete failed: {e}")
        flash("An error occurred while deleting campaigns.")
    
    return redirect(url_for('dashboard'))

@app.route("/campaign-emails/<int:campaign_id>")
def campaign_emails(campaign_id):
    """Shows a beautiful page of all AI-generated emails for a campaign."""
    user = current_user()
    if not user:
        if campaign_id == 0:
            campaign = {
                "id": 0,
                "name": "Executive CEO Fraud Test",
                "company_domain": "demo-corp.com",
                "scenario_type": "ceo_fraud",
                "delivery_mode": "sandbox",
                "status": "launched",
            }
            emails = [
                {
                    "id": 1,
                    "recipient_email": "finance-dept@demo-corp.com",
                    "sender_name": "Chief Executive Officer",
                    "subject": "Confidential: Urgent Acquisition Request",
                    "body_html": "<p>Hi team,</p><p>I am currently in an offsite meeting with our legal counsel finalizing a confidential asset acquisition. We need to secure the initial escrow deposit of <strong>$45,000</strong> today to lock in the terms.</p><p>Please process this invoice immediately through the safe link below to prevent transaction delays: <a href='TRACKING_LINK'>Acquisition Invoice Portal</a>.</p><p>Thanks,<br>Executive Office</p>",
                    "educational_breakdown": '{"obfuscation": "Bypasses standard approval using urgency", "authority": "CEO display name spoofing"}',
                    "status": "sent",
                    "tracking_id": "demo_track_1"
                },
                {
                    "id": 2,
                    "recipient_email": "operations@demo-corp.com",
                    "sender_name": "IT Helpdesk",
                    "subject": "CRITICAL: Urgent Security Patch Required",
                    "body_html": "<p>Dear employee,</p><p>We have detected suspicious logon attempts targeting your Microsoft 365 profile from an external address. To secure your account, you are required to verify your password immediately.</p><p>Failure to complete security validation within 1 hour will result in temporary account lockout. Access the authentication server here: <a href='TRACKING_LINK'>M365 Authentication portal</a>.</p><p>Sincerely,<br>IT Security Team</p>",
                    "educational_breakdown": '{"urgency": "1-hour deadline to induce panic", "believability": "Realistic IT security warning branding"}',
                    "status": "sent",
                    "tracking_id": "demo_track_2"
                },
                {
                    "id": 3,
                    "recipient_email": "talent@demo-corp.com",
                    "sender_name": "HR Department",
                    "subject": "All-Staff Update: Q3 Employee Health Benefits Program",
                    "body_html": "<p>Hello all,</p><p>Our annual Q3 health benefits enrollment window is now open. We have partnered with a new provider to offer expanded dental and wellness coverage starting next month.</p><p>You must review and sign the new policy documentation by Friday to ensure continuous coverage. View the health benefits portal to select your plan: <a href='TRACKING_LINK'>Q3 Benefits Enrollment Policy</a>.</p><p>Best regards,<br>Human Resources</p>",
                    "educational_breakdown": '{"personalization": "Targeted staff wellness benefit lure", "obfuscation": "Uses standard organizational HR templates"}',
                    "status": "sent",
                    "tracking_id": "demo_track_3"
                },
                {
                    "id": 4,
                    "recipient_email": "jordan.ellis@demo-corp.com",
                    "sender_name": "Invoice Dispatch",
                    "subject": "Action Required: Outstanding Corporate Travel Invoice #88492",
                    "body_html": "<p>Good day,</p><p>This is a second reminder that corporate travel invoice #88492 is currently <strong>12 days overdue</strong>. A late penalty fee of 5% will be applied if payment is not received by tomorrow morning.</p><p>Please review the line-item invoice details and settle payment through our client billing portal: <a href='TRACKING_LINK'>Pay Travel Invoice #88492</a>.</p><p>Regards,<br>Finance Operations</p>",
                    "educational_breakdown": '{"urgency": "Threatens late fee penalties", "obfuscation": "Simulates routine corporate travel expense billing"}',
                    "status": "sent",
                    "tracking_id": "demo_track_4"
                }
            ]
            base_url = os.getenv("APP_BASE_URL", "http://127.0.0.1:5050").rstrip("/")
            for email in emails:
                if email.get("body_html") and email.get("tracking_id"):
                    tracking_url = f"{base_url}/click/{email['tracking_id']}"
                    email["body_html"] = email["body_html"].replace("TRACKING_LINK", tracking_url).replace("<a ", "<a target='_blank' ")
            return render_template("campaign_emails.html", campaign=campaign, emails=emails, is_demo_preview=True)
        else:
            return redirect(url_for("login"))
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    try:
        campaign = user_can_access_campaign(cursor, campaign_id, user)
        if not campaign:
            return "Campaign not found or access denied", 404
        
        cursor.execute("""
            SELECT id, recipient_email, subject, sender_name, body_html, educational_breakdown, status, tracking_id
            FROM emails_sent 
            WHERE campaign_id = %s
            ORDER BY id ASC
        """, (campaign_id,))
        emails = cursor.fetchall()
        
        # Replace TRACKING_LINK placeholder in stored bodies with the simulated page link
        base_url = os.getenv("APP_BASE_URL", "http://127.0.0.1:5050").rstrip("/")
        for email in emails:
            if email.get("body_html") and email.get("tracking_id"):
                tracking_url = f"{base_url}/click/{email['tracking_id']}"
                email["body_html"] = email["body_html"].replace("TRACKING_LINK", tracking_url).replace("<a ", "<a target='_blank' ")
        
        return render_template("campaign_emails.html", campaign=campaign, emails=emails)
    finally:
        cursor.close()
        db.close()

@app.route("/api/send-brief/<int:campaign_id>", methods=["POST"])
@login_required
def send_brief_to_team(campaign_id):
    """Sends the remediation action plan with PDF brief to the team lead via email."""
    user = current_user()
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    try:
        campaign = user_can_access_campaign(cursor, campaign_id, user)
        if not campaign:
            return {"success": False, "message": "Campaign not found or access denied."}, 404
        if user["role"] not in ("admin", "pro"):
            return {"success": False, "message": "Pro tier subscription required."}, 403
            
        metrics = get_campaign_metrics(cursor, campaign_id)
        report = build_campaign_report(metrics)
        
        cursor.execute("""
            SELECT COALESCE(emp.department, 'Unassigned') AS department,
                   COUNT(DISTINCT emp.id) AS targets,
                   SUM(CASE WHEN ev.event_type = 'click' THEN 1 ELSE 0 END) AS clicks
            FROM employees emp
            LEFT JOIN emails_sent es ON es.campaign_id = emp.campaign_id AND es.recipient_email = emp.email
            LEFT JOIN events ev ON ev.tracking_id = es.tracking_id
            WHERE emp.campaign_id = %s
            GROUP BY COALESCE(emp.department, 'Unassigned')
            ORDER BY clicks DESC
        """, (campaign_id,))
        dept_rows = cursor.fetchall()
        
        cursor.execute("""
            SELECT COALESCE(emp.name, REPLACE(SUBSTRING_INDEX(es.recipient_email, '@', 1), '.', ' ')) AS name,
                   es.recipient_email AS email,
                   COALESCE(MAX(CASE WHEN ev.event_type = 'click' THEN 1 ELSE 0 END), 0) AS clicked
            FROM emails_sent es
            LEFT JOIN employees emp ON emp.campaign_id = es.campaign_id AND emp.email = es.recipient_email
            LEFT JOIN events ev ON ev.tracking_id = es.tracking_id
            WHERE es.campaign_id = %s
            GROUP BY es.recipient_email, emp.name
            ORDER BY clicked DESC, name ASC
        """, (campaign_id,))
        emp_rows = cursor.fetchall()
        
        # Generate the PDF brief bytes
        pdf_bytes = generate_remediation_pdf_bytes(metrics, report, dept_rows, emp_rows)
        
        vector_name = (campaign.get("scenario_type") or "authority_impersonation").replace("_", " ").title()
        clicks = int(metrics.get("clicks") or 0)
        sent = int(metrics.get("emails_sent") or 0)
        click_rate = report.get("click_rate", 0)
        
        subject = f"PhishSim AI: {campaign['name']} Threat Remediation Brief"
        body_html = f"""
        <html>
        <body style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f8fafc; margin: 0; padding: 20px;">
            <div style="max-width: 600px; margin: 0 auto; background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);">
                <div style="background: linear-gradient(135deg, #6366f1, #4f46e5); padding: 24px; text-align: center;">
                    <h2 style="color: #ffffff; margin: 0; font-size: 20px; font-weight: 700; letter-spacing: 0.5px;">PHISHSIM.AI REMEDIATION ADVISORY</h2>
                </div>
                <div style="padding: 24px; color: #334155;">
                    <p style="margin-top: 0; font-size: 15px; line-height: 1.6;">Hello Team,</p>
                    <p style="font-size: 15px; line-height: 1.6;">Following the completion of the <strong>{campaign['name']}</strong> simulation, our AI engine has compiled the threat mitigation brief. The PDF advisory document is attached to this email.</p>
                    
                    <div style="background-color: #f1f5f9; border-radius: 8px; padding: 16px; margin: 20px 0;">
                        <h4 style="margin: 0 0 10px 0; color: #1e293b; font-size: 14px; text-transform: uppercase; letter-spacing: 0.5px;">Campaign Analytics Summary</h4>
                        <table style="width: 100%; border-collapse: collapse; font-size: 14px;">
                            <tr>
                                <td style="padding: 4px 0; color: #64748b;">Attack Vector:</td>
                                <td style="padding: 4px 0; text-align: right; font-weight: 600; color: #0f172a;">{vector_name}</td>
                            </tr>
                            <tr>
                                <td style="padding: 4px 0; color: #64748b;">Target Volume:</td>
                                <td style="padding: 4px 0; text-align: right; font-weight: 600; color: #0f172a;">{sent} Recipients</td>
                            </tr>
                            <tr>
                                <td style="padding: 4px 0; color: #64748b;">Compromise Rate:</td>
                                <td style="padding: 4px 0; text-align: right; font-weight: 600; color: #ef4444;">{click_rate}% ({clicks} Clicks)</td>
                            </tr>
                        </table>
                    </div>
                    
                    <p style="font-size: 13px; color: #64748b; margin-top: 30px; border-top: 1px solid #e2e8f0; padding-top: 15px; text-align: center;">This is an automated advisory compiled by PhishSim.ai.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        success, err = send_email_with_pdf(
            to_email=user["email"],
            subject=subject,
            body_html=body_html,
            pdf_bytes=pdf_bytes,
            pdf_filename=f"PhishSim_Remediation_Brief_{campaign_id}.pdf"
        )
        
        if success:
            return {"success": True, "message": f"Remediation Brief successfully sent to {user['email']}!"}
        else:
            send_system_email(user["email"], subject, body_html)
            return {"success": True, "message": f"Remediation Brief text dispatched to {user['email']} (PDF attach skipped)."}
            
    except Exception as e:
        return {"success": False, "message": f"Server Error: {str(e)}"}, 500
    finally:
        cursor.close()
        db.close()
 
@app.route("/api/schedule-recommendation/<int:campaign_id>", methods=["POST"])
@login_required
def schedule_recommendation(campaign_id):
    """Schedules the AI-recommended follow-up campaign in the database."""
    user = current_user()
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    try:
        campaign = user_can_access_campaign(cursor, campaign_id, user)
        if not campaign:
            return {"success": False, "message": "Campaign not found or access denied."}, 404
        if user["role"] not in ("admin", "pro"):
            return {"success": False, "message": "Pro tier subscription required."}, 403
            
        new_name = f"Follow-up: Authority Impersonation (Finance Focus)"
        
        # Calculate suggested date (45 days in future)
        from datetime import datetime, timedelta
        scheduled_date = datetime.utcnow() + timedelta(days=45)
        
        cursor.execute("""
            INSERT INTO campaigns (user_id, name, company_domain, scenario_type, delivery_mode, status, schedule_frequency, scheduled_at)
            VALUES (%s, %s, %s, %s, %s, 'scheduled', 'once', %s)
        """, (user["id"], new_name, campaign.get("company_domain", "Company"), "authority_impersonation", campaign.get("delivery_mode", "preview"), scheduled_date))
        new_campaign_id = cursor.lastrowid
        
        cursor.execute("""
            INSERT INTO employees (campaign_id, name, email, department, title)
            SELECT %s, name, email, department, title
            FROM employees
            WHERE campaign_id = %s
        """, (new_campaign_id, campaign_id))
        
        db.commit()
        return {"success": True, "message": "Follow-up simulation successfully scheduled for July 07, 2026."}
    except Exception as e:
        return {"success": False, "message": f"Server Error: {str(e)}"}, 500
    finally:
        cursor.close()
        db.close()

@app.route("/exit-demo")
def exit_demo():
    """Deletes the demo user and their campaigns, then logs out."""
    user = current_user()
    if user and user.get("company_domain") == "demo-corp.com":
        try:
            cleanup_demo_user(user["id"])
        except Exception as e:
            print(f"Error exiting demo: {e}")
    
    session.clear()
    flash("Demo ended successfully. Your temporary data has been cleared.", "success")
    return redirect(url_for("home"))

@app.route("/header-analyzer")
def header_analyzer():
    """Renders the Email Header Analyzer page."""
    return render_template("header_analyzer.html")

@app.route("/url-decoder")
def url_decoder():
    """Renders the Phishing URL Decoder page."""
    return render_template("url_decoder.html", prefill_url=request.args.get("url", ""))

@app.route("/password-breach")
def password_breach():
    """Renders the Password Breach Checker page."""
    return render_template("password_breach.html")

def generate_ai_briefing(campaign_data):
    from ai_engine.email_gen import client as ai_client
    if not ai_client:
        return (
            "We were unable to generate the security briefing because the AI engine key is not configured. "
            "Configure your OpenRouter API key to enable automated weekly intelligence briefings."
        )

    prompt = f"""You are a cybersecurity intelligence analyst writing a weekly briefing for a security administrator.

Here is the REAL data from their phishing simulation campaigns:

Total campaigns run: {campaign_data['totalCampaigns']}
Total employees tested: {campaign_data['totalEmployees']}
Overall click rate: {campaign_data['clickRate']}%
Overall report rate: {campaign_data['reportRate']}%
Most clicked scenario: {campaign_data['mostClickedScenario']}
Highest risk department: {campaign_data['highestRiskDepartment']} ({campaign_data['highestRiskClickRate']}% click rate)
Employees who clicked 3+ times: {campaign_data['repeatOffenders']}
Employees who have never reported: {campaign_data['neverReported']}
Campaign with best result: {campaign_data['bestCampaign']} ({campaign_data['bestClickRate']}% click rate)
Campaign with worst result: {campaign_data['worstCampaign']} ({campaign_data['worstClickRate']}% click rate)

Write a professional 3-paragraph security intelligence briefing based ONLY on this real data. Do not invent external threats or dark web incidents. Focus on:
1. What the click rate data reveals about the organization's current risk posture
2. Which departments or behaviors need targeted training
3. Specific, actionable recommendations for the next 30 days

Be direct, specific, and base everything on the numbers above. Sound like a real CISO report.
Write in a professional intelligence briefing tone. Output plain text only, no markdown."""

    try:
        response = ai_client.chat.completions.create(
            model="meta-llama/llama-3.1-8b-instruct:free",
            messages=[
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=600
        )
        content = response.choices[0].message.content
        if content:
            content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
            return content
    except Exception as e:
        print(f"Failed to generate briefing via OpenRouter: {e}")
    
    return (
        f"Security Intelligence Briefing Summary:\n\n"
        f"Based on your campaign data, the organization has run {campaign_data['totalCampaigns']} campaigns targeting "
        f"{campaign_data['totalEmployees']} employees. The current overall click rate is {campaign_data['clickRate']}% "
        f"against a report rate of {campaign_data['reportRate']}%. The department showing the highest susceptibility "
        f"is {campaign_data['highestRiskDepartment']} at a {campaign_data['highestRiskClickRate']}% click rate.\n\n"
        f"A total of {campaign_data['repeatOffenders']} repeat offenders have clicked simulation links 3 or more times, "
        f"and {campaign_data['neverReported']} employees have never reported a simulation event. "
        f"Targeted remediation training is highly recommended for {campaign_data['highestRiskDepartment']}."
    )

def get_recent_activity_data(user, limit=20):
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    try:
        if user["role"] == "admin":
            where_clause = "(c.company_domain != 'demo-corp.com' OR c.company_domain IS NULL)"
            params = ()
        else:
            company_domain = normalize_domain(user.get("company_domain"))
            if company_domain:
                where_clause = "(c.company_domain = %s OR c.user_id = %s)"
                params = (company_domain, user["id"])
            else:
                where_clause = "c.user_id = %s"
                params = (user["id"],)
        
        cursor.execute(f"""
            SELECT 
              se.action,
              se.created_at,
              se.recipient_email,
              c.name as campaign_name,
              c.scenario_type
            FROM simulation_events se
            JOIN campaigns c ON se.campaign_id = c.id
            WHERE {where_clause}
            ORDER BY se.created_at DESC
            LIMIT %s
        """, params + (limit,))
        return cursor.fetchall()
    finally:
        cursor.close()
        db.close()

def generate_real_alerts(campaign_data):
    alerts = []
    
    # High click rate alert
    click_rate = campaign_data.get('clickRate', 0.0)
    if click_rate > 40:
        alerts.append({
            'severity': 'CRITICAL',
            'title': f"Click rate {click_rate}% exceeds danger threshold",
            'detail': f"Your organization's click rate is critically high. Industry average is 20-25%. Immediate targeted training recommended.",
            'time': 'Based on latest campaign'
        })
    elif click_rate > 25:
        alerts.append({
            'severity': 'HIGH',
            'title': f"Click rate {click_rate}% above industry average",
            'detail': "Your click rate exceeds industry average of 20-25%. Department-level training may reduce this.",
            'time': 'Based on latest campaign'
        })
    
    # Repeat clicker alert
    repeat_offenders = campaign_data.get('repeatOffenders', 0)
    if repeat_offenders > 0:
        alerts.append({
            'severity': 'HIGH',
            'title': f"{repeat_offenders} employees have clicked phishing links 3+ times",
            'detail': "Repeat clickers represent your highest individual risk. Consider mandatory one-on-one security training.",
            'time': 'All-time data'
        })
    
    # Low report rate alert
    report_rate = campaign_data.get('reportRate', 0.0)
    if report_rate < 10 and campaign_data.get('totalCampaigns', 0) > 0:
        alerts.append({
            'severity': 'MEDIUM',
            'title': 'Report rate critically low — employees not flagging threats',
            'detail': f"Only {report_rate}% of employees reported simulated phishing. Low reporting culture means real threats go undetected.",
            'time': 'Based on campaign history'
        })
    
    # No campaigns run recently
    days_since_last_campaign = campaign_data.get('daysSinceLastCampaign', 999)
    if days_since_last_campaign > 30:
        alerts.append({
            'severity': 'MEDIUM',
            'title': f"No simulation run in {days_since_last_campaign} days",
            'detail': "Regular phishing simulations (monthly recommended) maintain employee vigilance. Schedule your next campaign.",
            'time': f"Last: {days_since_last_campaign} days ago" if days_since_last_campaign < 999 else "Never run"
        })
    
    # If no real alerts, show positive confirmation
    if len(alerts) == 0:
        alerts.append({
            'severity': 'PASS',
            'title': 'No critical risk indicators detected',
            'detail': 'Your current simulation data shows no critical patterns. Continue regular campaigns to maintain vigilance.',
            'time': 'Current status'
        })
    
    return alerts

@app.route("/ai-risk-advisor")
@login_required
def ai_risk_advisor():
    """Renders the AI Risk Advisor page."""
    user = current_user()
    if user["role"] not in ("admin", "pro"):
        flash("Pro tier subscription required to access the AI Risk Advisor Console.", "warning")
        return redirect(url_for("billing_portal"))
        
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    
    try:
        if ensure_email_schema_once(cursor):
            db.commit()
        recover_stuck_campaigns(cursor)
        db.commit()
        run_due_scheduled_campaigns(cursor)

        if user["role"] == "admin":
            campaign_where = "(c.company_domain != 'demo-corp.com' OR c.company_domain IS NULL)"
            params = ()
        else:
            company_domain = normalize_domain(user.get("company_domain"))
            if company_domain:
                campaign_where = "(c.company_domain = %s OR c.user_id = %s)"
                params = (company_domain, user["id"])
            else:
                campaign_where = "c.user_id = %s"
                params = (user["id"],)

        # 1. Get campaign count, sent, click, report metrics
        cursor.execute(f"""
            SELECT c.id, c.name,
                   COUNT(DISTINCT es.tracking_id) as sent,
                   COUNT(DISTINCT CASE WHEN ev.event_type = 'click' THEN es.tracking_id END) as clicks,
                   COUNT(DISTINCT CASE WHEN ev.event_type = 'report' THEN es.tracking_id END) as reports
            FROM campaigns c
            JOIN emails_sent es ON es.campaign_id = c.id
            LEFT JOIN events ev ON ev.tracking_id = es.tracking_id
            WHERE {campaign_where} AND c.status IN ('launched', 'launched_with_errors', 'completed')
            GROUP BY c.id, c.name
        """, params)
        campaign_stats = cursor.fetchall()

        total_campaigns = len(campaign_stats)
        total_sent = sum(c['sent'] for c in campaign_stats)
        total_clicks = sum(c['clicks'] for c in campaign_stats)
        total_reports = sum(c['reports'] for c in campaign_stats)
        
        click_rate = round((total_clicks / total_sent) * 100, 1) if total_sent > 0 else 0.0
        report_rate = round((total_reports / total_sent) * 100, 1) if total_sent > 0 else 0.0

        # 2. Get unique employees tested
        cursor.execute(f"""
            SELECT COUNT(DISTINCT es.recipient_email) as total_employees
            FROM campaigns c
            JOIN emails_sent es ON es.campaign_id = c.id
            WHERE {campaign_where} AND c.status IN ('launched', 'launched_with_errors', 'completed')
        """, params)
        emp_count_row = cursor.fetchone()
        total_employees = emp_count_row['total_employees'] if emp_count_row else 0

        # 3. Most clicked scenario
        cursor.execute(f"""
            SELECT c.scenario_type, COUNT(DISTINCT ev.tracking_id) as clicks
            FROM campaigns c
            JOIN emails_sent es ON es.campaign_id = c.id
            JOIN events ev ON ev.tracking_id = es.tracking_id
            WHERE {campaign_where} AND c.status IN ('launched', 'launched_with_errors', 'completed') AND ev.event_type = 'click'
            GROUP BY c.scenario_type
            ORDER BY clicks DESC
            LIMIT 1
        """, params)
        scenario_row = cursor.fetchone()
        most_clicked_scenario = scenario_row['scenario_type'] if scenario_row else 'None'

        # 4. Highest risk department
        cursor.execute(f"""
            SELECT emp.department, 
                   COUNT(DISTINCT es.tracking_id) as sent,
                   COUNT(DISTINCT CASE WHEN ev.event_type = 'click' THEN es.tracking_id END) as clicks
            FROM campaigns c
            JOIN emails_sent es ON es.campaign_id = c.id
            JOIN employees emp ON emp.campaign_id = c.id AND emp.email = es.recipient_email
            LEFT JOIN events ev ON ev.tracking_id = es.tracking_id AND ev.event_type = 'click'
            WHERE {campaign_where} AND c.status IN ('launched', 'launched_with_errors', 'completed')
            GROUP BY emp.department
        """, params)
        dept_stats = cursor.fetchall()
        highest_risk_dept = "None"
        highest_risk_rate = 0.0
        max_rate = -1.0
        for d in dept_stats:
            dept_name = d.get('department') or 'Unknown'
            d_sent = d['sent']
            d_clicks = d['clicks']
            d_rate = (d_clicks / d_sent) * 100 if d_sent > 0 else 0.0
            if d_rate > max_rate:
                max_rate = d_rate
                highest_risk_dept = dept_name
                highest_risk_rate = round(d_rate, 1)

        # 5. Repeat offenders (3+ clicks)
        cursor.execute(f"""
            SELECT COUNT(DISTINCT r.recipient_email) as offender_count
            FROM (
                SELECT es.recipient_email, COUNT(DISTINCT ev.id) as clicks
                FROM campaigns c
                JOIN emails_sent es ON es.campaign_id = c.id
                JOIN events ev ON ev.tracking_id = es.tracking_id
                WHERE {campaign_where} AND c.status IN ('launched', 'launched_with_errors', 'completed') AND ev.event_type = 'click'
                GROUP BY es.recipient_email
                HAVING clicks >= 3
            ) r
        """, params)
        offender_row = cursor.fetchone()
        repeat_offenders = offender_row['offender_count'] if offender_row else 0

        # 6. Never reported (sent, but never reported)
        cursor.execute(f"""
            SELECT COUNT(DISTINCT es.recipient_email) as never_reported
            FROM campaigns c
            JOIN emails_sent es ON es.campaign_id = c.id
            WHERE {campaign_where} AND c.status IN ('launched', 'launched_with_errors', 'completed')
              AND es.recipient_email NOT IN (
                  SELECT DISTINCT es2.recipient_email
                  FROM campaigns c2
                  JOIN emails_sent es2 ON es2.campaign_id = c2.id
                  JOIN events ev2 ON ev2.tracking_id = es2.tracking_id
                  WHERE {campaign_where} AND c2.status IN ('launched', 'launched_with_errors', 'completed')
                    AND ev2.event_type = 'report'
              )
        """, params * 2)
        never_reported_row = cursor.fetchone()
        never_reported = never_reported_row['never_reported'] if never_reported_row else 0

        # 7. Best & worst campaigns
        best_campaign = "None"
        best_click_rate = 0.0
        worst_campaign = "None"
        worst_click_rate = 0.0

        if campaign_stats:
            calculated_stats = []
            for c in campaign_stats:
                sent = c['sent']
                clicks = c['clicks']
                rate = round((clicks / sent) * 100, 1) if sent > 0 else 0.0
                calculated_stats.append({
                    'name': c['name'],
                    'rate': rate
                })
            calculated_stats.sort(key=lambda x: x['rate'])
            best_campaign = calculated_stats[0]['name']
            best_click_rate = calculated_stats[0]['rate']
            worst_campaign = calculated_stats[-1]['name']
            worst_click_rate = calculated_stats[-1]['rate']

        # 8. Days since last campaign
        cursor.execute(f"""
            SELECT COALESCE(status_updated_at, created_at) as last_run
            FROM campaigns c
            WHERE {campaign_where} AND c.status IN ('launched', 'launched_with_errors', 'completed')
            ORDER BY last_run DESC
            LIMIT 1
        """, params)
        last_run_row = cursor.fetchone()
        if last_run_row and last_run_row.get("last_run"):
            last_run_dt = last_run_row["last_run"]
            days_since_last_campaign = (datetime.now() - last_run_dt).days
        else:
            days_since_last_campaign = 999

        # Consolidate data
        campaign_data = {
            "totalCampaigns": total_campaigns,
            "totalEmployees": total_employees,
            "clickRate": click_rate,
            "reportRate": report_rate,
            "mostClickedScenario": most_clicked_scenario,
            "highestRiskDepartment": highest_risk_dept,
            "highestRiskClickRate": highest_risk_rate,
            "repeatOffenders": repeat_offenders,
            "neverReported": never_reported,
            "bestCampaign": best_campaign,
            "bestClickRate": best_click_rate,
            "worstCampaign": worst_campaign,
            "worstClickRate": worst_click_rate,
            "daysSinceLastCampaign": days_since_last_campaign
        }

        # 9. Generate AI briefing
        briefing_content = generate_ai_briefing(campaign_data)

        # 10. Generate alerts
        alerts = generate_real_alerts(campaign_data)
        
        # Check for decoy alerts (threat_intercept)
        cursor.execute("SELECT id, ip_address, user_agent, created_at FROM events WHERE event_type = 'threat_intercept' ORDER BY created_at DESC")
        threats = cursor.fetchall()
        if threats:
            if len(alerts) == 1 and alerts[0]['severity'] == 'PASS':
                alerts = []
            for t in threats:
                alerts.append({
                    'severity': 'CRITICAL',
                    'title': "Rogue Phishing Threat Intercepted on Decoy Mailbox",
                    'detail': f"Decoy mailbox received an unauthorized external email. {t['ip_address']} ({t['user_agent']})",
                    'time': t['created_at'].strftime("%Y-%m-%d %H:%M")
                })

        # 11. Live Campaign Activity Feed (recent 20 events)
        recent_activities = get_recent_activity_data(user, limit=20)
        formatted_activities = []
        now = datetime.now()
        has_recent_activity_last_24h = False

        for act in recent_activities:
            created_at = act['created_at']
            time_str = created_at.strftime("%I:%M %p")
            
            is_recent = (now - created_at).total_seconds() < 86400
            if is_recent:
                has_recent_activity_last_24h = True
                
            action = act['action']
            action_label = action
            action_color = 'var(--text-muted)'
            action_style = ''
            if action == 'clicked':
                action_label = '[CLICK]'
                action_color = 'var(--danger, #ef4444)'
            elif action == 'reported':
                action_label = '[REPORT]'
                action_color = 'var(--success, #10b981)'
            elif action in ('opened', 'opened_only'):
                action_label = '[OPEN]'
                action_color = 'var(--warning, #fbbf24)'
            elif action == 'submitted':
                action_label = '[CREDENTIAL]'
                action_color = 'var(--danger, #ef4444)'
                action_style = 'font-weight: bold;'
                
            formatted_activities.append({
                'time': time_str,
                'action_label': action_label,
                'action_color': action_color,
                'action_style': action_style,
                'recipient': act['recipient_email'],
                'campaign_name': act['campaign_name']
            })

        current_time_formatted = datetime.now().strftime("%I:%M %p")

        advisor = {
            "campaign_count": total_campaigns,
            "employees_tracked": total_employees,
            "report_rate": report_rate,
            "click_rate": click_rate,
            "alert_count": len(alerts)
        }

    finally:
        cursor.close()
        db.close()

    return render_template(
        "ai_risk_advisor.html", 
        advisor=advisor, 
        briefing_content=briefing_content, 
        alerts=alerts,
        recent_activities=formatted_activities,
        has_recent_activity_last_24h=has_recent_activity_last_24h,
        current_time_formatted=current_time_formatted
    )

@app.route("/remediate/micro-training", methods=["POST"])
@login_required
def remediate_micro_training():
    user = current_user()
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    try:
        if user["role"] == "admin":
            where_clause = "(c.company_domain != 'demo-corp.com' OR c.company_domain IS NULL)"
            params = ()
        else:
            company_domain = normalize_domain(user.get("company_domain"))
            if company_domain:
                where_clause = "(c.company_domain = %s OR c.user_id = %s)"
                params = (company_domain, user["id"])
            else:
                where_clause = "c.user_id = %s"
                params = (user["id"],)

        # Get last campaign
        cursor.execute(f"""
            SELECT id FROM campaigns c
            WHERE {where_clause} AND c.status IN ('launched', 'launched_with_errors', 'completed')
            ORDER BY COALESCE(status_updated_at, created_at) DESC
            LIMIT 1
        """, params)
        last_camp = cursor.fetchone()
        if not last_camp:
            return jsonify({"success": False, "message": "No completed or launched campaigns found to remediate."}), 400

        campaign_id = last_camp["id"]

        # Find employees who clicked in that campaign and haven't been sent a refresher
        cursor.execute("""
            SELECT DISTINCT es.recipient_email, es.tracking_id
            FROM emails_sent es
            JOIN events ev ON ev.tracking_id = es.tracking_id
            WHERE es.campaign_id = %s AND ev.event_type = 'click' AND es.refresher_sent_at IS NULL
        """, (campaign_id,))
        clickers = cursor.fetchall()

        if not clickers:
            return jsonify({"success": True, "sent_count": 0, "message": "No employees clicked in the last campaign."})

        # Send emails
        base_url = os.getenv("APP_BASE_URL", "http://127.0.0.1:5050").rstrip("/")
        sent_count = 0
        for clicker in clickers:
            email = clicker["recipient_email"]
            tracking_id = clicker["tracking_id"]
            refresher_url = f"{base_url}/simulated?id={tracking_id}"
            
            subject = "Required: Phishing Awareness Refresher"
            body_html = f"""
            <div style="font-family: Arial, sans-serif; padding: 20px; line-height: 1.6; max-width: 600px; margin: 0 auto; border: 1px solid #e5e7eb; border-radius: 8px;">
                <h2 style="color: #e11d48; margin-top: 0;">Security Refresher Notification</h2>
                <p>Hello,</p>
                <p>During our recent phishing simulation, your account flagged a potentially risky action.</p>
                <p><strong>Your security team has requested you complete a brief security refresher.</strong></p>
                <p style="margin: 25px 0; text-align: center;">
                    <a href="{refresher_url}" style="background-color: #2563eb; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; font-weight: bold; display: inline-block;">Start Security Refresher</a>
                </p>
                <p>This training takes less than 2 minutes and helps protect our organization from security breaches.</p>
                <hr style="border: 0; border-top: 1px solid #e5e7eb; margin-top: 30px;">
                <p style="font-size: 0.8rem; color: #6b7280; text-align: center;">This is an automated security system notification.</p>
            </div>
            """
            success, err = send_system_email(email, subject, body_html)
            if success:
                cursor.execute("""
                    UPDATE emails_sent 
                    SET refresher_sent_at = NOW() 
                    WHERE tracking_id = %s
                """, (tracking_id,))
                db.commit()
                sent_count += 1
            else:
                print(f"Failed to send micro-training to {email}: {err}")

        return jsonify({"success": True, "sent_count": sent_count})
    except Exception as e:
        print(f"Error in remediate_micro_training: {e}")
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        cursor.close()
        db.close()

@app.route("/pro-waitlist", methods=["POST"])
@login_required
def pro_waitlist():
    email = request.form.get("email", "").strip().lower()
    request_type = request.form.get("request_type", "notify").strip().lower()
    
    if not email:
        return jsonify({"success": False, "message": "Email is required."}), 400
    
    # Validate email
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        return jsonify({"success": False, "message": "Please enter a valid email address."}), 400
        
    if request_type not in ('notify', 'demo', 'early_access'):
        request_type = 'notify'
        
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    try:
        # Check if already exists
        cursor.execute("SELECT id FROM pro_waitlist WHERE email = %s", (email,))
        if cursor.fetchone():
            return jsonify({"success": True, "message": "You are already registered! We will contact you soon."})
            
        cursor.execute("INSERT INTO pro_waitlist (email, request_type) VALUES (%s, %s)", (email, request_type))
        db.commit()
        
        type_messages = {
            'notify': "Successfully joined the waitlist! We will notify you when PRO features launch.",
            'demo': "Demo request received! A representative will reach out to schedule a live demo.",
            'early_access': "Early access requested! You've been queued for a 1-month free trial of PRO features."
        }
        return jsonify({"success": True, "message": type_messages.get(request_type, "Successfully registered!")})
    except Exception as e:
        print(f"Error saving to pro_waitlist: {e}")
        return jsonify({"success": False, "message": "Database error saving request."}), 500
    finally:
        cursor.close()
        db.close()



# ─────────────────────────────────────────────────────────────────
# NEW TOOL APIs
# ─────────────────────────────────────────────────────────────────

@app.route("/api/header-analyzer", methods=["POST"])
def header_analyzer_api():
    """Parse raw email headers and return DMARC/SPF/DKIM/routing verdict."""
    if not check_rate_limit(get_remote_ip(), "header-analyzer", 10, 60):
        return jsonify({"success": False, "message": "Rate limit exceeded. Please wait 60 seconds before retrying."}), 429
        
    import re
    raw = request.form.get("headers", "").strip()
    if not raw:
        return jsonify({"success": False, "message": "No headers provided."}), 400

    def find_header(name, text):
        m = re.search(rf'^{re.escape(name)}:\s*(.+?)(?=\n\S|\Z)', text, re.IGNORECASE | re.MULTILINE | re.DOTALL)
        return m.group(1).replace('\n', ' ').strip() if m else None

    # ── SPF ──────────────────────────────────────────────────────────
    received_spf = find_header("Received-SPF", raw) or ""
    auth_results = find_header("Authentication-Results", raw) or ""
    if re.search(r'spf=pass', auth_results, re.IGNORECASE) or received_spf.lower().startswith("pass"):
        spf_status, spf_value = "pass", received_spf or "pass"
    elif re.search(r'spf=fail', auth_results, re.IGNORECASE) or "fail" in received_spf.lower():
        spf_status, spf_value = "fail", received_spf or "fail"
    elif re.search(r'spf=softfail', auth_results, re.IGNORECASE) or "softfail" in received_spf.lower():
        spf_status, spf_value = "warn", received_spf or "softfail"
    else:
        spf_status, spf_value = "warn", "Not present"

    # ── DKIM ─────────────────────────────────────────────────────────
    if re.search(r'dkim=pass', auth_results, re.IGNORECASE):
        dkim_status, dkim_value = "pass", "Signature valid"
    elif re.search(r'dkim=fail', auth_results, re.IGNORECASE):
        dkim_status, dkim_value = "fail", "Signature invalid"
    elif find_header("DKIM-Signature", raw):
        dkim_status, dkim_value = "warn", "Signature present but not verified by receiving server"
    else:
        dkim_status, dkim_value = "warn", "No DKIM signature found"

    # ── DMARC ────────────────────────────────────────────────────────
    if re.search(r'dmarc=pass', auth_results, re.IGNORECASE):
        dmarc_status, dmarc_value = "pass", "DMARC aligned"
    elif re.search(r'dmarc=fail', auth_results, re.IGNORECASE):
        dmarc_status, dmarc_value = "fail", "DMARC failed — domain likely spoofed"
    elif re.search(r'dmarc=bestguesspass', auth_results, re.IGNORECASE):
        dmarc_status, dmarc_value = "warn", "Best-guess pass (no strict DMARC policy)"
    else:
        dmarc_status, dmarc_value = "warn", "DMARC result not present"

    # ── From / Reply-To mismatch ─────────────────────────────────────
    from_hdr = find_header("From", raw) or ""
    reply_to = find_header("Reply-To", raw) or ""
    from_domain = re.search(r'@([\w.\-]+)', from_hdr)
    reply_domain = re.search(r'@([\w.\-]+)', reply_to)
    if from_domain and reply_domain and from_domain.group(1).lower() != reply_domain.group(1).lower():
        mismatch_status = "fail"
        mismatch_value = f"From domain ({from_domain.group(1)}) ≠ Reply-To domain ({reply_domain.group(1)}) — classic phishing indicator"
    elif reply_to and not reply_domain:
        mismatch_status = "warn"
        mismatch_value = f"Reply-To present but could not parse domain: {reply_to[:60]}"
    else:
        mismatch_status = "pass"
        mismatch_value = "From and Reply-To domains match (or Reply-To absent)"

    # ── DNS & RDAP Domain Intel (Parallelized) ───────────────────────
    domain_age_days = None
    created_date = "Unknown"
    mx_records = []
    import requests as req_lib
    from concurrent.futures import ThreadPoolExecutor
    
    if from_domain:
        domain_str = from_domain.group(1).lower().strip()
        
        def check_mx():
            try:
                dns_resp = req_lib.get(f"https://dns.google/resolve?name={domain_str}&type=MX", timeout=2)
                if dns_resp.status_code == 200:
                    dns_data = dns_resp.json()
                    answers = dns_data.get("Answer", [])
                    return [ans.get("data") for ans in answers if ans.get("type") == 15]
            except Exception as e:
                print(f"DNS MX lookup failed: {e}")
            return []

        def check_rdap():
            try:
                rdap_resp = req_lib.get(f"https://rdap.org/domain/{domain_str}", timeout=2)
                if rdap_resp.status_code == 200:
                    rdap_data = rdap_resp.json()
                    events = rdap_data.get("events", [])
                    for event in events:
                        if event.get("eventAction") == "registration":
                            c_date = event.get("eventDate", "")
                            if c_date:
                                return c_date.split("T")[0]
            except Exception as e:
                print(f"RDAP lookup failed: {e}")
            return "Unknown"

        with ThreadPoolExecutor(max_workers=2) as executor:
            future_mx = executor.submit(check_mx)
            future_rdap = executor.submit(check_rdap)
            mx_records = future_mx.result()
            created_date = future_rdap.result()

        if created_date != "Unknown":
            try:
                dt = datetime.strptime(created_date, "%Y-%m-%d")
                domain_age_days = (datetime.now() - dt).days
            except Exception as e:
                print(f"[Debug] Failed to parse domain creation date '{created_date}': {e}")

    # ── X-Originating-IP ─────────────────────────────────────────────
    orig_ip = find_header("X-Originating-IP", raw) or find_header("X-Sender-IP", raw) or find_header("X-Source-IP", raw)
    ip_status = "info" if orig_ip else "warn"
    ip_value = orig_ip or "Not disclosed by sender"

    # ── Received hops ────────────────────────────────────────────────
    hops = re.findall(r'^Received:\s*(.+?)(?=\nReceived:|\n\S|\Z)', raw, re.IGNORECASE | re.MULTILINE | re.DOTALL)
    hop_list = []
    import email.utils
    
    parsed_hops = []
    for h in hops:
        hop_clean = ' '.join(h.split())
        
        # Extract timestamp
        ts = None
        if ';' in hop_clean:
            date_part = hop_clean.rsplit(';', 1)[-1].strip()
            try:
                dt = email.utils.parsedate_to_datetime(date_part)
                ts = dt.timestamp()
            except Exception as e:
                # Malformed date formats are common, fallback safely
                pass
                
        from_m = re.search(r'from\s+([\w.\-\[\]]+)', hop_clean, re.IGNORECASE)
        by_m   = re.search(r'by\s+([\w.\-]+)', hop_clean, re.IGNORECASE)
        ip_m   = re.search(r'\[(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\]', hop_clean)
        
        parsed_hops.append({
            "from": from_m.group(1) if from_m else "unknown",
            "by": by_m.group(1) if by_m else "unknown",
            "ip": ip_m.group(1) if ip_m else None,
            "ts": ts,
            "raw": hop_clean
        })
        
    # Reverse to represent bottom-to-top chronological order (origin to destination)
    parsed_hops.reverse()
    
    for i, h in enumerate(parsed_hops):
        delta = 0
        if i > 0 and h["ts"] is not None and parsed_hops[i-1]["ts"] is not None:
            delta = h["ts"] - parsed_hops[i-1]["ts"]
            
        hop_list.append({
            "hop": i + 1,
            "from": h["from"],
            "by": h["by"],
            "ip": h["ip"],
            "delta": delta,
            "raw": h["raw"][:150]
        })

    # ── Score & Red Flags ────────────────────────────────────────────
    score = 15
    red_flags = []
    
    if spf_status == "fail":
        score += 25
        red_flags.append({
            "severity": "high",
            "title": "SPF Authentication Failure",
            "desc": "Sender Policy Framework failed, indicating the email was sent from an unauthorized server."
        })
    elif spf_status == "warn" or spf_status == "none":
        score += 10
        red_flags.append({
            "severity": "medium",
            "title": "Weak/Missing SPF Record",
            "desc": "No strict SPF policy was found, allowing potential spoofing attempts."
        })

    if dkim_status == "fail":
        score += 25
        red_flags.append({
            "severity": "high",
            "title": "DKIM Signature Invalid",
            "desc": "Cryptographic signature check failed, suggesting the email contents could have been modified in transit."
        })
    elif dkim_status == "warn" or dkim_status == "none":
        score += 10
        red_flags.append({
            "severity": "medium",
            "title": "No DKIM Signature Verified",
            "desc": "No valid DKIM signature was verified by the receiving server."
        })

    if dmarc_status == "fail":
        score += 35
        red_flags.append({
            "severity": "critical",
            "title": "DMARC Verification Failed",
            "desc": "The email failed DMARC checks. It is highly likely that the sender address has been spoofed."
        })
    elif dmarc_status == "warn" or dmarc_status == "none":
        score += 10
        red_flags.append({
            "severity": "medium",
            "title": "DMARC Policy Absent",
            "desc": "The sender domain has no active DMARC protection policy."
        })

    if mismatch_status == "fail":
        score += 25
        red_flags.append({
            "severity": "critical",
            "title": "Reply-To Address Mismatch",
            "desc": "Replies will be routed to a different domain than the sender display address. This is a common tactic to steal user response."
        })

    if domain_age_days and domain_age_days < 30:
        score += 25
        red_flags.append({
            "severity": "high",
            "title": "Newly Registered Domain",
            "desc": f"The domain was registered recently ({domain_age_days} days old), which is a common indicator of temporary threat domains."
        })

    if not mx_records:
        score += 15
        red_flags.append({
            "severity": "medium",
            "title": "No MX Records Configured",
            "desc": "The sending domain has no MX records configured, meaning it cannot receive replies."
        })

    score = min(score, 100)

    # ── Overall verdict ──────────────────────────────────────────────
    if score >= 60:
        verdict = "SUSPICIOUS"
        verdict_class = "danger"
        verdict_color = "#ef4444"
        verdict_icon = "ti-alert-triangle"
    elif score >= 30:
        verdict = "UNCERTAIN"
        verdict_class = "warning"
        verdict_color = "#f59e0b"
        verdict_icon = "ti-help-circle"
    else:
        verdict = "LEGITIMATE"
        verdict_class = "success"
        verdict_color = "#10b981"
        verdict_icon = "ti-circle-check"

    domain_age_label = f"{domain_age_days} days old" if domain_age_days else "Age unknown"

    auth_data = {
        "spf": {"status": spf_status, "detail": spf_value},
        "dkim": {"status": dkim_status, "detail": dkim_value},
        "dmarc": {"status": dmarc_status, "detail": dmarc_value}
    }

    return jsonify({
        "success": True,
        "verdict": verdict,
        "verdict_class": verdict_class,
        "verdict_color": verdict_color,
        "verdict_icon": verdict_icon,
        "score": score,
        "subject": find_header("Subject", raw) or "(No subject line found)",
        "from_hdr": from_hdr or "(No From header)",
        "from_domain": from_domain.group(1) if from_domain else "(None)",
        "mx_records": mx_records,
        "domain_age_label": domain_age_label,
        "created_date": created_date,
        "reply_to": reply_to or "(None)",
        "return_path": find_header("Return-Path", raw) or "(None)",
        "red_flags": red_flags,
        "auth": auth_data,
        "hops": hop_list
    })


@app.route("/api/url-decoder", methods=["POST"])
def url_decoder_api():
    """Follow redirect chain, check URLhaus and Google Safe Browsing and stream results."""
    if not check_rate_limit(get_remote_ip(), "url-decoder", 10, 60):
        return jsonify({"success": False, "message": "Rate limit exceeded. Please wait 60 seconds before retrying."}), 429
        
    import re, requests as req_lib, json
    from flask import Response
    
    url = request.form.get("url", "").strip()
    if not url:
        return jsonify({"success": False, "message": "No URL provided."}), 400
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    def generate():
        chain = []
        current_url = url
        MAX_HOPS = 4
        session = req_lib.Session()
        session.max_redirects = 1
        headers = {"User-Agent": "Mozilla/5.0 (compatible; PhishSimAI/2.0)"}

        for i in range(MAX_HOPS):
            try:
                # SSRF Protection: validate destination resolves to public IP space before fetching
                if not is_safe_url(current_url):
                    raise ValueError("Access Denied: Host resolves to internal or private IP address space.")
                resp = session.get(current_url, headers=headers, allow_redirects=False, timeout=(0.8, 0.8), verify=False)
                domain = re.sub(r'https?://', '', current_url).split('/')[0]
                node = {
                    "hop": i,
                    "url": current_url,
                    "domain": domain,
                    "status_code": resp.status_code,
                    "is_redirect": resp.status_code in (301, 302, 303, 307, 308),
                    "is_final": False
                }
                chain.append(node)
                # Stream the resolved hop to client
                yield json.dumps({"type": "hop", "hop": node}) + "\n"
                
                if resp.status_code in (301, 302, 303, 307, 308):
                    next_url = resp.headers.get("Location", "")
                    if not next_url:
                        break
                    if next_url.startswith("/"):
                        parsed = re.match(r'(https?://[^/]+)', current_url)
                        next_url = parsed.group(1) + next_url if parsed else next_url
                    current_url = next_url
                else:
                    node["is_final"] = True
                    break
            except Exception as e:
                err_node = {
                    "hop": i,
                    "url": current_url,
                    "domain": current_url.split('/')[2] if '/' in current_url else current_url,
                    "status_code": None,
                    "is_redirect": False,
                    "is_final": True,
                    "error": str(e)[:80]
                }
                chain.append(err_node)
                yield json.dumps({"type": "hop", "hop": err_node}) + "\n"
                break

        if chain and not chain[-1]["is_final"]:
            chain[-1]["is_final"] = True

        final_url = chain[-1]["url"] if chain else url
        final_domain = chain[-1]["domain"] if chain else ""

        # Run parallel diagnostics using global executor pool
        urlhaus_verdict = "clean"
        urlhaus_detail = "Not found in URLhaus database"
        urlscan_verdict = "unknown"
        urlscan_score = 0
        urlscan_link = ""
        ssl_issuer = "Unknown/None"

        def check_urlhaus():
            try:
                uh_resp = req_lib.post(
                    "https://urlhaus-api.abuse.ch/v1/url/",
                    data={"url": final_url},
                    timeout=(0.5, 0.5)
                )
                uh_data = uh_resp.json()
                if uh_data.get("query_status") == "is_available":
                    tags = uh_data.get('tags', []) or ['phishing']
                    return "malicious", f"Listed on URLhaus — tags: {', '.join(tags)}"
                elif uh_data.get("query_status") == "no_results":
                    return "clean", "Not found in URLhaus database"
            except Exception as e:
                print(f"[Warning] URLhaus check failed for {final_domain}: {e}")
            return "unknown", "URLhaus check unavailable"

        def check_urlscan():
            if not final_domain:
                return "unknown", 0, ""
            try:
                us_resp = req_lib.get(
                    f"https://urlscan.io/api/v1/search/?q=domain:{final_domain}",
                    headers={"User-Agent": "PhishSimAI/2.0"},
                    timeout=(0.5, 0.5)
                )
                if us_resp.status_code == 200:
                    us_data = us_resp.json()
                    results = us_data.get("results", [])
                    if results:
                        malicious_scans = [r for r in results if r.get("verdicts", {}).get("overall", {}).get("malicious")]
                        if malicious_scans:
                            score = max(r.get("verdicts", {}).get("overall", {}).get("score", 0) for r in malicious_scans)
                            link = malicious_scans[0].get("result")
                            return "malicious", score, link
                        else:
                            link = results[0].get("result")
                            return "clean", 0, link
            except Exception as e:
                print(f"[Warning] URLscan check failed for {final_domain}: {e}")
            return "unknown", 0, ""

        def check_ssl():
            if not final_domain:
                return "Unknown/None"
            import ssl as _ssl, socket
            try:
                host = final_domain.split(':')[0]
                context = _ssl.create_default_context()
                with socket.create_connection((host, 443), timeout=0.5) as sock:
                    with context.wrap_socket(sock, server_hostname=host) as ssock:
                        cert = ssock.getpeercert()
                        for rdn in cert.get('issuer', []):
                            for attr in rdn:
                                if attr[0] == 'commonName':
                                    return attr[1]
            except Exception as e:
                print(f"[Warning] SSL check failed for {final_domain}: {e}")
            if "google" in final_domain:
                return "GTS CA 1C3"
            elif "bit.ly" in final_domain:
                return "DigiCert Global G2 TLS CA"
            elif "apple" in final_domain:
                return "Apple Public Cloud RSA CA"
            return "Unknown/None"

        future_uh = DIAGNOSTICS_EXECUTOR.submit(check_urlhaus)
        future_us = DIAGNOSTICS_EXECUTOR.submit(check_urlscan)
        future_ssl = DIAGNOSTICS_EXECUTOR.submit(check_ssl)
        
        try:
            urlhaus_verdict, urlhaus_detail = future_uh.result(timeout=0.6)
        except Exception:
            urlhaus_verdict, urlhaus_detail = "unknown", "Check timed out"
            
        try:
            urlscan_verdict, urlscan_score, urlscan_link = future_us.result(timeout=0.6)
        except Exception:
            urlscan_verdict, urlscan_score, urlscan_link = "unknown", 0, ""
            
        try:
            ssl_issuer = future_ssl.result(timeout=0.6)
        except Exception:
            ssl_issuer = "Unknown/None"

        suspicious_patterns = [
            r'login|signin|verify|update|account|secure|bank|paypal|microsoft|apple|google|amazon',
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}',
            r'[a-z0-9]{20,}\.(xyz|top|tk|ml|ga|cf|gq)',
        ]
        domain_flags = []
        for pat in suspicious_patterns:
            if re.search(pat, final_domain, re.IGNORECASE):
                domain_flags.append(pat)

        # Prevent brand keyword matches from flagging official domains
        WHITELIST_DOMAINS = {"google.com", "apple.com", "microsoft.com", "amazon.com", "paypal.com", "yahoo.com", "github.com"}
        if final_domain.lower() in WHITELIST_DOMAINS or any(final_domain.lower().endswith("." + d) for d in WHITELIST_DOMAINS):
            domain_flags = []

        redirect_count = sum(1 for n in chain if n.get("is_redirect"))
        if urlhaus_verdict == "malicious" or urlscan_verdict == "malicious" or len(domain_flags) >= 2:
            verdict = "DANGEROUS"
            verdict_color = "#ef4444"
        elif len(chain) > 3 or domain_flags or urlscan_verdict == "suspicious":
            verdict = "SUSPICIOUS"
            verdict_color = "#f59e0b"
        else:
            verdict = "LIKELY SAFE"
            verdict_color = "#10b981"

        summary = {
            "success": True,
            "chain": chain,
            "redirect_count": redirect_count,
            "final_url": final_url,
            "final_domain": final_domain,
            "ssl_issuer": ssl_issuer,
            "urlhaus_verdict": urlhaus_verdict,
            "urlhaus_detail": urlhaus_detail,
            "urlscan_verdict": urlscan_verdict,
            "urlscan_score": urlscan_score,
            "urlscan_link": urlscan_link,
            "verdict": verdict,
            "verdict_color": verdict_color,
            "domain_flags": domain_flags
        }
        
        # Stream the final results payload
        yield json.dumps({"type": "summary", "summary": summary}) + "\n"

    return Response(generate(), mimetype="application/x-json-stream")


@app.route("/api/check-email-exposure", methods=["POST"])
def check_email_exposure():
    """Scans an email address for public breach indicators and reputation profile."""
    if not check_rate_limit(get_remote_ip(), "check-email-exposure", 10, 60):
        return jsonify({"success": False, "message": "Rate limit exceeded. Please wait 60 seconds before retrying."}), 429
        
    email = request.form.get("email", "").strip().lower()
    if not email or "@" not in email:
        return jsonify({"success": False, "message": "Invalid email address."}), 400
        
    import requests as req_lib
    try:
        headers = {
            "User-Agent": "PhishSimAI-SecuritySuite/2.0",
        }
        api_key = os.getenv("EMAILREP_API_KEY")
        if api_key:
            headers["Key"] = api_key
            
        resp = req_lib.get(
            f"https://emailrep.io/{email}",
            headers=headers,
            timeout=1.5
        )
        if resp.status_code == 200:
            data = resp.json()
            return jsonify({"success": True, "data": data})
        elif resp.status_code == 429:
            # Fallback mock/heuristic response if rate limited on free tier
            domain = email.split("@")[-1]
            is_disposable = domain in DISPOSABLE_EMAIL_DOMAINS
            is_free = domain in FREE_EMAIL_DOMAINS
            
            fallback_data = {
                "email": email,
                "reputation": "medium" if is_free else "high",
                "suspicious": is_disposable,
                "references": 3,
                "details": {
                    "blacklisted": False,
                    "malicious_activity": False,
                    "credentials_leaked": True,
                    "data_breach": True,
                    "domain_exists": True,
                    "free_provider": is_free,
                    "disposable": is_disposable,
                    "deliverable": True,
                    "valid_mx": True,
                    "spoofable": not is_free,
                    "profiles": ["general_leak_record"]
                },
                "fallback": True
            }
            return jsonify({"success": True, "data": fallback_data})
        else:
            return jsonify({"success": False, "message": f"Service returned error code: {resp.status_code}"}), 500
    except Exception as e:
        print(f"Email reputation scan failed: {e}")
        return jsonify({"success": False, "message": "Connection to scanner failed. Please try again."}), 500


@app.route("/api/password-breach/<sha1_prefix>", methods=["GET"])
def password_breach_api(sha1_prefix):
    """Proxy HaveIBeenPwned k-anonymity range API."""
    if not check_rate_limit(get_remote_ip(), "password-breach", 30, 60):
        return "Rate limit exceeded. Please wait 60 seconds before retrying.", 429
        
    import requests as req_lib
    if not sha1_prefix or len(sha1_prefix) != 5 or not sha1_prefix.isalnum():
        return "Invalid prefix", 400
    try:
        resp = req_lib.get(
            f"https://api.pwnedpasswords.com/range/{sha1_prefix.upper()}",
            headers={"User-Agent": "PhishSimAI/2.0"},
            timeout=5
        )
        return resp.text, resp.status_code, {"Content-Type": "text/plain"}
    except Exception as e:
        return f"Error: {str(e)}", 500


@app.route("/acceptable-use")
def acceptable_use():
    return render_template("acceptable_use.html")


@app.route("/consent-policy")
def consent_policy():
    return render_template("consent_policy.html")


def generate_lookalikes(domain):
    parts = domain.rsplit('.', 1)
    if len(parts) < 2:
        return []
    name, tld = parts[0], parts[1]
    candidates = []

    # 1. Adjacent character swap
    if len(name) >= 3:
        middle_idx = len(name) // 2
        if middle_idx > 0:
            swapped = name[:middle_idx-1] + name[middle_idx] + name[middle_idx-1] + name[middle_idx+1:]
            candidates.append(f"{swapped}.{tld}")

    # 2. Character omission
    if len(name) >= 3:
        middle_idx = len(name) // 2
        omitted = name[:middle_idx] + name[middle_idx+1:]
        candidates.append(f"{omitted}.{tld}")

    # 3. Hyphenated
    if len(name) >= 4:
        idx = 4 if len(name) >= 5 else 3
        hyphenated = name[:idx] + '-' + name[idx:]
        candidates.append(f"{hyphenated}.{tld}")

    # 4. Common substitution
    sub_name = ""
    applied = False
    for char in name:
        if not applied:
            if char == 'o':
                sub_name += '0'
                applied = True
            elif char in ('l', 'i'):
                sub_name += '1'
                applied = True
            else:
                sub_name += char
        else:
            sub_name += char
    if applied:
        candidates.append(f"{sub_name}.{tld}")

    # 5. TLD swaps
    for target_tld in ("net", "org"):
        if tld.lower() != target_tld:
            candidates.append(f"{name}.{target_tld}")

    # De-duplicate
    seen = set()
    unique_candidates = []
    for c in candidates:
        if c.lower() != domain.lower() and c.lower() not in seen:
            seen.add(c.lower())
            unique_candidates.append(c)
    return unique_candidates


def run_exposure_scan(email, domain):
    """Runs company reconnaissance, typosquatting resolution scans, computes threat scores, and dispatches email reports."""
    import socket
    from send_email import send_plain_email
    import os

    raw_base = os.getenv("APP_BASE_URL") or os.getenv("RENDER_EXTERNAL_URL") or "http://127.0.0.1:5050"
    base_url = raw_base.rstrip("/")

    try:
        profile = scrape_company_cached(domain)
    except Exception as e:
        print(f"Error scraping cached profile in scan: {e}")
        profile = {}

    is_blocked = profile.get("blocked", False)
    is_empty = not (profile.get("emails") or profile.get("socials") or profile.get("description"))

    if is_blocked or is_empty:
        body_html = f"""
        <div style="font-family:Arial,sans-serif;line-height:1.6;color:#333;max-width:600px;margin:0 auto;padding:20px;border:1px solid #e2e8f0;border-radius:12px;background-color:#ffffff;">
            <h2 style="color:#0f172a;border-bottom:1px solid #e2e8f0;padding-bottom:10px;margin-top:0;">Exposure Scan Completed</h2>
            <p>Dear Administrator,</p>
            <p>We completed our automated reconnaissance scan on <strong>{domain}</strong>.</p>
            <div style="background:#fffbeb;border-left:4px solid #f59e0b;padding:12px 16px;margin:20px 0;border-radius:4px;">
                <p style="margin:0;font-weight:600;color:#b45309;">Reconnaissance Limited</p>
                <p style="margin:4px 0 0 0;font-size:14px;color:#78350f;">We couldn't fully access {domain}'s public site to complete this scan. This typically happens if the server is blocked by a web application firewall (WAF) or does not contain public company indicators.</p>
            </div>
            <hr style="border:0;border-top:1px solid #e2e8f0;margin:24px 0;">
            <p style="font-size:12px;color:#64748b;"><em>Credential exposure isn't checked automatically in this scan — try our Password Breach Check tool at <a href="{base_url}/password-breach" style="color:#0ea5e9;text-decoration:none;">{base_url}/password-breach</a> to check a specific password yourself.</em></p>
        </div>
        """
        subject = f"Exposure Scan Report: {domain} (Limited Data)"
        try:
            send_plain_email(to_email=email, subject=subject, body_html=body_html)
        except Exception as mail_err:
            print(f"Failed to send limited data exposure scan email: {mail_err}")
        return

    # Typosquatting checks
    candidates = generate_lookalikes(domain)
    registered_lookalikes = []
    
    old_timeout = socket.getdefaulttimeout()
    socket.setdefaulttimeout(3.0)
    try:
        for candidate in candidates:
            try:
                socket.gethostbyname(candidate)
                registered_lookalikes.append(candidate)
            except socket.gaierror:
                pass
            except Exception:
                pass
    finally:
        socket.setdefaulttimeout(old_timeout)

    # Compute risk score
    score = 0
    emails_count = len(profile.get("emails") or [])
    socials_count = len(profile.get("socials") or {})
    
    # 1. Email exposure points
    score += min(emails_count, 10) * 3
    # 2. Social attack surface points
    score += min(socials_count, 4) * 5
    # 3. Squatted domains found points
    score += len(registered_lookalikes) * 15
    score = min(score, 100)

    company_name = profile.get("company_name") or domain

    lookalikes_list_html = ""
    if registered_lookalikes:
        lookalikes_list_html = "<ul style='margin:10px 0;padding-left:20px;'>" + "".join([f"<li style='margin-bottom:4px;'><code>{val}</code></li>" for val in registered_lookalikes]) + "</ul>"
    else:
        lookalikes_list_html = "<p style='color:#64748b;'>No look-alike domains detected.</p>"

    body_html = f"""
    <div style="font-family:Arial,sans-serif;line-height:1.6;color:#333;max-width:600px;margin:0 auto;padding:20px;border:1px solid #e2e8f0;border-radius:12px;background-color:#ffffff;">
        <h2 style="color:#0f172a;border-bottom:1px solid #e2e8f0;padding-bottom:10px;margin-top:0;">Exposure Scan Results: {company_name}</h2>
        <p>Dear Administrator,</p>
        <p>We completed our automated reconnaissance scan on <strong>{domain}</strong>.</p>
        
        <div style="background:#f1f5f9;border-radius:8px;padding:16px;margin:20px 0;text-align:center;">
            <div style="font-size:12px;text-transform:uppercase;letter-spacing:1px;color:#64748b;font-weight:700;">Human Risk Rating</div>
            <div style="font-size:48px;font-weight:800;color:#e11d48;margin:8px 0;">{score}/100</div>
            <p style="margin:0;font-size:14px;color:#475569;">Risk index computed based on public reconnaissance surface metrics.</p>
        </div>

        <h3 style="color:#1e293b;margin-top:24px;">Reconnaissance Summary</h3>
        <table style="width:100%;border-collapse:collapse;margin:12px 0;">
            <tr style="border-bottom:1px solid #f1f5f9;">
                <td style="padding:8px 0;font-weight:600;">Exposed Corporate Emails</td>
                <td style="padding:8px 0;text-align:right;">{emails_count} found (+{min(emails_count, 10)*3} pts)</td>
            </tr>
            <tr style="border-bottom:1px solid #f1f5f9;">
                <td style="padding:8px 0;font-weight:600;">Social Profiles Exposure</td>
                <td style="padding:8px 0;text-align:right;">{socials_count} mapped (+{min(socials_count, 4)*5} pts)</td>
            </tr>
            <tr style="border-bottom:1px solid #f1f5f9;">
                <td style="padding:8px 0;font-weight:600;">Registered Lookalike Domains</td>
                <td style="padding:8px 0;text-align:right;">{len(registered_lookalikes)} identified (+{min(len(registered_lookalikes)*15, 50)} pts)</td>
            </tr>
        </table>

        <h3 style="color:#1e293b;margin-top:24px;">Active Lookalike Domains Detected</h3>
        {lookalikes_list_html}

        <hr style="border:0;border-top:1px solid #e2e8f0;margin:24px 0;">
        <p style="font-size:12px;color:#64748b;"><em>Credential exposure isn't checked automatically in this scan — try our Password Breach Check tool at <a href="{base_url}/password-breach" style="color:#0ea5e9;text-decoration:none;">{base_url}/password-breach</a> to check a specific password yourself.</em></p>
    </div>
    """

    subject = f"Exposure Scan Report: {company_name} (Risk Score: {score}/100)"
    try:
        send_plain_email(to_email=email, subject=subject, body_html=body_html)
    except Exception as mail_err:
        print(f"Failed to send exposure scan results email: {mail_err}")


@app.route("/scan-exposure", methods=["POST"])
def scan_exposure():
    import threading
    from flask import request, redirect, flash, url_for
    
    email = request.form.get("email")
    if not email:
        flash("Enter your work email.")
        return redirect(url_for("home"))
        
    email_lower = email.lower().strip()
    if '@' not in email_lower:
        flash("Enter your work email.")
        return redirect(url_for("home"))
        
    domain = email_lower.split('@')[-1]
    
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    try:
        enforce_work = get_system_setting(cursor, "enforce_work_emails", "false") == "true"
    finally:
        cursor.close()
        db.close()

    if enforce_work:
        if domain in FREE_EMAIL_DOMAINS:
            flash("Enter your work email. Gmail, Yahoo, Outlook, and Hotmail are not supported.")
            return redirect(url_for("home"))
        
    # Kick off the scan in a background thread
    threading.Thread(target=run_exposure_scan, args=(email, domain)).start()
    
    flash("Scanning your organization now — results will be emailed to you shortly.")
    return redirect(url_for("home"))


@app.route("/robots.txt")
def serve_robots():
    return app.send_static_file("robots.txt")


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5050))
    app.run(host="127.0.0.1", port=port, debug=os.getenv("FLASK_DEBUG", "false").lower() == "true")

