<div align="center">
  <img src="https://img.shields.io/badge/Python-3.9+-blue?style=for-the-badge&logo=python" alt="Python">
  <img src="https://img.shields.io/badge/Flask-Backend-lightgrey?style=for-the-badge&logo=flask" alt="Flask">
  <img src="https://img.shields.io/badge/AI-Anthropic%20Claude-purple?style=for-the-badge" alt="AI">
  <img src="https://img.shields.io/badge/Database-MySQL-orange?style=for-the-badge&logo=mysql" alt="MySQL">
  <h1>🛡️ PhishSim.ai — Agentic OS</h1>
  <p><strong>Autonomous Agentic Phishing Simulator & Security Awareness Platform</strong></p>
</div>

---

> **⚠️ LEGAL DISCLAIMER:** This software is for **Authorized Security Testing and Educational Purposes ONLY**. Unauthorized use of this tool against any target without explicit, written consent is illegal and unethical.

## ⚡ The Mission
PhishSim.ai is not just another phishing tool. It is a **Premium Agentic OS** designed to revolutionize security awareness. By merging data handling with Generative AI, PhishSim.ai creates hyper-realistic simulations that don't just "test" employees—they educate them through the lens of a real-world adversary.

## 🎥 System Demonstration
*(Insert your demo video or a GIF here! Show off the terminal animations, the dashboard updating, and the PDF report generation.)*

## 🖥️ The Agentic OS Experience
Experience a high-fidelity, cyberpunk-inspired control center. 
- **Neon & Glass Aesthetics:** Deep-dark terminal interfaces with dynamic glassmorphic dashboards.
- **True Adaptive UI:** Seamless Light & Dark mode rendering built entirely with Vanilla CSS variables (No external bloated frameworks).
- **Executive Real-time Tracking:** Live Bento-grid visualization of campaign metrics and Human Security Scores™.
- **Security Audit Logs:** Comprehensive tracking of all operator actions and authentication events.

## 🚀 Core Capabilities
- **Agentic Email Generation:** Upload an `employees.csv` and the AI automatically crafts hyper-personalized emails targeting specific roles and departments.
- **Multi-Mode SMTP Engine:** Test locally without sending a single real email, or plug in your production SMTP to launch live authorized campaigns.
- **Real-Time Telemetry:** Tracks `Open Rates`, `Click Rates`, and `Report Rates` instantly on the dashboard.
- **AI Threat Analyst Reports:** Dynamically generates an executive PDF report containing the organization's **Human Security Score™**, vulnerability radars, and AI-driven remediation advice.

## 🔐 Advanced Enterprise Security (Profile Section)
The operator profile is equipped with modern SaaS features to secure the platform itself:
- **Developer API Keys:** Generate `ps_live_...` API tokens. These keys allow security teams to trigger simulations programmatically via REST API or ingest campaign telemetry straight into their SIEM tools.
- **Two-Factor Authentication (2FA):** Support for Time-based One-Time Passwords (TOTP) to secure the operator's workspace from credential stuffing.
- **Email Notifications & Verification:** Ensures the operator's email is verified before allowing SMTP relay access, and sends automatic campaign summaries.

## 🛠️ Tech Stack
- **Backend:** Python 3.9+, Flask
- **Database:** MySQL (Structured for speed and relational integrity)
- **Frontend:** Vanilla JS, Custom CSS (Zero frameworks, pure glassmorphism)
- **AI:** OpenRouter / Anthropic Claude
- **Email:** SMTPLib (Configurable for Local, Mailtrap, or Production SMTP)
- **Reports:** `fpdf2` for dynamic PDF generation

## 🔄 Main Workflow
1. Create an account or sign in to a workspace.
2. Create a campaign with a name, company domain, scenario, and delivery mode.
3. Upload an employee CSV with names, emails, departments, titles, and optional seniority.
4. Generate campaign emails using company and role context.
5. Launch the campaign through sandbox or approved SMTP delivery.
6. Track opens, clicks, reports, delivery failures, and campaign status.
7. Review AI recommendations and export a PDF report.

## 📄 CSV Format
Use this header structure for uploading targets:
```csv
name,email,department,title,seniority
Alice Sharma,alice@example.com,Finance,Accounts Manager,Manager
Bob Patel,bob@example.com,IT,System Administrator,Mid
```

## 🔒 Source Code Access
**Note:** To prevent misuse of the autonomous AI logic and protect the proprietary engine, the **full backend logic is kept in a private repository.** 

The files provided in this public repository showcase the architectural structure, the UI/UX design components, and the system schematics. 

**Want to collaborate, discuss the architecture, or view the full source code?**
📧 **Contact Me on LinkedIn:** *(Insert your LinkedIn Profile Link here)*

## 🗺️ Continuous Evolution
This platform is in a state of continuous, aggressive development. I am dedicated to pushing this to an enterprise level. Future updates currently in development:
- Deep OSINT Engine (Automated LinkedIn/Social Media scraping for spear-phishing contexts)
- Employee Training Portal Integration
- API Webhooks for Enterprise SIEM Integration

*Built with 💙 by Kavy Sharma — "Securing the human element, one byte at a time."*
