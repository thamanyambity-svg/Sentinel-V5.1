import os

log_file = "evolution.log"
output_file = "debug_log_content.txt"

with open(output_file, "w") as out:
    if os.path.exists(log_file):
        size = os.path.getsize(log_file)
        out.write(f"File exists. Size: {size} bytes\n")
        if size > 0:
            out.write("--- Content Start ---\n")
            with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                out.write(f.read())
            out.write("\n--- Content End ---\n")
        else:
            out.write("File is empty.\n")
    else:
        out.write("File does not exist.\n")
