import os
import signal
import subprocess
import time
import logging
import sys

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('monitor_restarts.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

class BotManager:
    def __init__(self, bot_script="bot/main_v5.py"): # Updated to point to correct V5 script
        self.bot_script = bot_script
        self.bot_process = None
        self.logger = logging.getLogger("SmartRestart")
    
    def is_bot_running(self):
        """Vérifie si le bot tourne"""
        try:
            # Vérifier si le processus existe (ignorer grep et le script de restart lui-même)
            # On cherche "python" et le nom du script
            cmd = f"pgrep -f '{self.bot_script}'"
            result = subprocess.run(
                cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            return result.returncode == 0
        except Exception as e:
            self.logger.error(f"Erreur vérification processus: {e}")
            return False
    
    def start_bot(self):
        """Démarre le bot proprement"""
        if self.is_bot_running():
            self.logger.warning("⚠️ Bot déjà en cours d'exécution")
            return
        
        self.logger.info(f"🚀 Démarrage du bot ({self.bot_script})...")
        try:
            # Lancement en arrière-plan via nohup pour survivre à la fermeture du terminal si besoin
            # Mais ici on utilise Popen simple pour le contrôle
            # Prepare environment with PYTHONPATH
            env = os.environ.copy()
            env["PYTHONPATH"] = os.path.dirname(os.path.abspath(__file__))

            self.bot_process = subprocess.Popen(
                ["python3", self.bot_script],
                stdout=open("bot_output.log", "a"),
                stderr=open("bot_error.log", "a"),
                env=env
            )
            self.logger.info(f"✅ Bot démarré avec PID: {self.bot_process.pid}")
        except Exception as e:
            self.logger.error(f"❌ Échec du démarrage: {e}")
    
    def stop_bot(self):
        """Arrête le bot proprement"""
        # On utilise pkill pour être sûr d'arrêter l'instance qui tourne, même si ce script n'est pas le parent
        self.logger.info("🛑 Tentative d'arrêt du bot...")
        os.system(f"pkill -f '{self.bot_script}'")
        time.sleep(2)
        if not self.is_bot_running():
             self.logger.info("✅ Bot arrêté avec succès.")
        else:
             self.logger.warning("⚠️ Le bot semble toujours actif. Force kill...")
             os.system(f"pkill -9 -f '{self.bot_script}'")

# Utilisation
if __name__ == "__main__":
    manager = BotManager()
    
    if not manager.is_bot_running():
        print("Bot inactif. Démarrage...")
        manager.start_bot()
    else:
        print("✅ Bot déjà actif (Health Check OK)")
