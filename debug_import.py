
import sys
import os

print(f"Python Executable: {sys.executable}")
print(f"CWD: {os.getcwd()}")
print(f"Path: {sys.path}")

try:
    import bot.bridge.mt5_interface
    print(f"File Location: {bot.bridge.mt5_interface.__file__}")
    
    with open(bot.bridge.mt5_interface.__file__, 'r') as f:
        lines = f.readlines()
        print("--- CONTENT START ---")
        for i, line in enumerate(lines[:15]):
            print(f"{i+1}: {line.strip()}")
        print("--- CONTENT END ---")

except ImportError as e:
    print(f"Import Error: {e}")
except Exception as e:
    print(f"Error: {e}")
