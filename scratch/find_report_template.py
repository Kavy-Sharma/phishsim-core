import re
import os

files_to_search = [
    "templates/campaign_report.html",
    "templates/reports_demo.html"
]

patterns = [
    r"Overview",
    r"Radar",
    r"Forecast",
    r"Behavior"
]

for filename in files_to_search:
    if os.path.exists(filename):
        print(f"=== {filename} ===")
        with open(filename, "r", encoding="utf-8") as f:
            content = f.read()
        for pat in patterns:
            matches = re.findall(pat, content)
            print(f"  {pat}: {len(matches)} matches")
