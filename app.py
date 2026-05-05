from flask import Flask, render_template, request, redirect, url_for, send_file, session, flash
from dotenv import load_dotenv
import os
import mysql.connector
import csv
import io
import re
import time
import uuid
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from functools import wraps
import smtplib
from werkzeug.security import generate_password_hash, check_password_hash
from ai_engine.report_agent import build_campaign_report
from send_email import get_email_settings, resolve_email_provider, send_phishing_email

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-change-me")
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=(
        os.getenv("FLASK_COOKIE_SECURE", "").strip().lower() in ("1", "true", "yes", "on")
        or any(os.getenv(name) for name in ("RENDER", "RENDER_EXTERNAL_URL", "DYNO", "K_SERVICE"))
    ),
    PERMANENT_SESSION_LIFETIME=3600,
)
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

# --- Database Connection Helper ---
# Perfection Tip: Use a connection pool in production, but for now we optimize manual connections
def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", 3306)),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "phishsim_db"),
        charset="utf8mb4",
        collation="utf8mb4_unicode_ci",
        ssl_disabled=os.getenv("DB_SSL_DISABLED", "False").lower() == "true"
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

    for ddl in [
        "ALTER TABLE campaigns ADD COLUMN user_id INT",
        "ALTER TABLE campaigns ADD COLUMN delivery_mode VARCHAR(20) DEFAULT 'local'",
        "ALTER TABLE users ADD COLUMN email_verified BOOLEAN DEFAULT FALSE",
        "ALTER TABLE users ADD COLUMN verification_token VARCHAR(80)"
    ]:
        try:
            cursor.execute(ddl)
        except Exception:
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
            status VARCHAR(50) DEFAULT 'draft',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    try:
        cursor.execute("ALTER TABLE campaigns CHANGE target_domain company_domain VARCHAR(255)")
    except Exception:
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
    except Exception:
        pass

@app.before_request
def bootstrap_schema():
    if app.config.get("AUTH_SCHEMA_READY"):
        return
    try:
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        ensure_auth_schema(cursor)
        ensure_core_tables(cursor)
        db.commit()
        cursor.close()
        db.close()
        app.config["AUTH_SCHEMA_READY"] = True
    except Exception as e:
        print(f"Auth schema check failed: {e}")


@app.after_request
def add_security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    return response

def send_verification_email(to_email, token):
    settings = get_email_settings("smtp")
    if not settings["host"] or not settings["user"] or not settings["password"]:
        return False, "SMTP is not configured for account verification."

    base_url = os.getenv("APP_BASE_URL", "http://127.0.0.1:5000").rstrip("/")
    verify_url = f"{base_url}/verify-email/{token}"
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Verify your PhishSim AI account"
    msg["From"] = f"PhishSim AI <{settings['from_email']}>"
    msg["To"] = to_email
    msg.attach(MIMEText(
        f"<p>Welcome to PhishSim AI.</p><p>Verify your account before creating campaigns:</p><p><a href='{verify_url}'>Verify email</a></p>",
        "html"
    ))
    try:
        smtp_class = smtplib.SMTP_SSL if settings["encryption"] == "ssl" else smtplib.SMTP
        with smtp_class(settings["host"], settings["port"], timeout=float(os.getenv("SMTP_TIMEOUT_SECONDS", "6"))) as server:
            if settings["encryption"] == "starttls":
                server.ehlo()
                server.starttls()
                server.ehlo()
            server.login(settings["user"], settings["password"])
            server.send_message(msg)
        return True, None
    except Exception as e:
        return False, str(e)


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
        cursor.execute("SELECT id, name, email, role, company_domain, email_verified FROM users WHERE id = %s", (user_id,))
        g.user = cursor.fetchone()
        cursor.close()
        db.close()
        return g.user
    except Exception as e:
        print(f"Current user lookup failed: {e}")
        return None

@app.context_processor
def inject_current_user():
    return {"current_user": current_user()}

def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped

