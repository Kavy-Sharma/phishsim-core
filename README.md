# PhishSim AI

AI-powered phishing simulation and security-awareness reporting platform.

PhishSim AI helps security teams run authorized phishing simulations, generate personalized training emails, track campaign behavior, and produce AI-assisted risk reports. The public version of this repository is intentionally limited so the project can be shown without exposing private implementation details, abuse-prone logic, credentials, or production configuration.

> Legal and ethical use only: this project is for authorized security training, internal awareness programs, and educational demonstrations. Do not use it against any person, company, or system without explicit permission.

## Project Status

This repository is a portfolio/demo version of a private project. The private repository contains the full working implementation and active development history. The public repository is designed to show the product idea, UI, workflow, architecture, and selected safe code only.

Live demo: add your deployed URL here  
Private source access: available on request for reviewers, recruiters, or collaborators

## What It Does

- Creates phishing-awareness campaigns from a company domain and employee CSV.
- Uses company context and employee role data to generate tailored simulation emails.
- Supports sandbox email delivery for local testing and SMTP delivery for approved live campaigns.
- Tracks email delivery, opens, clicks, and user reports.
- Shows campaign-level metrics in a web dashboard.
- Generates AI-assisted campaign recommendations and PDF reports.
- Includes a safe reveal page that teaches users what signals they missed after they click.
- Provides account, admin, user, campaign, and report management screens.

## Screenshots

Add screenshots to `docs/screenshots/` and keep them sanitized. Do not show real employee emails, private company data, API keys, SMTP settings, database names, or anything from `.env`.

Recommended screenshots:

1. `docs/screenshots/home.png` - landing page showing the PhishSim AI concept and demo entry point.
2. `docs/screenshots/dashboard.png` - campaign dashboard with sample or blurred metrics.
3. `docs/screenshots/new-campaign.png` - campaign creation flow with fake company/domain data.
4. `docs/screenshots/campaign-report.png` - AI security report page with dummy campaign results.
5. `docs/screenshots/generated-emails.png` - generated email preview using fake recipients only.
6. `docs/screenshots/training-reveal.png` - post-click education page explaining the simulated phish.
7. `docs/screenshots/pdf-report.png` - exported report preview with all sensitive details removed.

Example layout after adding images:

```md
## Screenshots

![Home page](docs/screenshots/home.png)
![Dashboard](docs/screenshots/dashboard.png)
![Campaign report](docs/screenshots/campaign-report.png)
```

## Tech Stack

- Backend: Python, Flask
- Database: MySQL or TiDB-compatible MySQL
- Frontend: Jinja templates, HTML, CSS, vanilla JavaScript
- AI: OpenRouter-compatible chat completions
- Email: Python `smtplib`, local SMTP sandbox, configurable live SMTP
- Reports: `fpdf2`
- Data processing: CSV parsing, pandas/scikit-learn-ready dependencies
- Deployment: Gunicorn-compatible Python web service

## Main Workflow

1. Create an account or sign in to a workspace.
2. Create a campaign with a name, company domain, scenario, and delivery mode.
3. Upload an employee CSV with names, emails, departments, titles, and optional seniority.
4. Generate campaign emails using company and role context.
5. Launch the campaign through sandbox or approved SMTP delivery.
6. Track opens, clicks, reports, delivery failures, and campaign status.
7. Review AI recommendations and export a PDF report.

## CSV Format

Use this header:

```csv
name,email,department,title,seniority
Alice Sharma,alice@example.com,Finance,Accounts Manager,Manager
Bob Patel,bob@example.com,IT,System Administrator,Mid
```

For public screenshots and demos, use fake recipients such as `example.com`, `demo.local`, or `training.test`.

## Local Setup

```bash
git clone https://github.com/Kavy-Sharma/phishsim-ai.git
cd phishsim-ai
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Create a `.env` file locally. Do not commit it.

```env
FLASK_SECRET_KEY=change-this-secret
APP_BASE_URL=http://127.0.0.1:5000

DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=
DB_NAME=phishsim_db
DB_SSL_DISABLED=True

OPENROUTER_API_KEY=your-openrouter-key
OPENROUTER_TIMEOUT_SECONDS=10

EMAIL_MODE=local
LOCAL_SMTP_HOST=127.0.0.1
LOCAL_SMTP_PORT=1025
LOCAL_EMAIL_FROM=training@phishsim.local

ADMIN_EMAIL=admin@phishsim.ai
ADMIN_PASSWORD=change-this-password
```

Run the app:

```bash
python app.py
```

Then open:

```text
http://127.0.0.1:5000
```

## Email Delivery Modes

Use local/sandbox delivery while developing. A local SMTP catcher such as smtp4dev or Mailpit is the safest way to test the flow without sending real emails.

For live delivery, configure SMTP only after you have written authorization from the organization being tested.

Common SMTP variables:

```env
EMAIL_MODE=smtp
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-smtp-user
SMTP_PASS=your-app-password
SMTP_FROM_EMAIL=security-training@example.com
SMTP_ENCRYPTION=starttls
SMTP_TIMEOUT_SECONDS=6
```

## Deployment Notes

For Render or a similar Python host:

- Build command: `pip install -r requirements.txt`
- Start command: `gunicorn app:app`
- Set all secrets in the host dashboard, not in Git.
- Set `APP_BASE_URL` to the deployed URL so tracking and report links work.
- Use a hosted MySQL/TiDB-compatible database for production-like deployments.

## Public Repository Safety

Keep the public repository as a polished demo, not the full private product.

Safe to show publicly:

- README, architecture overview, screenshots, and demo link.
- UI templates with sensitive logic removed.
- Sample CSV files with fake people and fake domains.
- Sanitized report examples.
- High-level workflow and feature descriptions.

Do not publish:

- `.env`, API keys, SMTP passwords, database URLs, private tokens, or app secrets.
- Real recipient lists or real customer/company data.
- Production database migrations containing private details.
- Full email-generation prompts if you consider them part of your core IP.
- Abuse-prone delivery automation, tracking internals, or security-bypass details.
- Commit history from the private repository if it contains secrets or full logic.

## Recommended Two-Repo Workflow

Your current remotes are set up like this:

```text
origin  -> public repository
private -> private repository
```

Use the private repository for normal development:

```bash
git add .
git commit -m "Update PhishSim AI core"
git push private main
```

Only push selected public-safe changes to `origin`. Before pushing publicly, check exactly what will be exposed:

```bash
git status
git diff --stat origin/main..HEAD
git diff origin/main..HEAD
```

Best public strategy:

1. Keep private development in `private/main`.
2. Maintain a separate public branch, for example `public-demo`.
3. Copy only safe files into that branch: README, screenshots, static demo UI, and sanitized examples.
4. Remove or stub sensitive backend logic before pushing.
5. Push public updates only from the public-safe branch.

Example:

```bash
git switch -c public-demo
```

After sanitizing files:

```bash
git add README.md docs/screenshots static templates requirements.txt
git commit -m "Refresh public demo README and screenshots"
git push origin public-demo:main
```

If the public repo is several weeks behind, do not merge private `main` directly into it. That can accidentally publish the full project. Instead, manually copy only safe changes or use a dedicated public branch that never receives private-only commits.

## Suggested Public README Text

If you want the public repo to clearly say what it is, use this short notice near the top:

```md
This is the public demo repository for PhishSim AI. It contains a safe preview of the UI, workflow, screenshots, and selected non-sensitive code. The full private implementation is not published because it contains security-sensitive simulation logic and deployment configuration. For code review, collaboration, or hiring discussions, contact me directly.
```

## Security Notes

- Simulations must be approved by the target organization.
- Use fake or consented test users during development.
- Keep live SMTP disabled until the campaign is authorized.
- Treat generated campaign reports as internal security documents.
- Rotate any credential that was ever committed accidentally.

## Author

Built by Kavy Sharma.

Contact: add your email, portfolio, LinkedIn, or GitHub profile here.
