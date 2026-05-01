from flask import Flask, render_template, request, redirect, url_for, send_file, session, flash
from dotenv import load_dotenv
import os
import mysql.connector
import csv
import io
from datetime import datetime
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from ai_engine.report_agent import build_campaign_report

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-change-me")

# --- Database Connection Helper ---
# Perfection Tip: Use a connection pool in production, but for now we optimize manual connections
def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password=os.getenv("DB_PASSWORD"),
        database="phishsim_db",
        charset="utf8mb4",
        collation="utf8mb4_unicode_ci"
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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    for ddl in [
        "ALTER TABLE campaigns ADD COLUMN user_id INT",
        "ALTER TABLE campaigns ADD COLUMN delivery_mode VARCHAR(20) DEFAULT 'local'"
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
            SET password_hash = %s, role = 'admin'
            WHERE id = %s
        """, (generate_password_hash(admin_password), existing_admin["id"]))
    else:
        cursor.execute("""
            INSERT INTO users (name, email, password_hash, role, company_domain)
            VALUES (%s, %s, %s, %s, %s)
        """, (
            "Platform Admin",
            admin_email,
            generate_password_hash(admin_password),
            "admin",
            None
        ))

@app.before_request
def bootstrap_schema():
    if app.config.get("AUTH_SCHEMA_READY"):
        return
    try:
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        ensure_auth_schema(cursor)
        db.commit()
        cursor.close()
        db.close()
        app.config["AUTH_SCHEMA_READY"] = True
    except Exception as e:
        print(f"Auth schema check failed: {e}")

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
        cursor.execute("SELECT id, name, email, role, company_domain FROM users WHERE id = %s", (user_id,))
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
        "ALTER TABLE emails_sent ADD COLUMN error_message TEXT"
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

def get_campaign_metrics(cursor, campaign_id):
    """Loads one campaign with employee, delivery, and event metrics."""
    ensure_email_tracking_table(cursor)
    ensure_events_table(cursor)
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

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        ensure_auth_schema(cursor)
        db.commit()
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        cursor.close()
        db.close()

        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            session["role"] = user["role"]
            return redirect(request.args.get("next") or url_for("dashboard"))

        flash("Invalid email or password.")

    return render_template("login.html")

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        company_domain = request.form.get("company_domain", "").strip() or None

        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        ensure_auth_schema(cursor)
        try:
            cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
            if cursor.fetchone():
                flash("Email already registered.")
                return redirect(url_for('signup'))
                
            cursor.execute("""
                INSERT INTO users (name, email, password_hash, role, company_domain)
                VALUES (%s, %s, %s, %s, %s)
            """, (name, email, generate_password_hash(password), "company_user", company_domain))
            db.commit()
            cursor.execute("SELECT id, role FROM users WHERE email = %s", (email,))
            user = cursor.fetchone()
            session["user_id"] = user["id"]
            session["role"] = user["role"]
            return redirect(url_for("dashboard"))
        except Exception as e:
            flash(f"Signup failed: {e}")
        finally:
            cursor.close()
            db.close()
            
    return render_template("signup.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))

@app.route("/users", methods=["GET", "POST"])
@admin_required
def manage_users():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        role = request.form.get("role", "company_user")
        company_domain = request.form.get("company_domain", "").strip() or None

        if role not in ("admin", "company_user"):
            role = "company_user"

        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        ensure_auth_schema(cursor)
        try:
            cursor.execute("""
                INSERT INTO users (name, email, password_hash, role, company_domain)
                VALUES (%s, %s, %s, %s, %s)
            """, (name, email, generate_password_hash(password), role, company_domain))
            db.commit()
        except Exception as e:
            flash(f"Could not create user: {e}")
        cursor.close()
        db.close()
        return redirect(url_for("manage_users"))

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    ensure_auth_schema(cursor)
    db.commit()
    cursor.execute("SELECT id, name, email, role, company_domain, created_at FROM users ORDER BY id DESC")
    users = cursor.fetchall()
    cursor.close()
    db.close()
    return render_template("users.html", users=users)

@app.route("/dashboard")
@login_required
def dashboard():
    user = current_user()
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    try:
        # Schema guards - only run once or in background
        ensure_email_tracking_table(cursor)
        ensure_events_table(cursor)
        db.commit()

        # 1. FETCH ALL CAMPAIGNS WITH AGGREGATED METRICS IN ONE SINGLE QUERY (PERFECTION!)
        # This replaces the N+1 problem (looping through campaigns and running queries)
        if user["role"] == "admin":
            where_clause = ""
            params = ()
        else:
            where_clause = "WHERE c.user_id = %s"
            params = (user["id"],)

        sql = f"""
            SELECT 
                c.*,
                (SELECT COUNT(*) FROM employees e WHERE e.campaign_id = c.id) as employee_count,
                (SELECT COUNT(*) FROM emails_sent es WHERE es.campaign_id = c.id AND COALESCE(es.status, 'sent') = 'sent') as emails_sent,
                (SELECT COUNT(*) FROM emails_sent es WHERE es.campaign_id = c.id AND es.status = 'failed') as emails_failed,
                (SELECT error_message FROM emails_sent es WHERE es.campaign_id = c.id AND es.status = 'failed' ORDER BY id DESC LIMIT 1) as latest_error,
                COUNT(DISTINCT CASE WHEN e.event_type IN ('open', 'click', 'report') THEN e.tracking_id END) as opens,
                COUNT(DISTINCT CASE WHEN e.event_type = 'click' THEN e.tracking_id END) as clicks,
                COUNT(DISTINCT CASE WHEN e.event_type = 'report' THEN e.tracking_id END) as reports
            FROM campaigns c
            LEFT JOIN emails_sent es_join ON c.id = es_join.campaign_id
            LEFT JOIN events e ON es_join.tracking_id = e.tracking_id
            {where_clause}
            GROUP BY c.id
            ORDER BY c.id DESC
        """
        cursor.execute(sql, params)
        campaigns = cursor.fetchall()
        
    except Exception as e:
        print(f"Dashboard query failed: {e}")
        campaigns = []
    finally:
        cursor.close()
        db.close()
        
    return render_template("dashboard.html", campaigns=campaigns)

# 1. ADD THIS ROUTE: This shows the "Create Campaign" page
@app.route("/new-campaign", methods=["GET", "POST"])
@login_required
def new_campaign():
    user = current_user()
    if request.method == "POST":
        # 1. Get data from the form
        name = request.form.get("campaign_name")
        domain = request.form.get("company_domain")
        scenario = request.form.get("scenario")
        consent = request.form.get("consent_confirmed")
        requested_mode = request.form.get("delivery_mode", "smtp")
        if user["role"] == "admin":
            delivery_mode = requested_mode if requested_mode in ("local", "smtp") else "local"
        else:
            delivery_mode = "smtp"

        # 2. Security Check: Ensure consent was ticked
        if not consent:
            return "Error: You must confirm consent before launching.", 400

        # 3. Save to Database
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        ensure_auth_schema(cursor)
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

    return render_template("new_campaign.html")

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
            
            for row in reader:
                name = row.get("name", "")
                email = row.get("email", "")
                department = row.get("department", "")
                title = row.get("title", "")
                
                if email:
                    cursor.execute(sql, (name, email, department, title, campaign_id))
                    
            db.commit()
            cursor.close()
            db.close()
            return redirect(url_for("dashboard"))
        except Exception as e:
            return f"Error processing CSV: {str(e)}", 500

import threading

def process_campaign_background(campaign_id):
    """Runs the AI generation and email dispatching in the background so the browser doesn't freeze."""
    import time
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
        
        try:
            from osint.scraper import scrape_company
            company_profile = scrape_company(campaign["company_domain"])
        except ImportError:
            company_profile = {
                "company_name": campaign.get("company_domain", "Your Company"),
                "description": "Standard corporate description",
                "writing_tone": "professional and urgent"
            }
        
        try:
            from ai_engine.email_gen import generate_phishing_email
        except ImportError:
            def generate_phishing_email(context, scenario):
                return {
                    "subject": "Important Policy Update",
                    "sender_name": "HR Department",
                    "body_html": "<p>Please review the attached document.</p><p><a href='TRACKING_LINK'>Review Document</a></p>"
                }

        from send_email import send_phishing_email

        sent_count = 0
        failed_count = 0

        for emp in employees:
            import uuid
            tracking_id = str(uuid.uuid4())
            time.sleep(0.2) # Minimal delay to avoid rate limits

            emp_context = {
                "name": emp.get("name", "Employee"),
                "department": emp.get("department", "staff"),
                "title": emp.get("title", "employee"),
                "company_name": company_profile.get("company_name", ""),
                "company_tone": company_profile.get("writing_tone", "")
            }
            
            email_data = generate_phishing_email(emp_context, campaign["scenario_type"])
            
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
                    (campaign_id, tracking_id, recipient_email, status, error_message)
                VALUES (%s, %s, %s, %s, %s)
            """
            try:
                cursor.execute(tracking_sql, (
                    campaign_id,
                    tracking_id,
                    emp["email"],
                    send_status,
                    error_message
                ))
                db.commit() # Commit after each email so we get live updates
            except Exception as db_err:
                print(f"Tracking DB error: {db_err}")
            
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
    if tracking_id:
        try:
            db = get_db_connection()
            cursor = db.cursor(dictionary=True)
            cursor.execute("""
                SELECT c.scenario_type 
                FROM campaigns c
                JOIN emails_sent e ON c.id = e.campaign_id
                WHERE e.tracking_id = %s
            """, (tracking_id,))
            res = cursor.fetchone()
            if res:
                scenario_type = res['scenario_type'].replace('_', ' ').title()
            cursor.close()
            db.close()
        except:
            pass
    return render_template("simulated.html", scenario=scenario_type)

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
        ensure_email_tracking_table(cursor)
        ensure_events_table(cursor)
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

if __name__ == "__main__":
    app.run(debug=True)
