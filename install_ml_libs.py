import subprocess
import sys

def install(package):
    subprocess.check_call([sys.executable, "-m", "pip", "install", package])

try:
    install("joblib")
    install("scikit-learn")
    install("lightgbm")
    install("pandas")
    print("✅ Installation complete.")
except Exception as e:
    print(f"❌ Installation failed: {e}")
