import app
from fpdf import FPDF
import datetime

db = app.get_db_connection()
cursor = db.cursor(dictionary=True)
campaign = app.get_campaign_metrics(cursor, 127)
report = app.build_campaign_report(campaign)

cursor.execute("""
    SELECT COALESCE(emp.department, 'Unassigned') AS department,
           COUNT(DISTINCT emp.id) AS targets,
           SUM(CASE WHEN ev.event_type = 'click' THEN 1 ELSE 0 END) AS clicks
    FROM employees emp
    LEFT JOIN emails_sent es ON es.campaign_id = emp.campaign_id AND es.recipient_email = emp.email
    LEFT JOIN events ev ON ev.tracking_id = es.tracking_id
    WHERE emp.campaign_id = 127
    GROUP BY COALESCE(emp.department, 'Unassigned')
    ORDER BY clicks DESC
""")
dept_rows = cursor.fetchall()

cursor.execute("""
    SELECT COALESCE(emp.name, REPLACE(SUBSTRING_INDEX(es.recipient_email, '@', 1), '.', ' ')) AS name,
           es.recipient_email AS email,
           COALESCE(MAX(CASE WHEN ev.event_type = 'click' THEN 1 ELSE 0 END), 0) AS clicked
    FROM emails_sent es
    LEFT JOIN employees emp ON emp.campaign_id = es.campaign_id AND emp.email = es.recipient_email
    LEFT JOIN events ev ON ev.tracking_id = es.tracking_id
    WHERE es.campaign_id = 127
    GROUP BY es.recipient_email, emp.name
    ORDER BY clicked DESC, name ASC
""")
emp_rows = cursor.fetchall()
cursor.close()
db.close()

vector_name = (campaign.get("scenario_type") or "authority_impersonation").replace("_", " ").title()
click_rate = report.get("click_rate", 0)

failed_depts = []
for d in dept_rows:
    t = d.get("targets") or 1
    d_rate = round((d.get("clicks") or 0) / t * 100)
    if d_rate > 0:
        failed_depts.append(f"{d['department']} ({d_rate}% clicks)")

failed_depts_str = ", ".join(failed_depts[:2]) if failed_depts else "None"
at_risk_names = [e["name"].title() for e in emp_rows if e.get("clicked")]
at_risk_names_str = ", ".join(at_risk_names[:3]) if at_risk_names else "None"

pdf = FPDF()
pdf.set_auto_page_break(True, margin=15)
pdf.add_page()
pdf.set_fill_color(15, 23, 42)
pdf.rect(0, 0, 210, 42, "F")
pdf.set_text_color(255, 255, 255)
pdf.set_font("Helvetica", "B", 18)
pdf.set_xy(15, 12)
pdf.cell(0, 10, "PHISHSIM AI SECURITY ADVISORY", ln=1)
pdf.set_font("Helvetica", "", 10)
pdf.cell(0, 5, "Campaign Remediation Brief & Protocol", ln=1)

pdf.set_text_color(71, 85, 105)
pdf.set_xy(15, 50)
pdf.set_font("Helvetica", "B", 9)
pdf.cell(30, 6, "DATE:")
pdf.set_font("Helvetica", "", 9)
pdf.cell(60, 6, datetime.datetime.utcnow().strftime("%B %d, %Y"))
pdf.set_font("Helvetica", "B", 9)
pdf.cell(35, 6, "CLASSIFICATION:")
pdf.set_font("Helvetica", "", 9)
pdf.cell(65, 6, "CONFIDENTIAL / INTERNAL USE ONLY", ln=1)

pdf.set_xy(15, 56)
pdf.set_font("Helvetica", "B", 9)
pdf.cell(30, 6, "COMPANY:")
pdf.set_font("Helvetica", "", 9)
pdf.cell(60, 6, "Example")
pdf.set_font("Helvetica", "B", 9)
pdf.cell(35, 6, "TARGET AUDIENCE:")
pdf.set_font("Helvetica", "", 9)
pdf.cell(65, 6, "Executive Board", ln=1)

pdf.ln(5)
pdf.set_draw_color(226, 232, 240)
pdf.line(15, pdf.get_y(), 195, pdf.get_y())
pdf.ln(8)

def add_pdf_section(pdf, title, content_lines):
    print("Adding section:", title, "x:", pdf.x, "y:", pdf.y)
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(99, 102, 241)
    pdf.cell(0, 8, title, ln=1)
    pdf.ln(1)
    pdf.set_text_color(51, 65, 85)
    pdf.set_font("Helvetica", "", 10)
    for line in content_lines:
        print("  Line:", repr(line), "x:", pdf.x, "y:", pdf.y)
        pdf.multi_cell(0, 6, str(line))
        pdf.ln(2)
    pdf.ln(5)

add_pdf_section(pdf, "1. EXECUTIVE SUMMARY", [
    f"This remedial brief was dynamically compiled by PhishSim AI following the completion of the {vector_name} simulation campaign. During the exercise, an overall compromise rate of {click_rate}% was recorded across {campaign.get('employee_count', 0)} test recipients.",
    "Social-engineering tactics successfully bypassed cognitive defenses, showing that additional awareness controls are required."
])

add_pdf_section(pdf, "2. EXPOSURE DETAILS", [
    f"- Vulnerable Departments: {failed_depts_str}",
    f"- Top At-Risk Employees Requiring Intervention: {at_risk_names_str}",
    "",
    "The primary attack vector utilized compliance pressure and spoofed organizational authority, which typically exposes training gaps in display-name verification and urgent protocol overrides."
])
