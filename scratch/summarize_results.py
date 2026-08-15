import re
import os
from collections import defaultdict

filepath = "scratch/color_audit_grouped_summary.txt"
if not os.path.exists(filepath):
    print("Grouped summary file not found.")
    exit(1)

with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

# Let's count hits by file and by color across the whole project
file_summaries = {}
current_file = None
current_hits = []

for line in content.splitlines():
    if line.startswith("File: "):
        if current_file:
            file_summaries[current_file] = current_hits
        # Extract filename and hits count
        current_file = line.replace("File: ", "")
        current_hits = []
    elif line.strip() and not line.startswith("Total files") and not line.startswith("-"):
        # Match line number and colors
        match = re.match(r"^\s+Line\s+(\d+):\s+([^->]+)\s+->\s+(.*)$", line)
        if match:
            line_num, colors_str, line_content = match.groups()
            current_hits.append({
                "line": line_num,
                "colors": [c.strip() for c in colors_str.split(",")],
                "content": line_content.strip()
            })

if current_file:
    file_summaries[current_file] = current_hits

print("### Summary of Remaining Hardcoded Colors by File\n")
for file_path, hits in sorted(file_summaries.items()):
    # Count occurrences of each color in this file
    color_counts = defaultdict(int)
    for hit in hits:
        for c in hit["colors"]:
            color_counts[c] += 1
    
    color_desc = ", ".join(f"{color} ({count}x)" for color, count in sorted(color_counts.items()))
    print(f"- **{file_path}**: {len(hits)} hits | Colors: {color_desc}")
    # Print first 3 occurrences as examples
    for hit in hits[:3]:
        print(f"  - Line {hit['line']}: `{hit['content'][:80]}...`")
    if len(hits) > 3:
        print(f"  - ... ({len(hits) - 3} more occurrences)")
