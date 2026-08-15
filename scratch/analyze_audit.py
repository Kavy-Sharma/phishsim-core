import re
import os
import sys
from collections import defaultdict

# Reconfigure stdout to use utf-8
sys.stdout.reconfigure(encoding='utf-8')

# Read UTF-8 converted results
filepath = "scratch/color_audit_results_utf8.txt"
output_summary_path = "scratch/color_audit_grouped_summary.txt"

if not os.path.exists(filepath):
    print("Audit results file not found.")
    exit(1)

with open(filepath, "r", encoding="utf-8") as f:
    lines = f.readlines()

patterns = [
    "#38BDF8", "#38bdf8", "#3b82f6", "#2563eb", "#6366f1",
    "#a855f7", "#8b5cf6", "#10b981", "#059669", "#22c55e",
    "#00f0ff", "#ff007f", "#eab308"
]

results = defaultdict(list)

for idx, line in enumerate(lines, 1):
    line = line.strip()
    if not line:
        continue
    # Format of line: <filename>:<line_number>:<content>
    match = re.match(r"^([^:]+):(\d+):(.*)$", line)
    if match:
        file_path, line_num, content = match.groups()
        found_colors = []
        for p in patterns:
            if p.lower() in content.lower():
                found_colors.append(p)
        results[file_path].append({
            "line": line_num,
            "colors": list(set(found_colors)),
            "content": content
        })

with open(output_summary_path, "w", encoding="utf-8") as out:
    out.write(f"Total files with hits: {len(results)}\n\n")
    for file_path, hits in sorted(results.items()):
        out.write(f"File: {file_path} ({len(hits)} hits)\n")
        for hit in hits:
            out.write(f"  Line {hit['line']}: {', '.join(hit['colors'])} -> {hit['content']}\n")
        out.write("-" * 80 + "\n")

print(f"Summary written to {output_summary_path}. Total files: {len(results)}")