def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = current_user()
        if not user or user["role"] != "admin":
            return "Forbidden", 403
        return view(*args, **kwargs)
    return wrapped

def user_can_access_campaign(cursor, campaign_id, user):
    if user["role"] == "admin":
        cursor.execute("SELECT * FROM campaigns WHERE id = %s", (campaign_id,))
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
        "ALTER TABLE emails_sent ADD COLUMN body_html TEXT"
    ]:
        try:
            cursor.execute(ddl)
        except Exception:
            pass

    for ddl in [
        "CREATE INDEX idx_emails_sent_campaign_status ON emails_sent (campaign_id, status)",
        "CREATE INDEX idx_emails_sent_campaign_tracking ON emails_sent (campaign_id, tracking_id)",
        "CREATE INDEX idx_emails_sent_tracking ON emails_sent (tracking_id)"
    ]:
        try:
            cursor.execute(ddl)
        except Exception:
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
    for ddl in [
        "CREATE INDEX idx_events_tracking_type ON events (tracking_id, event_type)",
        "CREATE INDEX idx_events_tracking ON events (tracking_id)"
    ]:
        try:
            cursor.execute(ddl)
        except Exception:
            pass

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
    return changed

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
        WHERE campaign_id = %s AND COALESCE(status, 'sent') = 'sent'
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
    return render_template("home.html")

