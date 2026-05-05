"""
╔══════════════════════════════════════════════════════════════════════╗
║  SENTINEL V10 — start_production.py                                  ║
║  Lance tous les composants du système en 1 seule commande            ║
║                                                                      ║
║  Composants démarrés :                                               ║
║    1. NewsFilter      — bloque trading pendant news haute impact     ║
║    2. OpenAI Bridge   — antigravity_openai_bridge.py                 ║
║    3. Watchdog        — redémarre les processus si crash             ║
║    4. Dashboard       — terminal dashboard temps réel                ║
║                                                                      ║
║  Usage:                                                              ║
║    python start_production.py               # démarrage complet      ║
║    python start_production.py --no-bridge   # sans bridge AI        ║
║    python start_production.py --no-dash     # sans dashboard        ║
║    python start_production.py --status      # statut des composants ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import os
import sys
import json
import time
import signal
import argparse

# Fix macOS fork() segfault with PyTorch/numpy in child processes
os.environ["OBJC_DISABLE_INITIALIZE_FORK_SAFETY"] = "YES"
os.environ["PYTHONUNBUFFERED"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
import subprocess
import threading
from datetime import datetime
from pathlib import Path

# ══════════════════════════════════════════════════════════════════
#  CONFIGURATION
# ══════════════════════════════════════════════════════════════════

BASE_DIR   = Path(__file__).parent

# Utiliser le venv local s'il existe pour avoir accès à PyTorch (torch)
venv_python = BASE_DIR / "venv" / "bin" / "python3"
if venv_python.exists():
    PYTHON_EXE = str(venv_python)
else:
    PYTHON_EXE = sys.executable

# Couleurs
R = "\033[91m"; G = "\033[92m"; Y = "\033[93m"
C = "\033[96m"; B = "\033[1m";  D = "\033[2m"; X = "\033[0m"


def ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


def log(level: str, msg: str):
    colors = {"INFO": C, "OK": G, "WARN": Y, "ERR": R, "START": B}
    col = colors.get(level, X)
    print(f"  {D}[{ts()}]{X} {col}[{level}]{X} {msg}")


# ══════════════════════════════════════════════════════════════════
#  COMPOSANTS
# ══════════════════════════════════════════════════════════════════

class Component:
    """Représente un sous-processus géré."""

    def __init__(self, name: str, cmd: list, check_file: Path = None,
                 restart_on_crash: bool = True, startup_delay: float = 2.0,
                 log_file: Path = None):
        self.name             = name
        self.cmd              = cmd
        self.check_file       = check_file
        self.restart_on_crash = restart_on_crash
        self.startup_delay    = startup_delay
        self.log_file         = log_file
        self.process: subprocess.Popen = None
        self.start_time       = None
        self.restarts         = 0
        self.failed           = False

    def start(self) -> bool:
        try:
            log("START", f"Démarrage de {B}{self.name}{X} ...")
            
            # Gestion des logs individuels
            out_dest = subprocess.DEVNULL
            err_dest = subprocess.PIPE
            if self.log_file:
                out_dest = open(self.log_file, "a", encoding="utf-8")
                err_dest = subprocess.STDOUT # Rediriger stderr vers stdout (le fichier)

            self.process = subprocess.Popen(
                self.cmd,
                cwd=str(BASE_DIR),
                stdout=out_dest,
                stderr=err_dest,
            )
            self.start_time = time.time()
            time.sleep(self.startup_delay)

            if self.process.poll() is not None:
                err = ""
                try:
                    if self.process.stderr is not None:
                        err = self.process.stderr.read().decode("utf-8", errors="replace")[:300]
                    elif self.log_file and Path(self.log_file).exists():
                        lines = Path(self.log_file).read_text(errors="replace").strip().split("\n")
                        err = "\n    ".join(lines[-5:])
                except Exception as _e:
                    err = f"(impossible de lire l'erreur: {_e})"
                log("ERR", f"{self.name} s'est terminé prématurément:\n    {err}")
                self.failed = True
                return False

            log("OK", f"{B}{self.name}{X} démarré (PID {self.process.pid})")
            return True

        except FileNotFoundError:
            log("ERR", f"Script introuvable: {self.cmd[1] if len(self.cmd) > 1 else self.cmd}")
            self.failed = True
            return False
        except Exception as e:
            log("ERR", f"{self.name} erreur démarrage: {e}")
            self.failed = True
            return False

    def is_alive(self) -> bool:
        if self.process is None:
            return False
        return self.process.poll() is None

    def stop(self):
        if self.process and self.is_alive():
            log("INFO", f"Arrêt de {self.name} (PID {self.process.pid})")
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()

    def uptime(self) -> str:
        if self.start_time is None:
            return "—"
        diff = int(time.time() - self.start_time)
        h, r = divmod(diff, 3600)
        m, s = divmod(r, 60)
        return f"{h:02d}h{m:02d}m{s:02d}s"

    def status_line(self) -> str:
        if self.failed:
            status = f"{R}ÉCHEC{X}"
        elif self.is_alive():
            status = f"{G}ACTIF{X}"
        else:
            status = f"{Y}ARRÊTÉ{X}"
        pid_str = f"PID {self.process.pid}" if self.process else "—"
        return (f"  {B}{self.name:<25}{X}  {status:<20}  "
                f"Uptime: {C}{self.uptime()}{X}  "
                f"Restarts: {self.restarts}  {D}({pid_str}){X}")


# ══════════════════════════════════════════════════════════════════
#  GESTIONNAIRE DE PRODUCTION
# ══════════════════════════════════════════════════════════════════

class ProductionManager:

    def __init__(self, args):
        self.args        = args
        self.components  = []
        self._stop_event = threading.Event()
        self._watchdog   = None

    def _build_components(self) -> list:
        """Construit la liste des composants à démarrer selon les options."""
        comps = []
        logs_dir = BASE_DIR / "logs"
        logs_dir.mkdir(exist_ok=True)

        # ── 1. News Filter (toujours actif) ───────────────────────
        if not self.args.no_news:
            # Démarré comme script standalone inline (thread)
            # On lance news_filter en mode "service" si disponible
            news_cmd = [PYTHON_EXE, "-c", """
