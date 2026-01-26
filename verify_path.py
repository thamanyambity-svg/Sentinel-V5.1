import os

def check_path():
    env_file = "bot/.env"
    path = None
    
    if os.path.exists(env_file):
        with open(env_file, "r") as f:
            for line in f:
                if line.startswith("MT5_FILES_PATH="):
                    path = line.strip().split("=", 1)[1].strip('"')
                    break
    
    with open("verification_result.txt", "w") as log:
        def log_print(msg):
            print(msg)
            log.write(msg + "\n")

        if not path:
            log_print("❌ MT5_FILES_PATH not found in bot/.env")
            return

        log_print(f"🔍 Checking Path: {path}")
        
        if not os.path.exists(path):
            log_print("❌ Path does NOT exist!")
            return

        log_print("✅ Path exists.")
        
        # Check Command Folder
        cmd_dir = os.path.join(path, "Command")
        if os.path.exists(cmd_dir):
            files = os.listdir(cmd_dir)
            log_print(f"📂 Command Folder exists. Contains {len(files)} files.")
            if len(files) > 0:
                log_print("⚠️ WARNING: Files are accumulating! MT5 is NOT reading them.")
                log_print(f"   Sample: {files[:3]}")
        else:
            log_print("⚠️ Command folder missing (Bot should have created it).")

        # Check for Experts/Sentinel.mq5 to confirm it's the right install
        # Accessing parent of MQL5/Files -> MQL5/Experts
        mql5_root = os.path.dirname(path) # UP one level from Files
        experts_dir = os.path.join(mql5_root, "Experts")
        
        log_print(f"🔍 Checking Experts Dir: {experts_dir}")
        if os.path.exists(experts_dir):
            # Recursive search for Sentinel.mq5
            found = False
            for root, dirs, files in os.walk(experts_dir):
                if "Sentinel.mq5" in files:
                    log_print(f"✅ FOUND Sentinel.mq5 at: {os.path.join(root, 'Sentinel.mq5')}")
                    found = True
                    break
            if not found:
                 log_print("❌ Sentinel.mq5 NOT found in Experts folder. Wrong MT5 instance?")
        else:
            log_print(f"❌ Experts folder not found at {experts_dir}")

check_path()