@app.route("/demo-login")
def demo_login():
    """Instantly creates a populated demo account and logs the user in."""
    import uuid
    import random
    from datetime import datetime, timedelta
    
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    
    demo_email = f"demo_{uuid.uuid4().hex[:8]}@phishsim.ai"
    cursor.execute("""
        INSERT INTO users (name, email, password_hash, role, company_domain)
        VALUES (%s, %s, %s, 'company_user', 'demo-corp.com')
    """, ("Demo Admin", demo_email, generate_password_hash("demo_pass")))
    
    user_id = cursor.lastrowid
    
    # Preload Campaign 1 (Launched & Successful)
    cursor.execute("""
        INSERT INTO campaigns (user_id, name, company_domain, scenario_type, delivery_mode, status)
        VALUES (%s, 'Q3 Finance Phish (Simulated)', 'demo-corp.com', 'ceo_fraud', 'local', 'launched')
    """, (user_id,))
    camp1_id = cursor.lastrowid
    
    # Preload Campaign 2 (Launched & Completed)
    cursor.execute("""
        INSERT INTO campaigns (user_id, name, company_domain, scenario_type, delivery_mode, status)
        VALUES (%s, 'Mandatory HR Training (Simulated)', 'demo-corp.com', 'hr_update', 'smtp', 'launched')
    """, (user_id,))
    camp2_id = cursor.lastrowid
    
    # Populate Fake Emails & Events for Camp 1
    ensure_email_tracking_table(cursor)
    ensure_events_table(cursor)
    
    for i in range(1, 46): # 45 fake employees
        trk_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO emails_sent (campaign_id, tracking_id, recipient_email, status, educational_breakdown, subject, sender_name, body_html)
            VALUES (%s, %s, %s, 'sent', 'This email used false urgency from the CEO. Always verify wire transfers via phone.', %s, %s, %s)
        """, (camp1_id, trk_id, f"employee{i}@demo-corp.com", "URGENT: Wire Transfer Approval Needed Today", "CEO's Office", f"<p>Dear employee,</p><p>I am in a meeting all day and need you to process an urgent wire transfer for our new vendor. The payment must go out before 3 PM.</p><p>Please click here to <a href='TRACKING_LINK'>review the invoice and wire details</a>.</p><p>Let me know once it's done.</p>"))
        
        # 60% Open Rate
        if random.random() < 0.60:
            cursor.execute("INSERT INTO events (tracking_id, event_type, ip_address) VALUES (%s, 'open', '127.0.0.1')", (trk_id,))
            
            # 30% Click Rate (of those who opened)
            if random.random() < 0.30:
                cursor.execute("INSERT INTO events (tracking_id, event_type, ip_address) VALUES (%s, 'click', '127.0.0.1')", (trk_id,))
            
            # 10% Report Rate
            elif random.random() < 0.10:
                cursor.execute("INSERT INTO events (tracking_id, event_type, ip_address) VALUES (%s, 'report', '127.0.0.1')", (trk_id,))
                
    # Populate Fake Emails & Events for Camp 2
    for i in range(1, 31): # 30 fake employees
        trk_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO emails_sent (campaign_id, tracking_id, recipient_email, status, educational_breakdown, subject, sender_name, body_html)
            VALUES (%s, %s, %s, 'sent', 'This email impersonated HR and created a false compliance deadline.', %s, %s, %s)
        """, (camp2_id, trk_id, f"staff{i}@demo-corp.com", "Action Required: Annual HR Benefits Update", "Human Resources", f"<p>Hello,</p><p>Our records indicate that you have not yet confirmed your benefits enrollment for the upcoming year. The deadline is tomorrow at 5 PM.</p><p>Failure to complete this may result in a lapse of coverage.</p><p>Please log in immediately to <a href='TRACKING_LINK'>update your enrollment status</a>.</p><p>Regards,<br>HR Department</p>"))
        
        # 80% Open Rate (HR is tricky!)
        if random.random() < 0.80:
            cursor.execute("INSERT INTO events (tracking_id, event_type, ip_address) VALUES (%s, 'open', '127.0.0.1')", (trk_id,))
            
            # 40% Click Rate
            if random.random() < 0.40:
                cursor.execute("INSERT INTO events (tracking_id, event_type, ip_address) VALUES (%s, 'click', '127.0.0.1')", (trk_id,))
            
            # 5% Report Rate
            elif random.random() < 0.05:
                cursor.execute("INSERT INTO events (tracking_id, event_type, ip_address) VALUES (%s, 'report', '127.0.0.1')", (trk_id,))
                
    db.commit()
    cursor.close()
    db.close()
    
    session["user_id"] = user_id
    flash("Welcome to the PhishSim Demo! We've pre-loaded some active campaigns and statistics for you.", "success")
    return redirect(url_for("dashboard"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
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
            session.permanent = True
            session["user_id"] = user["id"]
            session["role"] = user["role"]
            return redirect(request.args.get("next") or url_for("dashboard"))

        record_failed_login(login_key)
        flash("Invalid email or password.")

    return render_template("login.html")

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        company_domain = normalize_domain(request.form.get("company_domain", ""))

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
            session["role"] = user["role"]
            sent, error = send_verification_email(email, token)
            if sent:
                flash("Account created. A verification link was sent to your email; you can still test campaigns before verifying.")
            else:
                flash(f"Account created, but verification email could not be sent: {error}")
            return redirect(url_for("dashboard"))
        except Exception as e:
            flash(f"Signup failed: {e}")
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

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))

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
    finally:
        cursor.close()
        db.close()
        
    return render_template("profile.html", user=user, stats=stats)

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
            flash(f"Could not create user: {e}")
        cursor.close()
        db.close()
        return redirect(url_for("manage_users"))

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT id, name, email, role, company_domain, created_at FROM users ORDER BY id DESC")
    users = cursor.fetchall()
    cursor.close()
    db.close()
    return render_template("users.html", users=users)

