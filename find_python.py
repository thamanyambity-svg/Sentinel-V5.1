import sys
import os

LOG = "found.txt"

def log(msg):
    with open(LOG, "a") as f:
        f.write(msg + "\n")

try:
    log(f"EXEC: {sys.executable}")
except:
    pass

try:
    import dotenv
    log("SUCCESS: dotenv imported")
except ImportError:
    log("FAILURE: dotenv missing")

try:
    import pandas
    log("SUCCESS: pandas imported")
except ImportError:
    log("FAILURE: pandas missing")
