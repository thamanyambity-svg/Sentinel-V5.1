import sys
import os

with open("env_info.txt", "w") as f:
    f.write(f"Executable: {sys.executable}\n")
    try:
        import pandas
        f.write(f"Pandas found: {pandas.__file__}\n")
    except ImportError:
        f.write("Pandas NOT found\n")
    
    f.write(f"Path: {sys.path}\n")
    f.write(f"CWD: {os.getcwd()}\n")