@app.route("/delete-user/<int:user_id>", methods=["POST"])
@admin_required
def delete_user(user_id):
    db = get_db_connection()
    cursor = db.cursor()
    try:
        # Don't let the user delete themselves
        if user_id == session.get("user_id"):
            flash("You cannot delete your own account.")
        else:
            cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
            db.commit()
            flash("User deleted successfully.")
    except Exception as e:
        flash(f"Error deleting user: {e}")
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
@login_required
def dashboard():
    user = current_user()
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    try:
        if ensure_email_schema_once(cursor):
            db.commit()

        # 1. FETCH ALL CAMPAIGNS WITH AGGREGATED METRICS IN ONE SINGLE QUERY (PERFECTION!)
        # This replaces the N+1 problem (looping through campaigns and running queries)
        if user["role"] == "admin":
            where_clause = "WHERE c.company_domain != 'demo-corp.com' OR c.company_domain IS NULL"
            params = ()
        else:
            where_clause = "WHERE c.user_id = %s"
            params = (user["id"],)

        sql = f"""
            SELECT 
                c.*,
                u.name AS owner_name,
                u.email AS owner_email,
                (SELECT COUNT(*) FROM employees e WHERE e.campaign_id = c.id) as employee_count,
                (SELECT COUNT(*) FROM emails_sent es WHERE es.campaign_id = c.id AND COALESCE(es.status, 'sent') = 'sent') as emails_sent,
                (SELECT COUNT(*) FROM emails_sent es WHERE es.campaign_id = c.id AND es.status = 'failed') as emails_failed,
                (SELECT error_message FROM emails_sent es WHERE es.campaign_id = c.id AND es.status = 'failed' ORDER BY id DESC LIMIT 1) as latest_error,
                COUNT(DISTINCT CASE WHEN e.event_type IN ('open', 'click', 'report') THEN e.tracking_id END) as opens,
                COUNT(DISTINCT CASE WHEN e.event_type = 'click' THEN e.tracking_id END) as clicks,
                COUNT(DISTINCT CASE WHEN e.event_type = 'report' THEN e.tracking_id END) as reports
            FROM campaigns c
            LEFT JOIN users u ON c.user_id = u.id
            LEFT JOIN emails_sent es_join ON c.id = es_join.campaign_id
            LEFT JOIN events e ON es_join.tracking_id = e.tracking_id
            {where_clause}
            GROUP BY c.id
            ORDER BY c.id DESC
        """
        cursor.execute(sql, params)
        campaigns = cursor.fetchall()
        total_employees = sum(c['employee_count'] for c in campaigns)
        total_opens = sum(c['opens'] for c in campaigns)
        total_clicks = sum(c['clicks'] for c in campaigns)
        total_reports = sum(c['reports'] for c in campaigns)
        
        global_risk = 0
        if total_opens > 0:
            global_risk = int((total_clicks / total_opens) * 100)
        elif total_employees > 0 and total_clicks > 0: # fallback
            global_risk = int((total_clicks / total_employees) * 100)
            
        global_stats = {
            "total_campaigns": len(campaigns),
            "total_employees": total_employees,
            "global_risk": global_risk,
            "total_reports": total_reports
        }
        
    except Exception as e:
        print(f"Dashboard query failed: {e}")
        campaigns = []
        global_stats = {"total_campaigns": 0, "total_employees": 0, "global_risk": 0, "total_reports": 0}
    finally:
        cursor.close()
        db.close()
        
    return render_template("dashboard.html", campaigns=campaigns, global_stats=global_stats)

