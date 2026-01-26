import os
import codecs

log_path = "/Users/macbookpro/Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/Program Files/MetaTrader 5/MQL5/Logs/20260119.log"
output_path = "decoded_log.txt"

print(f"Reading {log_path}...")

try:
    with codecs.open(log_path, "r", "utf-16le") as f:
        # Read all lines
        lines = f.readlines()
        
    print(f"Read {len(lines)} lines.")
    
    # Get last 50 lines
    last_lines = lines[-50:]
    
    with open(output_path, "w", encoding="utf-8") as out:
        for line in last_lines:
            out.write(line)
            
    print(f"Success! Wrote last 50 lines to {output_path}")

except Exception as e:
    print(f"Error: {e}")
