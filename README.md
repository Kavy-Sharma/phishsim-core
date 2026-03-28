# PhishSim AI

PhishSim AI is an AI-powered phishing simulation platform designed for security awareness training.  
The goal of this project is to simulate realistic phishing scenarios so organizations can train employees to recognize and avoid phishing attacks.

⚠️ This project is strictly for **educational and security awareness purposes only**.

---

# Project Overview

PhishSim AI combines OSINT (Open Source Intelligence) and AI to generate highly realistic phishing simulation emails.

The system works in multiple phases:

1. Collect company intelligence from public websites.
2. Generate personalized phishing emails using AI.
3. Simulate phishing campaigns.
4. Track interactions and improve employee awareness.

---

# Phase 1 – OSINT Company Intelligence

Phase 1 focuses on collecting publicly available company information to understand how the company communicates.

This data helps AI generate realistic phishing simulation emails.

### Features

- Website scraping
- Company description extraction
- Writing tone analysis
- Social media discovery
- Email detection
- Bot protection detection
- Link extraction

Example output:

```json
{
 "company_name": "DigitalOcean",
 "description": "Build on DigitalOcean's cloud infrastructure...",
 "recent_context": ["Customers growing with DigitalOcean"],
 "writing_tone": "Simple and affordable cloud infrastructure...",
 "emails": [],
 "links": [],
 "socials": {
   "linkedin": "https://linkedin.com/company/digitalocean"
 }
}