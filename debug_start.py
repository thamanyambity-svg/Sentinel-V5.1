import sys
import os

print("--- DEBUG START ---")
print(f"Python Executable: {sys.executable}")
print(f"Python Version: {sys.version}")
print(f"CWD: {os.getcwd()}")
print(f"PYTHONPATH: {os.environ.get('PYTHONPATH', 'Not Set')}")
print("--- SYS.PATH ---")
for p in sys.path:
    print(p)
print("----------------")

try:
    import dotenv
    print(f"SUCCESS: dotenv found at {dotenv.__file__}")
except ImportError as e:
    print(f"ERROR: dotenv import failed: {e}")

try:
    import pandas
    print(f"SUCCESS: pandas found at {pandas.__file__}")
except ImportError as e:
    print(f"ERROR: pandas import failed: {e}")
