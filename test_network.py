
import socket
import requests
import subprocess
import sys

print("🔍 DIAGNOSTIC RÉSEAU")

# Test DNS
try:
    ip = socket.gethostbyname("discord.com")
    print(f"✅ DNS discord.com: OK ({ip})")
except Exception as e:
    print(f"❌ DNS discord.com: ÉCHEC ({e})")

# Test HTTP
try:
    r = requests.get("http://google.com", timeout=5)
    print(f"✅ HTTP: Connecté (Status {r.status_code})")
except Exception as e:
    print(f"❌ HTTP: Échec ({e})")

# Test PING (Google DNS)
try:
    # Ping 2 times, timeout 3s
    cmd = ["ping", "-c", "2", "-W", "3000", "8.8.8.8"] if sys.platform != "win32" else ["ping", "-n", "2", "-w", "3000", "8.8.8.8"]
    subprocess.run(cmd, timeout=5, check=True, stdout=subprocess.PIPE)
    print("✅ Ping 8.8.8.8: OK")
except Exception as e:
    print(f"❌ Ping 8.8.8.8: Échec ({e})")

# Test PING (Discord)
try:
    cmd = ["ping", "-c", "2", "-W", "3000", "discord.com"] if sys.platform != "win32" else ["ping", "-n", "2", "-w", "3000", "discord.com"]
    subprocess.run(cmd, timeout=5, check=True, stdout=subprocess.PIPE)
    print("✅ Ping discord.com: OK")
except Exception as e:
    print(f"❌ Ping discord.com: Échec ({e})")
