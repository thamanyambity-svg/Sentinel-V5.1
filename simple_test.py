import sys
import os

with open('simple_test_result.txt', 'w') as f:
    f.write(f"PYTHON EXEC: {sys.executable}\n")
    f.write(f"CWD: {os.getcwd()}\n")
    f.write(f"PATH: {sys.path}\n")

    try:
        import dotenv
        f.write(f"SUCCESS: dotenv loaded from {dotenv.__file__}\n")
    except ImportError as e:
        f.write(f"FAILURE: dotenv error: {e}\n")

    try:
        import pandas
        f.write(f"SUCCESS: pandas loaded from {pandas.__file__}\n")
    except ImportError as e:
        f.write(f"FAILURE: pandas error: {e}\n")

