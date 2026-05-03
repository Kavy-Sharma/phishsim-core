# 🎣 PhishSim.ai — Agentic OS Simulation platform

<p align="center">
  <img src="https://img.shields.io/badge/Agentic-OS-00E5FF?style=for-the-badge&logo=ai&logoColor=black" alt="Agentic OS" />
  <img src="https://img.shields.io/badge/Python-3.9+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python" />
  <img src="https://img.shields.io/badge/Flask-Premium_UI-000000?style=for-the-badge&logo=flask&logoColor=white" alt="Flask" />
  <img src="https://img.shields.io/badge/Claude-AI_Engine-D97757?style=for-the-badge&logo=anthropic&logoColor=white" alt="Claude AI" />
</p>

---

## ⚡ The Mission
**PhishSim.ai** is not just another phishing tool. It is a **Premium Agentic OS** designed to revolutionize security awareness. By merging **OSINT data mining** with **Generative AI**, PhishSim.ai creates hyper-realistic simulations that don't just "test" employees—they **educate** them through the lens of a real-world adversary.

> [!CAUTION]
> **LEGAL DISCLAIMER:** This software is for **Authorized Security Testing and Educational Purposes ONLY**. Unauthorized use of this tool against any target without explicit, written consent is illegal and unethical.

---

## 🖥️ The Agentic OS Experience
Experience a high-fidelity, cyberpunk-inspired control center. Our custom-built UI provides a seamless "Operating System" feel right in your browser.

- **Dynamic Terminals**: Fully interactive command-line interfaces featuring fluid minimize animations, expandable viewports, and floating `[LIVE]` telemetry badges.
- **Neon Glassmorphism**: Deep-dark backgrounds with cyan and blue neon accents, frosted glass panels, and immersive hover states.
- **Data Visualization**: High-fidelity `Chart.js` radar mappings for instantaneous vulnerability signature analysis.

---

## 🚀 Core Capabilities

| Feature | Description | Engine |
| :--- | :--- | :--- |
| **OSINT Scraper** | Automatically mines company descriptions and writing tones from public data. | `osint_miner` |
| **Generative AI** | Crafts department-specific phishing emails using psychological triggers. | `Claude-3.5-Sonnet` |
| **Live Telemetry** | Real-time tracking of opens (pixel) and clicks with IP/User-Agent logging. | `Flask-Core` |
| **Multi-Mode Delivery** | Switch between **Sandbox (smtp4dev)** and **Live (SMTP)** with one click. | `SMTP-Relay` |
| **AI-PDF Reporting** | Generates professionally branded PDF risk reports with actionable AI recommendations. | `FPDF / AI` |

---

## 🛠️ Tech Stack
- **Backend:** `Python 3.9+`, `Flask`
- **Database:** `MySQL` (Includes automated schema self-healing and dynamic migrations)
- **Frontend:** `Vanilla JS`, `Vanilla CSS` (Zero frameworks, pure custom styling)
- **AI:** `OpenRouter` / `Anthropic Claude`
- **Email:** `SMTPLib` (Configurable for Local testing or Production SMTP)

---

## ⚙️ Quick Start

### 1. Deployment
```bash
# Clone the OS
git clone https://github.com/yourusername/Phishsim.ai.git
cd Phishsim.ai

# Install System Modules
pip install -r requirements.txt
```

### 2. Database Setup (Cloud or Local)
For local development, install MySQL and ensure `DB_HOST=localhost`.
For free cloud deployment, we recommend **TiDB Serverless**:
1. Go to [tidbcloud.com](https://tidbcloud.com/) and create a free serverless cluster.
2. Get your connection parameters (Host, Port `4000`, User, Password).

### 3. Environment Configuration
Create a `.env` file based on the provided defaults. Ensure these are set for production:
```env
APP_BASE_URL=https://your-app-name.onrender.com
DB_HOST=gateway01.us-east-1.prod.aws.tidbcloud.com
DB_PORT=4000
DB_USER=your_prefix.root
DB_PASSWORD=your_secure_password
DB_NAME=test
DB_SSL_DISABLED=False
```

### 4. Deployment (Render.com)
PhishSim is pre-configured for Render.com's Free Web Service tier:
1. Connect your GitHub repository to Render.
2. **Environment:** `Python 3`
3. **Build Command:** `pip install -r requirements.txt`
4. **Start Command:** `gunicorn app:app`
5. Inject your `.env` securely via the Render dashboard.

> Note: On the very first request, the app will automatically build the `users`, `campaigns`, and `events` tables, and run self-healing scripts to ensure your database is up to date!

---

## 📊 Roadmap
- [x] **Phase 1**: Agentic OS UI Overhaul (Terminals, Modals, Animations)
- [x] **Phase 2**: Multi-Mode SMTP Integration & Self-Healing DB
- [x] **Phase 3**: Premium PDF Generation & Radar Telemetry
- [ ] **Phase 4**: In-App Email Previewer (Capture emails without SMTP)
- [ ] **Phase 5**: Advanced OSINT (Social Media Scrutiny)

---

<p align="center">
  Built with 💙 by <b>Kavy Sharma</b><br>
  <i>"Securing the human element, one byte at a time."</i>
</p>
