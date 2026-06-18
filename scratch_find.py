import re

# Read current file content
filename = 'templates/home.html'
content = open(filename, encoding='utf-8').read()

# 1. Scrolled navbar style replacement
scrolled_old = """/* Scrolled State */
.navbar.scrolled {
    height: 52px !important;
    background: rgba(2, 6, 23, 0.95) !important;
}"""

scrolled_new = """/* Scrolled State */
.navbar.scrolled {
    height: 52px !important;
    background: rgba(2, 6, 23, 0.95) !important;
    border-bottom: 1px solid rgba(56,189,248,0.2) !important;
    box-shadow: 0 4px 30px rgba(0,0,0,0.4) !important;
}"""

if scrolled_old in content:
    content = content.replace(scrolled_old, scrolled_new)
    print("Scrolled style replaced successfully.")
else:
    print("Scrolled style not found!")

# 2. Close button style replacement
close_btn_old = """.close-menu-btn {
    position: absolute;
    top: 20px;
    right: 20px;
    background: none;
    border: none;
    color: #94a3b8;
    font-size: 2.5rem;
    cursor: pointer;
}"""

close_btn_new = """.close-menu-btn {
    position: absolute;
    top: 20px;
    right: 20px;
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.1);
    color: #94a3b8;
    font-size: 1.3rem;
    cursor: pointer;
    width: 44px;
    height: 44px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.2s ease;
}
.close-menu-btn:hover {
    background: rgba(255,255,255,0.08);
    color: #fff;
    border-color: rgba(255,255,255,0.2);
}"""

if close_btn_old in content:
    content = content.replace(close_btn_old, close_btn_new)
    print("Close button style replaced successfully.")
else:
    print("Close button style not found!")

# 3. Redesigned Navbar Markup
# Find navbar section
navbar_start = '<nav class="navbar" id="navbar">'
# We will match the entire block up to the Mobile Menu links closing tag
mobile_menu_links_end = '</div>\n</div>'

# Let's locate navbar in content
start_idx = content.find(navbar_start)
end_search_idx = content.find('<!-- HERO -->', start_idx)
# Let's find the closing of the mobile overlay within that region
overlay_end_idx = content.rfind('</div>\n</div>', start_idx, end_search_idx) + len('</div>\n</div>')

