import os
import time

filepath = "bot_output.log"
if os.path.exists(filepath):
    stats = os.stat(filepath)
    print(f"Size: {stats.st_size} bytes")
    print(f"Last Modified: {time.ctime(stats.st_mtime)}")
    
    # Read first 5 lines
    with open(filepath, 'r') as f:
        print("--- First 5 lines ---")
        for i in range(5):
            print(f.readline().strip())
else:
    print("File not found.")
