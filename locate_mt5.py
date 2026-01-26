import os

search_roots = [
    "/Users/macbookpro/Library/Application Support",
    "/Users/macbookpro/Documents",
    "/Users/macbookpro/Desktop",
    "/Users/macbookpro/Downloads"
]

print("🔍 Searching for 'MQL5' folders...")

for root_dir in search_roots:
    if not os.path.exists(root_dir):
        continue
        
    for root, dirs, files in os.walk(root_dir):
        # Skip hidden folders to speed up
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        
        if "MQL5" in dirs:
            full_path = os.path.join(root, "MQL5")
            print(f"FOUND: {full_path}")
            
            # Check for Sentinel.mq5 inside the Experts folder
            experts_path = os.path.join(full_path, "Experts")
            if os.path.exists(experts_path):
                 for r, d, f in os.walk(experts_path):
                    if "Sentinel.mq5" in f:
                        print(f"  ✅ Sentinel.mq5 FOUND HERE: {os.path.join(r, 'Sentinel.mq5')}")
            
            # Print Files/Command content if exists
            cmd_path = os.path.join(full_path, "Files", "Command")
            if os.path.exists(cmd_path):
                 print(f"  📂 Has Command Folder: {cmd_path}")
                 files_in_cmd = os.listdir(cmd_path)
                 print(f"     - Files count: {len(files_in_cmd)}")

print("Search complete.")