if start_idx != -1 and overlay_end_idx != -1:
    old_navbar_block = content[start_idx:overlay_end_idx]
    
    new_navbar_block = """<nav class="navbar" id="navbar">
    <div class="nav-container">
        <a href="/" class="brand-logo">
            <span class="logo-indicator"></span>
            PhishSim<span style="color: #06b6d4;">.ai</span>
            <span class="logo-version-badge">v2.0</span>
        </a>
        
        <!-- Logged-in state -->
        {% if current_user %}
        <div class="nav-links">
            <a href="/dashboard" class="nav-link">Dashboard</a>
            <a href="/new-campaign" class="nav-link">Campaigns</a>
            {% if current_user.role == 'admin' %}
            <a href="/admin" class="nav-link" style="color: #ef4444 !important; font-weight: 600;"><i class="ti ti-shield-lock" style="margin-right: 4px; vertical-align: middle;"></i>Admin</a>
            {% endif %}
            <div class="nav-dropdown">
                <button class="nav-dropdown-trigger">Tools <i class="ti ti-chevron-down"></i></button>
                <div class="nav-dropdown-menu">
                    <a href="/threat-analyzer"><i class="ti ti-heartbeat" style="color:#06b6d4;margin-right:6px;"></i>Threat Analyzer</a>
                    <a href="/header-analyzer"><i class="ti ti-mail-search" style="color:#8b5cf6;margin-right:6px;"></i>Header Analyzer</a>
                    <a href="/url-decoder"><i class="ti ti-link" style="color:#10b981;margin-right:6px;"></i>URL Decoder</a>
                    <a href="/password-breach"><i class="ti ti-key" style="color:#f59e0b;margin-right:6px;"></i>Password Breach Check</a>
                    <a href="/ai-risk-advisor" style="border-top: 1px solid rgba(255,255,255,0.05); color:#f59e0b;"><i class="ti ti-crown" style="font-size:0.8rem;margin-right:2px;"></i> AI Risk Advisor</a>
                </div>
            </div>
        </div>
        
        <div class="nav-actions">
            {% if current_user.company_domain == 'demo-corp.com' %}
            <span style="font-family: var(--mono); font-size: 9px; font-weight: 700; background: rgba(245, 158, 11, 0.1); border: 1px solid rgba(245, 158, 11, 0.3); color: #f59e0b; padding: 2px 6px; border-radius: 4px; text-transform: uppercase;">SANDBOX MODE</span>
            <a href="/exit-demo" style="background: rgba(239, 68, 68, 0.1); border: 1px solid rgba(239, 68, 68, 0.4); color: #fca5a5; font-size: 11px; font-family: var(--font-mono); font-weight: 700; padding: 6px 12px; border-radius: 4px; text-decoration: none; text-transform: uppercase; transition: all 0.25s;" onmouseover="this.style.background='#ef4444'; this.style.color='#fff';" onmouseout="this.style.background='rgba(239, 68, 68, 0.1)'; this.style.color='#fca5a5';">Exit Sandbox</a>
            {% endif %}
            
            <i class="ti ti-bell" style="font-size: 1.25rem; color: #94a3b8; cursor: pointer;"></i>
            
            <div class="theme-toggle-pill" id="theme-toggle" role="button" aria-label="Switch theme" title="Switch theme">
                <div class="theme-toggle-slider"></div>
                <i class="ti ti-sun icon-sun"></i>
                <i class="ti ti-moon icon-moon"></i>
            </div>
            
            <!-- Billing icon-only button -->
            <a href="/billing" class="nav-billing-btn" title="Billing & Plan" style="font-size: 1.25rem; color: #94a3b8; text-decoration: none; display: inline-flex; align-items: center; justify-content: center; transition: color 0.2s;" onmouseover="this.style.color='#fff';" onmouseout="this.style.color='#94a3b8';">
                <i class="ti ti-credit-card"></i>
            </a>
            
            <!-- Upgrade Chip for non-admin/non-pro -->
            {% if current_user.role not in ('admin', 'pro') %}
            <a href="/billing" class="upgrade-chip" style="background: rgba(245, 158, 11, 0.15); border: 1px solid rgba(245, 158, 11, 0.4); color: #fbbf24; font-family: var(--font-mono), monospace; font-size: 11px; font-weight: 700; padding: 6px 12px; border-radius: 6px; text-decoration: none; text-transform: uppercase; transition: all 0.25s; display: inline-flex; align-items: center; gap: 4px;" onmouseover="this.style.background='#f59e0b'; this.style.color='#000';" onmouseout="this.style.background='rgba(245, 158, 11, 0.15)'; this.style.color='#fbbf24';">
                <i class="ti ti-crown"></i> Upgrade
            </a>
            {% endif %}
            
            {% set name_parts = current_user.name.split(' ') %}
            <a href="/profile" class="nav-avatar">
                {% if name_parts|length > 1 %}{{ name_parts[0][0]|upper }}{{ name_parts[1][0]|upper }}{% else %}{{ current_user.name[:2]|upper }}{% endif %}
            </a>
            
            <!-- PRO Badge beside Avatar -->
            {% if current_user.role == 'pro' %}
            <span class="pro-badge" style="background: linear-gradient(135deg, #38bdf8, #6366f1); color: #fff; font-size: 0.6rem; font-weight: 800; padding: 2px 6px; border-radius: 4px; margin-left: -6px; margin-right: 6px; display: inline-block; vertical-align: middle; pointer-events: none;">PRO</span>
            {% endif %}
            
            <a href="/logout" class="nav-link nav-link-login" style="font-size: 0.85rem;">Logout</a>
            
            <button class="hamburger-btn" onclick="toggleMobileMenu()" aria-label="Toggle Menu">
                <span class="bar"></span>
                <span class="bar"></span>
                <span class="bar"></span>
            </button>
        </div>
        
        <!-- Logged-out (public) state -->
        {% else %}
        <div class="nav-links">
            <div class="nav-dropdown">
                <button class="nav-dropdown-trigger">Solutions <i class="ti ti-chevron-down"></i></button>
                <div class="nav-dropdown-menu">
                    <a href="/#attack-flow">How It Works</a>
                    <a href="/#pricing">Pricing</a>
                    <a href="/#solutions">Solutions Suite</a>
                    <a href="/reports-demo">AI Report Preview</a>
                </div>
            </div>
            <a href="/#attack-flow" class="nav-link">How It Works</a>
            <a href="/#pricing" class="nav-link">Pricing</a>
            <div class="nav-dropdown">
                <button class="nav-dropdown-trigger">Threat Tools <i class="ti ti-chevron-down"></i></button>
                <div class="nav-dropdown-menu">
                    <a href="/threat-analyzer"><i class="ti ti-heartbeat" style="color:#06b6d4;margin-right:6px;"></i>Threat Analyzer</a>
                    <a href="/header-analyzer"><i class="ti ti-mail-search" style="color:#8b5cf6;margin-right:6px;"></i>Header Analyzer</a>
                    <a href="/url-decoder"><i class="ti ti-link" style="color:#10b981;margin-right:6px;"></i>URL Decoder</a>
                    <a href="/password-breach"><i class="ti ti-key" style="color:#f59e0b;margin-right:6px;"></i>Password Breach Check</a>
                    <a href="/ai-risk-advisor" style="border-top: 1px solid rgba(255,255,255,0.05); color:#f59e0b;"><i class="ti ti-crown" style="font-size:0.8rem;margin-right:2px;"></i> AI Risk Advisor</a>
                </div>
            </div>
        </div>
        
        <div class="nav-actions">
            <div class="theme-toggle-pill" id="theme-toggle" role="button" aria-label="Switch theme" title="Switch theme">
                <div class="theme-toggle-slider"></div>
                <i class="ti ti-sun icon-sun"></i>
                <i class="ti ti-moon icon-moon"></i>
            </div>
            <a href="/login" class="nav-link nav-link-login" style="font-size: 14px;">Login</a>
            <a href="/demo-login" class="btn-try-demo">Try Demo <i class="ti ti-arrow-right"></i></a>
            
            <button class="hamburger-btn" onclick="toggleMobileMenu()" aria-label="Toggle Menu">
                <span class="bar"></span>
                <span class="bar"></span>
                <span class="bar"></span>
            </button>
        </div>
        {% endif %}
    </div>
</nav>

<!-- Mobile overlay menu -->
<div class="mobile-menu-overlay" id="mobile-menu-overlay">
    <button class="close-menu-btn" onclick="toggleMobileMenu()"><i class="ti ti-x"></i></button>
    <div class="mobile-menu-links">
        {% if current_user %}
        <a href="/dashboard" onclick="toggleMobileMenu()">Dashboard</a>
        <a href="/new-campaign" onclick="toggleMobileMenu()">Campaigns</a>
        {% if current_user.role == 'admin' %}
        <a href="/admin" onclick="toggleMobileMenu()" style="color: #ef4444;"><i class="ti ti-shield-lock" style="margin-right: 4px;"></i>Admin Panel</a>
        {% endif %}
        <a href="/threat-analyzer" onclick="toggleMobileMenu()">Threat Analyzer</a>
        <a href="/header-analyzer" onclick="toggleMobileMenu()">Header Analyzer</a>
        <a href="/url-decoder" onclick="toggleMobileMenu()">URL Decoder</a>
        <a href="/password-breach" onclick="toggleMobileMenu()">Password Breach Check</a>
        <a href="/ai-risk-advisor" onclick="toggleMobileMenu()" style="color:#f59e0b;"><i class="ti ti-crown" style="font-size:0.85rem;margin-right:4px;"></i> AI Risk Advisor</a>
        <a href="/reports-demo" onclick="toggleMobileMenu()">AI Report</a>
        <a href="/profile" onclick="toggleMobileMenu()">
            Profile
            {% if current_user.role == 'pro' %}
            <span class="pro-badge" style="background: linear-gradient(135deg, #38bdf8, #6366f1); color: #fff; font-size: 0.6rem; font-weight: 800; padding: 2px 6px; border-radius: 4px; margin-left: 6px; display: inline-block; vertical-align: middle;">PRO</span>
            {% endif %}
        </a>
        <a href="/billing" onclick="toggleMobileMenu()"><i class="ti ti-credit-card"></i> Billing & Plan</a>
        {% if current_user.role not in ('admin', 'pro') %}
        <a href="/billing" onclick="toggleMobileMenu()" style="color: #fbbf24;"><i class="ti ti-crown"></i> Upgrade to PRO</a>
        {% endif %}
        <a href="/logout" onclick="toggleMobileMenu()">Logout</a>
        {% if current_user.company_domain == 'demo-corp.com' %}
        <a href="/exit-demo" onclick="toggleMobileMenu()" style="color: #ef4444;">Exit Sandbox</a>
        {% endif %}
        {% else %}
        <a href="/dashboard" onclick="toggleMobileMenu()">Dashboard</a>
        <a href="/new-campaign" onclick="toggleMobileMenu()">Campaigns</a>
        <a href="/#attack-flow" onclick="toggleMobileMenu()">How It Works</a>
        <a href="/#pricing" onclick="toggleMobileMenu()">Pricing</a>
        <a href="/threat-analyzer" onclick="toggleMobileMenu()">Threat Analyzer</a>
        <a href="/header-analyzer" onclick="toggleMobileMenu()">Header Analyzer</a>
        <a href="/url-decoder" onclick="toggleMobileMenu()">URL Decoder</a>
        <a href="/password-breach" onclick="toggleMobileMenu()">Password Breach Check</a>
        <a href="/ai-risk-advisor" onclick="toggleMobileMenu()" style="color:#f59e0b;"><i class="ti ti-crown" style="font-size:0.85rem;margin-right:4px;"></i> AI Risk Advisor</a>
        <a href="/reports-demo" onclick="toggleMobileMenu()">AI Report</a>
        <a href="/login" onclick="toggleMobileMenu()">Login</a>
        <a href="/demo-login" onclick="toggleMobileMenu()" style="color: #06b6d4;">Try Demo</a>
        {% endif %}
    </div>
</div>"""
    
    content = content.replace(old_navbar_block, new_navbar_block)
    print("Navbar block replaced successfully.")
else:
    print("Navbar block not found!")

# Write back to file
open(filename, 'w', encoding='utf-8').write(content)
print("Finished!")
