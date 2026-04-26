# 🎣 PhishSim AI

**An Advanced, AI-Powered Phishing Simulation & Security Awareness Platform**

PhishSim AI is an enterprise-grade phishing simulation platform designed for security awareness training. By leveraging Open-Source Intelligence (OSINT) and cutting-edge Large Language Models (LLMs), PhishSim AI generates highly realistic, context-aware phishing simulations to train employees to recognize and report sophisticated cyber threats.

> ⚠️ **DISCLAIMER:** This project is strictly for **educational and authorized security awareness training purposes only**. It must only be used on networks and targets where explicit written consent has been provided.

---

## 🚀 Features & Architecture

The system operates across four highly integrated phases:

### Phase 1: OSINT Intelligence Gathering
The engine dynamically scrapes public company data, extracting descriptions, writing tone, social media presence, and recent context to ensure simulations are specifically tailored to the target organization's internal communication style.

### Phase 2: AI Email Generation Engine
Using advanced LLMs via OpenRouter, the engine crafts hyper-realistic phishing emails. It utilizes psychological triggers (Authority, Urgency, Compliance) and adapts the tone based on the target employee's department and seniority level, making the emails practically indistinguishable from real internal communications.

### Phase 3: Flask Web Application & Dashboard
A sleek, premium dark-themed web application that acts as the control center:
- **Campaign Management:** Create, manage, and launch phishing campaigns.
- **Target Management:** Upload employee targets via CSV files.
- **Dynamic Dashboard:** Real-time visibility into all active and past campaigns.
- **Background Dispatch:** Non-blocking email dispatch using background threading and Mailtrap integration.

### Phase 4: Advanced Tracking & Analytics
A comprehensive tracking system that monitors employee interactions with the simulation:
- **Open Tracking:** Invisible 1x1 tracking pixels log when an email is opened.
- **Click Tracking:** Links redirect to a highly convincing Microsoft 365 fake login page before revealing the simulation.
- **Reporting Mechanism:** Injected "Report Suspicious Email" buttons allow employees to successfully report the phish.
- **Educational Reveal:** A beautifully designed landing page provides immediate, visual feedback and tips to employees who fall for the simulation.
- **Real-Time Database Logging:** Captures IP addresses, User-Agents, and timestamps for robust reporting.

---

## 🛠️ Technology Stack

- **Backend:** Python, Flask
- **Database:** MySQL
- **Frontend:** HTML5, CSS3 (Custom Glassmorphism UI, No external frameworks)
- **AI/LLM:** OpenRouter API
- **Email Delivery:** SMTP (Mailtrap for sandbox testing)

---

## ⚙️ Setup & Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/yourusername/Phishsim.ai.git
   cd Phishsim.ai
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Environment Variables:**
   Create a `.env` file in the root directory and add the following:
   ```env
   OPENROUTER_API_KEY=your_api_key_here
   DB_PASSWORD=your_mysql_password
   MAILTRAP_USER=your_mailtrap_user
   MAILTRAP_PASS=your_mailtrap_password
   ```

4. **Initialize the Database:**
   Ensure your local MySQL server is running and you have created a database named `phishsim_db`. The application will automatically construct the required tables (`campaigns`, `employees`, `emails_sent`, `events`) upon launch.

5. **Run the Application:**
   ```bash
   python app.py
   ```
   Navigate to `http://127.0.0.1:5000` in your browser.

---

## 🛡️ Best Practices & Usage

- **Always obtain consent** before launching a campaign against any domain or employee list.
- Use **Mailtrap** during development to prevent accidentally sending emails to real inboxes.
- Monitor your dashboard closely to identify departments that may require additional security training based on click rates.