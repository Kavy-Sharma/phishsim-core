import os
import re
from collections import defaultdict

patterns = [
    "#38BDF8", "#38bdf8", "#3b82f6", "#2563eb", "#6366f1",
    "#a855f7", "#8b5cf6", "#10b981", "#059669", "#22c55e",
    "#00f0ff", "#ff007f", "#eab308"
]

color_re = re.compile("|".join(patterns), re.IGNORECASE)

results = defaultdict(list)

# Directories to search
search_dirs = ["static", "templates"]

for s_dir in search_dirs:
    if not os.path.exists(s_dir):
        continue
    for root, dirs, files in os.walk(s_dir):
        for file in files:
            if file.endswith((".html", ".css")):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        lines = f.readlines()
                except Exception as e:
                    # Fallback to other encoding if utf-8 fails
                    try:
                        with open(file_path, "r", encoding="latin-1") as f:
                            lines = f.readlines()
                    except Exception:
                        continue
                
                for idx, line in enumerate(lines, 1):
                    matches = color_re.findall(line)
                    if matches:
                        # Find unique matches in this line matching the case-insensitive pattern
                        found = []
                        for m in matches:
                            # Normalize case to match pattern list
                            for p in patterns:
                                if m.lower() == p.lower() and p not in found:
                                    found.append(p)
                        results[file_path].append({
                            "line": idx,
                            "colors": found,
                            "content": line.strip()
                        })

# Write the final perfect summary to a file
output_path = "scratch/color_audit_grouped_summary.txt"
with open(output_path, "w", encoding="utf-8") as out:
    out.write(f"Total files with hits: {len(results)}\n\n")
    for file_path, hits in sorted(results.items()):
        out.write(f"File: {file_path} ({len(hits)} hits)\n")
        for hit in hits:
            out.write(f"  Line {hit['line']}: {', '.join(hit['colors'])} -> {hit['content']}\n")
        out.write("-" * 80 + "\n")

# Print high-level report
print("### Summary of Remaining Hardcoded Colors by File\n")
for file_path, hits in sorted(results.items()):
    color_counts = defaultdict(int)
    for hit in hits:
        for c in hit["colors"]:
            color_counts[c] += 1
    
    color_desc = ", ".join(f"`{color}` ({count}x)" for color, count in sorted(color_counts.items()))
    print(f"- **{file_path}**: {len(hits)} hits | Colors: {color_desc}")
    for hit in hits[:3]:
        print(f"  - Line {hit['line']}: `{hit['content'][:80]}...`")
    if len(hits) > 3:
        print(f"  - ... ({len(hits) - 3} more occurrences)")