import sys, time, logging
sys.path.insert(0, '.')
logging.basicConfig(level=logging.WARNING)
try:
    from news_filter import NewsFilter
    nf = NewsFilter(mt5_path='.')
    nf.start()
    print('[NewsFilter] Démarré')
    while True:
        time.sleep(60)
except Exception as e:
    print(f'[NewsFilter] Erreur: {e}')
    raise
"""]
            comps.append(Component(
                name="NewsFilter",
                cmd=news_cmd,
                check_file=BASE_DIR / "news_block.json",
                restart_on_crash=True,
                startup_delay=3.0,
            ))

        # ── 2. OpenAI Bridge ──────────────────────────────────────
        if not self.args.no_bridge:
            bridge_script = BASE_DIR / "antigravity_openai_bridge.py"
            if bridge_script.exists():
                comps.append(Component(
                    name="AI Bridge (OpenAI)",
                    cmd=[PYTHON_EXE, str(bridge_script)],
                    restart_on_crash=True,
                    startup_delay=2.0,
                ))
            else:
                log("WARN", "antigravity_openai_bridge.py introuvable — bridge ignoré")

        # ── 3. Sentinel Server (si présent et si torch disponible) ─────────
        server_script = BASE_DIR / "sentinel_server.py"
        if server_script.exists() and not self.args.no_server:
            # Vérifier si torch est disponible avant de démarrer
            torch_ok = False
            try:
                import importlib
                importlib.import_module("torch")
                torch_ok = True
            except ImportError as e:
                log("DEBUG", f"Torch import failed: {e}")
                pass

            if not torch_ok:
                log("WARN", "Module 'torch' absent — Sentinel Server désactivé")
                log("WARN", f"  Installez-le : {PYTHON_EXE} -m pip install torch --index-url https://download.pytorch.org/whl/cpu")
            else:
                comps.append(Component(
                    name="Sentinel Server",
                    cmd=[PYTHON_EXE, str(server_script)],
                    restart_on_crash=True,
                    startup_delay=2.0,
                    log_file=logs_dir / "server.log"
                ))

        # ── 4. Sentinel Notifier (Alertes Discord/Telegram) ───────
        notifier_script = BASE_DIR / "sentinel_notifier.py"
        if notifier_script.exists():
            comps.append(Component(
                name="Sentinel Notifier",
                cmd=[PYTHON_EXE, str(notifier_script)],
                restart_on_crash=True,
                startup_delay=1.0,
                log_file=logs_dir / "notifier.log"
            ))

        # ── 5. Learning Agent (Collecte) ──────────────────────────
        learning_script = BASE_DIR / "learning_agent.py"
        if learning_script.exists():
            comps.append(Component(
                name="Learning Agent",
                cmd=[PYTHON_EXE, str(learning_script)],
                restart_on_crash=True,
                startup_delay=1.0,
                log_file=logs_dir / "learning.log"
            ))

        # ── 5c. V7.0 Meta-Learning Engine (Réputation) ────────────
        meta_learning = BASE_DIR / "agents" / "learning_engine.py"
        if meta_learning.exists():
            comps.append(Component(
                name="V7 Meta-Learning",
                cmd=[PYTHON_EXE, str(meta_learning)],
                restart_on_crash=True,
                startup_delay=2.0,
                log_file=logs_dir / "meta_learning.log"
            ))

        # ── 5b. ML Predictor (Générateur JSON pour EA V7) ─────────
        predictor_script = BASE_DIR / "ml_predictor.py"
        if predictor_script.exists():
            comps.append(Component(
                name="ML Predictor",
                cmd=[PYTHON_EXE, str(predictor_script)],
                restart_on_crash=True,
                startup_delay=1.0,
                log_file=logs_dir / "ml_predictor.log"
            ))

        # ── 6. Continuous Trainer (Optimisation ML) ───────────────
        trainer_script = BASE_DIR / "continuous_trainer.py"
        if trainer_script.exists():
            comps.append(Component(
                name="Continuous Trainer",
                cmd=[PYTHON_EXE, str(trainer_script)],
                restart_on_crash=True,
                startup_delay=2.0,
                log_file=logs_dir / "trainer.log"
            ))

        # ── 7. Ratchet Manager (Trailing Stop Avancé) ─────────────
        ratchet_script = BASE_DIR / "ratchet_manager.py"
        if ratchet_script.exists():
            comps.append(Component(
                name="Ratchet Manager",
                cmd=[PYTHON_EXE, str(ratchet_script)],
                restart_on_crash=True,
                startup_delay=1.0,
                log_file=logs_dir / "ratchet.log"
            ))

        # ── 8. Sentinel Reasoning (Sovereign Governor polling) ─────
        reasoning_script = BASE_DIR / "sentinel_reasoning.py"
        if reasoning_script.exists():
            comps.append(Component(
                name="Sovereign Governor",
                cmd=[PYTHON_EXE, str(reasoning_script), "--poll", "--interval", "15"],
                restart_on_crash=True,
                startup_delay=3.0,
                log_file=logs_dir / "reasoning.log"
            ))

        # ── 9. Massive Data Fetcher ───────────────────────────────
        massive_script = BASE_DIR / "bot" / "ai_agents" / "massive_data_fetcher.py"
        if massive_script.exists():
            comps.append(Component(
                name="Massive Data API",
                cmd=[PYTHON_EXE, str(massive_script), "--daemon"],
                restart_on_crash=True,
                startup_delay=2.0,
                log_file=logs_dir / "massive.log"
            ))

        return comps

    # ── Démarrage ─────────────────────────────────────────────────

    def start(self):
        self._print_banner()

        # Nettoyage automatique du disque (Log Rotation / Clean up)
        self._cleanup_disk_space()

        # Securité anti-doublon (Daily Restart)
        pid_file = BASE_DIR / "production.pid"
        if pid_file.exists():
            try:
                old_pid = int(pid_file.read_text().strip())
                log("INFO", f"Ancienne instance détectée (PID {old_pid}). Extinction en cours...")
                os.kill(old_pid, signal.SIGTERM)
                time.sleep(3)
            except OSError:
                pass # Processus inactif ou permission refusée
            except ValueError:
                pass

        self.components = self._build_components()

        if not self.components:
            log("WARN", "Aucun composant à démarrer. Vérifiez les options.")

        # Démarrage séquentiel avec délai
        started = 0
        for comp in self.components:
            if comp.start():
                started += 1
            time.sleep(0.5)

        log("INFO", f"{started}/{len(self.components)} composant(s) démarré(s)")

        # Watchdog en thread
        self._watchdog = threading.Thread(
            target=self._watchdog_loop,
            daemon=True,
            name="Watchdog"
        )
        self._watchdog.start()

        # Écriture du PID file
        pid_file = BASE_DIR / "production.pid"
        pid_file.write_text(str(os.getpid()))

        # Signal handlers
        signal.signal(signal.SIGINT,  self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

        # Dashboard en premier plan ou boucle de statut
        if not self.args.no_dash:
            self._run_dashboard()
        else:
            self._run_status_loop()

    # ── Watchdog ──────────────────────────────────────────────────

    def _watchdog_loop(self):
        """Redémarre les composants crashés toutes les 30s."""
        log("INFO", f"{D}Watchdog actif — vérification toutes les 30s{X}")
        while not self._stop_event.is_set():
            for comp in self.components:
                if (not comp.is_alive() and not comp.failed
                        and comp.restart_on_crash
                        and comp.start_time is not None):
                    log("WARN", f"{comp.name} crashé — redémarrage (#{comp.restarts + 1})")
                    comp.restarts += 1
                    comp.start()
            self._stop_event.wait(30)

    # ── Dashboard en premier plan ─────────────────────────────────

    def _run_dashboard(self):
        """Lance dashboard.py en sous-processus (bloquant)."""
        dash_script = BASE_DIR / "dashboard.py"
        if not dash_script.exists():
            log("WARN", "dashboard.py introuvable — mode statut simple activé")
            self._run_status_loop()
            return

        log("INFO", "Lancement du Dashboard...")
        try:
            dash_proc = subprocess.run(
                [PYTHON_EXE, str(dash_script), "--interval", "5"],
                cwd=str(BASE_DIR),
            )
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()

    # ── Boucle de statut simple ───────────────────────────────────

    def _run_status_loop(self):
        """Affiche le statut toutes les 30s si pas de dashboard."""
        log("INFO", "Mode statut simple (Ctrl+C pour arrêter)")
        try:
            while not self._stop_event.is_set():
                self._print_status()
                self._stop_event.wait(30)
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()

    # ── Arrêt propre ──────────────────────────────────────────────

    def stop(self):
        if self._stop_event.is_set():
            return
        self._stop_event.set()
        log("INFO", "Arrêt du système en cours...")
        for comp in reversed(self.components):
            comp.stop()

        pid_file = BASE_DIR / "production.pid"
        if pid_file.exists():
            pid_file.unlink()

        log("OK", "Tous les composants arrêtés. À bientôt ! 🏁")

    def _handle_signal(self, signum, frame):
        print()
        self.stop()
        sys.exit(0)

    # ── Disk Cleanup (Auto-Suppression des vieux fichiers) ────────

    def _cleanup_disk_space(self):
        try:
            now = time.time()
            deleted = 0
            # 1. Logs de production (> 14 jours)
            logs_dir = BASE_DIR / "logs"
            if logs_dir.exists():
                for f in logs_dir.glob("*.log"):
                    if now - f.stat().st_mtime > 14 * 86400:
                        f.unlink()
                        deleted += 1

            # 2. Modèles ML obsolètes et traces IA (> 45 jours)
            models_dir = BASE_DIR / "models"
            if models_dir.exists():
                for f in models_dir.glob("model_v*.json"):
                    if now - f.stat().st_mtime > 45 * 86400:
                        f.unlink()
                        deleted += 1

            # 3. Fichiers MT5 temporaires (> 30 jours)
            mt5_env = os.environ.get("MT5_FILES_PATH")
            if mt5_env:
                for ext in ["trade_source_*.jsonl", "*.log", "crash_dumps*.txt"]:
                    for f in Path(mt5_env).glob(ext):
                        if now - f.stat().st_mtime > 30 * 86400:
                            f.unlink()
                            deleted += 1

            if deleted > 0:
                log("OK", f"Rotation Disque: {deleted} fichiers temporaires obsolètes purgés.")
        except Exception as e:
            log("WARN", f"Erreur rotation disque: {e}")

    # ── Affichage ─────────────────────────────────────────────────

    def _print_banner(self):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n{C}{'═' * 60}{X}")
        print(f"{B}  SENTINEL V10 — DÉMARRAGE PRODUCTION{X}")
        print(f"{C}{'═' * 60}{X}")
        print(f"{D}  {now}{X}")
        print(f"  Python  : {B}{PYTHON_EXE}{X}")
        print(f"  Dossier : {B}{BASE_DIR}{X}")
        opts = []
        if self.args.no_bridge: opts.append("sans bridge")
        if self.args.no_dash:   opts.append("sans dashboard")
        if self.args.no_news:   opts.append("sans news filter")
        if opts:
            print(f"  Options : {Y}{', '.join(opts)}{X}")
        print(f"{C}{'═' * 60}{X}\n")

    def _print_status(self):
        print(f"\n{C}{'─' * 60}{X}")
        print(f"{B}  STATUT — {ts()}{X}")
        print(f"{C}{'─' * 60}{X}")
        for comp in self.components:
            print(comp.status_line())
        print(f"{C}{'─' * 60}{X}")


# ══════════════════════════════════════════════════════════════════
#  COMMANDE --STATUS (lecture seule)
# ══════════════════════════════════════════════════════════════════

from dotenv import load_dotenv
load_dotenv() # Charger .env avant show_status

def show_status():
    """Affiche le statut sans démarrer quoi que ce soit."""
    print(f"\n{C}{'═' * 60}{X}")
    print(f"{B}  SENTINEL V10 — STATUT SYSTÈME{X}")
    print(f"{C}{'═' * 60}{X}")

    # Récupérer le chemin live depuis l'environnement
    mt5_env = os.environ.get("MT5_FILES_PATH")
    mt5_path = Path(mt5_env) if mt5_env else BASE_DIR

    checks = {
        "status.json"            : mt5_path / "status.json",
        "news_block.json"        : mt5_path / "news_block.json",
        "action_plan.json"       : mt5_path / "action_plan.json",
        "backtest_summary.json"  : mt5_path / "backtest_summary.json",
        "training_history.json"  : mt5_path / "training_history.json",
        "fundamental_state.json" : mt5_path / "fundamental_state.json",
        "ticks_v3.json"          : mt5_path / "ticks_v3.json",
    }

    for label, path in checks.items():
        if path.exists():
            age_s = time.time() - path.stat().st_mtime
            age   = f"{int(age_s)}s" if age_s < 60 else f"{int(age_s/60)}m"
            size  = path.stat().st_size
            fresh = G if age_s < 120 else Y if age_s < 600 else R
            print(f"  {fresh}✔{X}  {label:<28} {D}({age} ago, {size} B){X}")
        else:
            print(f"  {R}✘{X}  {label:<28} {D}(absent){X}")

    # PID file
    pid_file = BASE_DIR / "production.pid"
    if pid_file.exists():
        pid = pid_file.read_text().strip()
        print(f"\n  {G}✔{X}  Production en cours  {D}(PID {pid}){X}")
    else:
        print(f"\n  {Y}ℹ{X}  Production non démarrée")

    # Lecture rapide status.json
    status_path = mt5_path / "status.json"
    if status_path.exists():
        try:
            with open(status_path) as f:
                data = json.load(f)
            bal  = data.get("balance", 0)
            eq   = data.get("equity", 0)
            trd  = data.get("trading", False)
            pos  = len(data.get("positions", []))
            te   = G + "ACTIVÉ"  if trd else R + "DÉSACTIVÉ"
            print(f"\n  {B}Compte MT5{X}: Balance={G}${bal:,.2f}{X}  "
                  f"Equity={G}${eq:,.2f}{X}  Trading={te}{X}  "
                  f"Positions={C}{pos}{X}")
        except Exception:
            pass

    print(f"{C}{'═' * 60}{X}\n")


# ══════════════════════════════════════════════════════════════════
#  POINT D'ENTRÉE
# ══════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Sentinel V10 — Script de démarrage production"
    )
    parser.add_argument("--no-bridge",  action="store_true", help="Désactiver le bridge OpenAI")
    parser.add_argument("--no-dash",    action="store_true", help="Désactiver le dashboard")
    parser.add_argument("--no-news",    action="store_true", help="Désactiver le news filter")
    parser.add_argument("--no-server",  action="store_true", help="Désactiver sentinel_server")
    parser.add_argument("--status",     action="store_true", help="Afficher le statut et quitter")
    args = parser.parse_args()

    if args.status:
        show_status()
        return

    mgr = ProductionManager(args)
    mgr.start()


if __name__ == "__main__":
    main()
