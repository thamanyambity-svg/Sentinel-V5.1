import sys
import os

STATUS_FILE = "env_status.txt"

def log(msg):
    with open(STATUS_FILE, "a") as f:
        f.write(msg + "\n")

# Reset file
with open(STATUS_FILE, "w") as f:
    f.write("--- ENV VERIFICATION START ---\n")

log(f"Executable: {sys.executable}")
log(f"Version: {sys.version}")
log(f"CWD: {os.getcwd()}")
log(f"Path: {sys.path}")

try:
    import dotenv
    log(f"SUCCESS: dotenv found at {dotenv.__file__}")
except ImportError as e:
    log(f"FAILURE: dotenv error: {e}")

try:
    import pandas
    log(f"SUCCESS: pandas found at {pandas.__file__}")
except ImportError as e:
    log(f"FAILURE: pandas error: {e}")

try:
    import discord
    log(f"SUCCESS: discord found at {discord.__file__}")
except ImportError as e:
    log(f"FAILURE: discord error: {e}")

log("--- ENV VERIFICATION END ---")
