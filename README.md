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
Experience a high-fidelity, cyberpunk-inspired control center. Our custom-built **Terminal UI** and **Glassmorphic Dashboard** provide a seamless "Operating System" feel right in your browser.

- **Neon Aesthetics**: Deep-dark backgrounds with cyan and blue neon accents.
- **Interactive Terminal**: A fully functional command-line interface for system interactions.
- **Bento Grid Layout**: Modern, high-density visualization of campaign metrics and system health.

---

## 🚀 Core Capabilities

| Feature | Description | Engine |
| :--- | :--- | :--- |
| **OSINT Scraper** | Automatically mines company descriptions and writing tones from public data. | `osint_miner` |
| **Generative AI** | Crafts department-specific phishing emails using psychological triggers. | `Claude-3.5-Sonnet` |
| **Live Telemetry** | Real-time tracking of opens (pixel) and clicks with IP/User-Agent logging. | `Flask-Core` |
| **Multi-Mode Delivery** | Switch between **Trial (Mailtrap/smtp4dev)** and **Live (SMTP)** with one click. | `SMTP-Relay` |
| **AI-PDF Reporting** | Generates detailed risk reports with AI-driven recommendations. | `Report-Gen` |

---

## 🛠️ Tech Stack
- **Backend:** `Python 3.9+`, `Flask`
- **Database:** `MySQL` (Structured for speed and relational integrity)
- **Frontend:** `Vanilla JS`, `Custom CSS` (Zero frameworks, pure glassmorphism)
- **AI:** `OpenRouter` / `Anthropic Claude`
- **Email:** `SMTPLib` (Configurable for Local, Mailtrap, or Production SMTP)

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

### 2. Environment Configuration
Create a `.env` file in the root directory:
```env
# AI CONFIG
OPENROUTER_API_KEY=sk-or-v1-...

# DATABASE
DB_PASSWORD=your_secure_password

# EMAIL MODES
EMAIL_PROVIDER=local  # Options: local, mailtrap, smtp
LOCAL_SMTP_PORT=25    # Default for smtp4dev
```

### 3. Launch System
```bash
python app.py
```
> Access the interface at: `http://127.0.0.1:5000`

---

## 📊 Roadmap
- [x] **Phase 1**: Agentic OS UI Overhaul (Terminal & Bento Grid)
- [x] **Phase 2**: Multi-Mode SMTP Integration (Trial vs Live)
- [ ] **Phase 3**: In-App Email Previewer (Capture emails without SMTP)
- [ ] **Phase 4**: Advanced OSINT (Social Media Scrutiny)

---

<p align="center">
  Built with 💙 by <b>Kavy Sharma</b><br>
  <i>"Securing the human element, one byte at a time."</i>
</p>
