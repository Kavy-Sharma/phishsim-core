import re

def search_tabs(filename):
    print(f"=== {filename} ===")
    try:
        with open(filename, "r", encoding="utf-8") as f:
            content = f.read()
        
        # search for lists of tabs, tabs navigation or tab clicks
        # e.g., finding lines with Overview, Metrics, etc.
        lines = content.splitlines()
        for idx, line in enumerate(lines):
            if any(term in line for term in ["Radar", "Forecast", "Behavior", "Metrics", "Overview"]):
                if "class=" in line or "id=" in line or "<button" in line or "<div" in line or "<a" in line or "onclick" in line:
                    print(f"{idx+1}: {line.strip()}")
    except Exception as e:
        print(f"Error: {e}")

search_tabs("templates/campaign_report.html")
search_tabs("templates/reports_demo.html")
