from flask import Flask, render_template, request, redirect, url_for, send_file
from dotenv import load_dotenv
import os
import mysql.connector
import csv
import io
from datetime import datetime

load_dotenv()

app = Flask(__name__)

# --- Database Connection Helper ---
def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password=os.getenv("DB_PASSWORD"),
        database="phishsim_db"
    )

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

@app.route("/")
def home():
    return render_template("home.html")

@app.route("/dashboard")
def dashboard():
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    
    # 1. Fetch campaigns
    cursor.execute("SELECT * FROM campaigns ORDER BY id DESC")
    campaigns = cursor.fetchall()
    
    for camp in campaigns:
        # 2. Get employee count
        cursor.execute("SELECT COUNT(*) as count FROM employees WHERE campaign_id = %s", (camp["id"],))
        camp["employee_count"] = cursor.fetchone()["count"]
        
        # 3. Get tracking stats if launched
        if camp["status"] == "launched":
            # Count how many emails were sent total
            try:
                cursor.execute("SELECT COUNT(*) as sent FROM emails_sent WHERE campaign_id = %s", (camp["id"],))
                camp["emails_sent"] = cursor.fetchone()["sent"]
                
                # Fetch events
                sql_events = """
                    SELECT e.event_type, COUNT(*) as count 
                    FROM events e
                    JOIN emails_sent es ON e.tracking_id = es.tracking_id
                    WHERE es.campaign_id = %s
                    GROUP BY e.event_type
                """
                cursor.execute(sql_events, (camp["id"],))
                events = cursor.fetchall()
                
                camp["opens"] = 0
                camp["clicks"] = 0
                camp["reports"] = 0
                
                for ev in events:
                    if ev["event_type"] == "open":
                        camp["opens"] = ev["count"]
                    elif ev["event_type"] == "click":
                        camp["clicks"] = ev["count"]
                    elif ev["event_type"] == "report":
                        camp["reports"] = ev["count"]
            except Exception as e:
                print(f"Error fetching stats for campaign {camp['id']}: {e}")
                camp["emails_sent"] = 0
                camp["opens"] = 0
                camp["clicks"] = 0
                camp["reports"] = 0
                    
    cursor.close()
    db.close()
    return render_template("dashboard.html", campaigns=campaigns)

# 1. ADD THIS ROUTE: This shows the "Create Campaign" page
@app.route("/new-campaign", methods=["GET", "POST"])
def new_campaign():
    if request.method == "POST":
        # 1. Get data from the form
        name = request.form.get("campaign_name")
        domain = request.form.get("company_domain")
        scenario = request.form.get("scenario")
        consent = request.form.get("consent_confirmed")

        # 2. Security Check: Ensure consent was ticked
        if not consent:
            return "Error: You must confirm consent before launching.", 400

        # 3. Save to Database
        db = get_db_connection()
        cursor = db.cursor()
        sql = "INSERT INTO campaigns (name, company_domain, scenario_type, status) VALUES (%s, %s, %s, %s)"
        values = (name, domain, scenario, 'draft')
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
def upload_employees(campaign_id):
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

        for emp in employees:
            import uuid
            tracking_id = str(uuid.uuid4())
            time.sleep(1) # Small delay to prevent API rate limits

            emp_context = {
                "name": emp.get("name", "Employee"),
                "department": emp.get("department", "staff"),
                "title": emp.get("title", "employee"),
                "company_name": company_profile.get("company_name", ""),
                "company_tone": company_profile.get("writing_tone", "")
            }
            
            email_data = generate_phishing_email(emp_context, campaign["scenario_type"])
            
            send_phishing_email(
                to_email=emp["email"],
                subject=email_data["subject"],
                sender_name=email_data["sender_name"],
                body_html=email_data["body_html"],
                tracking_id=tracking_id
            )
            
            tracking_sql = "INSERT INTO emails_sent (campaign_id, tracking_id) VALUES (%s, %s)"
            try:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS emails_sent (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        campaign_id INT,
                        tracking_id VARCHAR(255) UNIQUE,
                        sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                cursor.execute(tracking_sql, (campaign_id, tracking_id))
                db.commit() # Commit after each email so we get live updates
            except Exception as db_err:
                print(f"Tracking DB error: {db_err}")
            
        cursor.execute("UPDATE campaigns SET status = 'launched' WHERE id = %s", (campaign_id,))
        db.commit()
        cursor.close()
        db.close()
    except Exception as e:
        print(f"Background thread error: {e}")

@app.route("/launch-campaign/<int:campaign_id>", methods=["POST"])
def launch_campaign(campaign_id):
    try:
        db = get_db_connection()
        cursor = db.cursor()
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
    return render_template("simulated.html")

@app.route("/report/<tracking_id>")
def report_email(tracking_id):
    """Handles the user clicking 'Report this email'."""
    log_event(tracking_id, "report", request.remote_addr, request.user_agent.string)
    return render_template("thank_you_for_reporting.html")

@app.route("/delete-campaign/<int:campaign_id>", methods=["POST"])
def delete_campaign(campaign_id):
    """Deletes a campaign and its associated data."""
    try:
        db = get_db_connection()
        cursor = db.cursor()
        
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