# 1. ADD THIS ROUTE: This shows the "Create Campaign" page
@app.route("/new-campaign", methods=["GET", "POST"])
@login_required
def new_campaign():
    user = current_user()
    if request.method == "POST":
        # 1. Get data from the form
        name = request.form.get("campaign_name")
        domain = normalize_domain(request.form.get("company_domain") or user.get("company_domain") or email_domain(user.get("email")))
        scenario = request.form.get("scenario")
        consent = request.form.get("consent_confirmed")
        requested_mode = request.form.get("delivery_mode", "smtp" if user["role"] != "admin" else "local")
        delivery_mode = requested_mode if requested_mode in ("local", "smtp") else "smtp"
        if user["role"] != "admin":
            delivery_mode = "smtp"

        # 2. Security Check: Ensure consent was ticked
        if not consent:
            return "Error: You must confirm consent before launching.", 400
        if not domain:
            flash("Add a domain or testing label for this campaign.")
            return redirect(url_for("new_campaign"))
        if delivery_mode == "smtp" and not request.form.get("deliverability_confirmed"):
            flash("Confirm that your organization has allowlisted the simulation sender before using Live Mode.")
            return redirect(url_for("new_campaign"))

        # 3. Save to Database
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        sql = """
            INSERT INTO campaigns
                (name, company_domain, scenario_type, status, user_id, delivery_mode)
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        values = (name, domain, scenario, 'draft', user["id"], delivery_mode)
        cursor.execute(sql, values)
        db.commit()
        campaign_id = cursor.lastrowid
        cursor.close()
        db.close()

        # 4. Redirect to Dashboard (we will show the campaign there later)
        return redirect(url_for('dashboard'))

    return render_template("new_campaign.html", user=user)

# 2. ADD THIS ROUTE: Handles CSV upload for employees
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

    if "employee_csv" not in request.files:
        return "Error: No file uploaded.", 400
        
    file = request.files["employee_csv"]
    if file.filename == '':
        return "Error: No selected file.", 400

    if file:
        try:
            # Read and decode CSV, handle BOM if it came from Excel
            stream = io.StringIO(file.stream.read().decode("utf-8-sig"), newline=None)
            reader = csv.DictReader(stream)
            
            db = get_db_connection()
            cursor = db.cursor()
            sql = "INSERT INTO employees (name, email, department, title, campaign_id) VALUES (%s, %s, %s, %s, %s)"
            inserted = 0
            
            for row in reader:
                name = row.get("name", "")
                email = row.get("email", "").strip().lower()
                department = row.get("department", "")
                title = row.get("title", "")
                
                if email:
                    cursor.execute(sql, (name, email, department, title, campaign_id))
                    inserted += 1
                    
            db.commit()
            cursor.close()
            db.close()
            if inserted == 0:
                flash("No target emails were found in the CSV.")
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
            from osint.scraper import scrape_company
            company_profile = scrape_company(campaign["company_domain"])
        else:
            company_profile = {
                "company_name": campaign.get("company_domain", "Your Company"),
                "description": "",
                "writing_tone": "professional and urgent"
            }
        
        try:
            from ai_engine.email_gen import generate_phishing_email
        except ImportError:
            def generate_phishing_email(context, scenario):
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
                generation_cache[cache_key] = generate_phishing_email(template_context, campaign["scenario_type"])

            email_data = generation_cache[cache_key].copy()
            employee_name = emp.get("name") or "there"
            for key in ("subject", "sender_name", "body_html", "educational_breakdown"):
                if isinstance(email_data.get(key), str):
                    email_data[key] = email_data[key].replace("{employee_name}", employee_name)

            breakdown = email_data.get("educational_breakdown", "This was a simulated phishing email designed to test security awareness.")
            
            result = send_phishing_email(
                to_email=emp["email"],
                subject=email_data["subject"],
                sender_name=email_data["sender_name"],
                body_html=email_data["body_html"],
                tracking_id=tracking_id,
                delivery_mode=campaign.get("delivery_mode")
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
                    (campaign_id, tracking_id, recipient_email, status, error_message, educational_breakdown, subject, sender_name, body_html)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                    email_data["body_html"]
                ))
            except Exception as db_err:
                print(f"Tracking DB error: {db_err}")
                failed_count += 1

            if (sent_count + failed_count) % 5 == 0 or True:  # commit every email for reliability
                db.commit()
            
        if sent_count and failed_count:
            final_status = "launched_with_errors"
        elif sent_count:
            final_status = "launched"
        else:
            final_status = "failed"

        cursor.execute("UPDATE campaigns SET status = %s WHERE id = %s", (final_status, campaign_id))
        db.commit()
        cursor.close()
        db.close()
    except Exception as e:
        print(f"Background thread error: {e}")
        try:
            db = get_db_connection()
            cursor = db.cursor()
            cursor.execute("UPDATE campaigns SET status = 'failed' WHERE id = %s", (campaign_id,))
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
            cursor.execute("UPDATE campaigns SET delivery_mode = 'smtp' WHERE id = %s", (campaign_id,))
            db.commit()
            campaign["delivery_mode"] = "smtp"

        resolved_provider = resolve_email_provider(campaign.get("delivery_mode"))
        if resolved_provider == "smtp":
            settings = get_email_settings(campaign.get("delivery_mode"))
            if not settings["host"] or not settings["user"] or not settings["password"]:
                cursor.close()
                db.close()
                flash("SMTP delivery is not configured. Add SMTP_HOST, SMTP_USER, SMTP_PASS, and SMTP_FROM_EMAIL in .env.")
                return redirect(url_for("dashboard"))

        # Immediately set status to launching and show dashboard to user
        cursor.execute("UPDATE campaigns SET status = 'launching' WHERE id = %s", (campaign_id,))
        db.commit()
        cursor.close()
        db.close()
        
        # Start background thread
        thread = threading.Thread(target=process_campaign_background, args=(campaign_id,))
        thread.daemon = True
        thread.start()
        
        return redirect(url_for('dashboard'))
        
    except Exception as e:
        return f"Error launching campaign: {str(e)}", 500

# ==========================================
# PHASE 4: TRACKING ROUTES
# ==========================================

@app.route("/pixel/<tracking_id>.png")
def tracking_pixel(tracking_id):
    """Returns a 1x1 transparent PNG and logs the open event."""
    log_event(tracking_id, "open", request.remote_addr, request.user_agent.string)
    
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

@app.route("/click/<tracking_id>")
def track_click(tracking_id):
    """Logs click then shows fake landing page."""
    log_event(tracking_id, "click", request.remote_addr, request.user_agent.string)
    return render_template("fake_login.html", tracking_id=tracking_id)

@app.route("/simulated")
def simulation_reveal():
    """Shows after 3 seconds on fake login - explains the simulation."""
    tracking_id = request.args.get('id')
    scenario_type = None
    breakdown = None
    if tracking_id:
        try:
            db = get_db_connection()
            cursor = db.cursor(dictionary=True)
            cursor.execute("""
                SELECT c.scenario_type, e.educational_breakdown 
                FROM campaigns c
                JOIN emails_sent e ON c.id = e.campaign_id
                WHERE e.tracking_id = %s
            """, (tracking_id,))
            res = cursor.fetchone()
            if res:
                scenario_type = res['scenario_type'].replace('_', ' ').title()
                breakdown = res.get('educational_breakdown')
            cursor.close()
            db.close()
        except:
            pass
    return render_template("simulated.html", scenario=scenario_type, breakdown=breakdown)

@app.route("/report/<tracking_id>")
def report_email(tracking_id):
    """Handles the user clicking 'Report this email'."""
    log_event(tracking_id, "report", request.remote_addr, request.user_agent.string)
    return render_template("thank_you_for_reporting.html")

@app.route("/campaign-report/<int:campaign_id>")
@login_required
def campaign_report(campaign_id):
    """Shows an agentic campaign summary based on tracked behavior."""
    user = current_user()
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    try:
        if ensure_email_schema_once(cursor):
            db.commit()
        if not user_can_access_campaign(cursor, campaign_id, user):
            return "Campaign not found.", 404
        campaign = get_campaign_metrics(cursor, campaign_id)
    finally:
        cursor.close()
        db.close()

    if not campaign:
        return "Campaign not found.", 404

    report = build_campaign_report(campaign)
    return render_template("campaign_report.html", campaign=campaign, report=report)

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
    pdf.rect(10, 52, 190, 30, "DF")
    pdf.set_text_color(15, 23, 42)
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 8, clean_pdf_text(f"Calculated Risk Level: {report['risk_level']}"), ln=1)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(45, 8, clean_pdf_text(f"Delivery: {report['delivery_rate']}%"))
    pdf.cell(45, 8, clean_pdf_text(f"Open: {report['open_rate']}%"))
    pdf.cell(50, 8, clean_pdf_text(f"Click: {report['click_rate']}%"))
    pdf.cell(50, 8, clean_pdf_text(f"Report: {report['report_rate']}%"), ln=1)

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
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(15, 23, 42)
        table_cell(pdf, 62, 7, "Recipient", 30)
        table_cell(pdf, 25, 7, "Status", 10)
        table_cell(pdf, 90, 7, "Subject", 45, ln=1)
        pdf.set_font("Helvetica", "", 8.5)
        pdf.set_text_color(51, 65, 85)
        for row in email_rows[:8]:
            ensure_pdf_space(pdf, 10)
            table_cell(pdf, 62, 6, row.get("recipient_email", ""), 32)
            table_cell(pdf, 25, 6, row.get("status", ""), 10)
            table_cell(pdf, 90, 6, row.get("subject", ""), 48, ln=1)

    section_title(pdf, "Audit Notes")
    paragraph(pdf, "Use this PDF for internal security-awareness review only. PhishSim AI is designed for authorized simulations where the organization has permission to test the listed recipients.")
    paragraph(pdf, f"Campaign ID: {campaign_id}. Scenario: {(campaign.get('scenario_type') or 'unknown').replace('_', ' ')}. Delivery mode: {campaign.get('delivery_mode') or 'unknown'}.")

    if pdf.get_y() > 260:
        pdf.add_page()
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
    cloned_delivery_mode = campaign["delivery_mode"] if user["role"] == "admin" else "smtp"
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
        except:
            pass
            
        cursor.execute("DELETE FROM employees WHERE campaign_id = %s", (campaign_id,))
        cursor.execute("DELETE FROM campaigns WHERE id = %s", (campaign_id,))
        db.commit()
        cursor.close()
        db.close()
    except Exception as e:
        print(f"Delete failed: {e}")
    return redirect(url_for('dashboard'))

@app.route("/campaign-emails/<int:campaign_id>")
@login_required
def campaign_emails(campaign_id):
    """Shows a beautiful page of all AI-generated emails for a campaign."""
    user = current_user()
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
        base_url = os.getenv("APP_BASE_URL", "http://127.0.0.1:5000").rstrip("/")
        for email in emails:
            if email.get("body_html") and email.get("tracking_id"):
                tracking_url = f"{base_url}/click/{email['tracking_id']}"
                email["body_html"] = email["body_html"].replace("TRACKING_LINK", tracking_url)
        
        return render_template("campaign_emails.html", campaign=campaign, emails=emails)
    finally:
        cursor.close()
        db.close()

@app.route("/exit-demo")
def exit_demo():
    """Deletes the demo user and their campaigns, then logs out."""
    user = current_user()
    if user and user.get("company_domain") == "demo-corp.com":
        db = get_db_connection()
        cursor = db.cursor()
        try:
            # Delete campaigns and cascade
            cursor.execute("SELECT id FROM campaigns WHERE user_id = %s", (user["id"],))
            campaigns = cursor.fetchall()
            for (camp_id,) in campaigns:
                try:
                    cursor.execute("SELECT tracking_id FROM emails_sent WHERE campaign_id = %s", (camp_id,))
                    tracking_ids = [r[0] for r in cursor.fetchall()]
                    if tracking_ids:
                        format_strings = ','.join(['%s'] * len(tracking_ids))
                        cursor.execute(f"DELETE FROM events WHERE tracking_id IN ({format_strings})", tuple(tracking_ids))
                    cursor.execute("DELETE FROM emails_sent WHERE campaign_id = %s", (camp_id,))
                except: pass
                cursor.execute("DELETE FROM employees WHERE campaign_id = %s", (camp_id,))
            
            cursor.execute("DELETE FROM campaigns WHERE user_id = %s", (user["id"],))
            cursor.execute("DELETE FROM users WHERE id = %s", (user["id"],))
            db.commit()
        except Exception as e:
            print(f"Error exiting demo: {e}")
        finally:
            cursor.close()
            db.close()
    
    session.clear()
    flash("Demo ended successfully. Your temporary data has been cleared.", "success")
    return redirect(url_for("home"))

if __name__ == "__main__":
    app.run(debug=True)
