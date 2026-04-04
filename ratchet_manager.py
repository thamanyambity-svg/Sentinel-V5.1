#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════╗
║  SENTINEL V11 — ratchet_manager.py                                   ║
║  Gestionnaire de Profit par Paliers (Stratégie du Cliquet)           ║
║                                                                      ║
║  Logique :                                                           ║
║    Quand le profit atteint un palier → le SL est déplacé au palier   ║
║    précédent, verrouillant ce gain pour toujours.                    ║
║                                                                      ║
║  Paliers :                                                           ║
║    +$1.50 → SL → Break-Even + marge (0.15$)                          ║
║    +$2.50 → SL verrouille +1.00$                                     ║
║    +$4.00 → SL verrouille +2.00$                                     ║
║    +$6.00 → SL verrouille +3.50$                                     ║
║    +$10.0 → SL verrouille +6.00$                                     ║
║    +$15.0 → SL verrouille +10.0$                                     ║
║    +$25.0 → SL verrouille +15.0$                                     ║
║    +$50.0 → SL verrouille +30.0$                                     ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import os, json, time, logging, threading, requests
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Dict, List

# ── Logging ──────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("ratchet_manager.log", encoding="utf-8"),
    ],
)
log = logging.getLogger("RatchetManager")

# ── Chemins ──────────────────────────────────────────────────────────
BASE_DIR  = Path(__file__).parent
MT5_FILES = Path(os.environ.get(
    "MT5_FILES_PATH",
    os.path.expanduser(
        "~/Library/Application Support/net.metaquotes.wine.metatrader5"
        "/drive_c/users/user/AppData/Roaming/MetaQuotes/Terminal/Common/Files"
    )
))

# ── Fichiers de communication avec MT5 ───────────────────────────────
STATUS_FILE   = MT5_FILES / "status.json"
COMMANDS_FILE = MT5_FILES / "python_commands.json"  # Lu par MQL5
RATCHET_STATE = BASE_DIR  / "ratchet_state.json"

# ── Config ───────────────────────────────────────────────────────────
POLL_INTERVAL = 5   # Vérification toutes les 5 secondes

# ── Paliers du Cliquet ────────────────────────────────────────────────
# Format : (seuil_profit, profit_verrouillé)
# Quand profit >= seuil → SL déplacé pour garantir le profit_verrouillé
RATCHET_LEVELS = [
    (1.50,  0.15),   # +$1.5 → Break-Even + 4 pips approx (marge)
    (2.50,  1.00),   # +$2.5 → verrouille $1
    (4.00,  2.00),   # +$4   → verrouille $2
    (6.00,  3.50),   # +$6   → verrouille $3.5
    (10.00, 6.00),   # +$10  → verrouille $6
    (15.00, 10.00),  # +$15  → verrouille $10
    (25.00, 15.00),  # +$25  
    (50.00, 30.00),  # +$50 
    (75.00, 50.00),  # +$75
    (100.0, 70.00),  # +$100 (Coriace !)
]

# ── Discord ───────────────────────────────────────────────────────────
DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK_URL", "")


# ══════════════════════════════════════════════════════════════════════
# UTILITAIRES
# ══════════════════════════════════════════════════════════════════════

def load_json(path: Path, default=None):
    try:
        if path.exists() and path.stat().st_size > 0:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        log.debug("load_json %s: %s", path.name, e)
    return default if default is not None else {}


def save_json(path: Path, data):
    tmp = path.with_suffix(".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
        tmp.replace(path)
    except Exception as e:
        log.error("save_json %s: %s", path.name, e)


def send_discord(msg: str):
    if not DISCORD_WEBHOOK:
        return
    try:
        requests.post(DISCORD_WEBHOOK, json={"content": msg}, timeout=5)
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════════════
# GESTIONNAIRE DE CLIQUET
# ══════════════════════════════════════════════════════════════════════

class RatchetManager:
    """
    Surveille les positions ouvertes et déplace le SL automatiquement
    selon les paliers de profit définis.
    """

    def __init__(self):
        # État par ticket : quel palier a déjà été atteint
        # {ticket: {"level_index": int, "locked_profit": float, "entry_price": float}}
        self._state: Dict = self._load_state()
        self._running = False

    def _load_state(self) -> Dict:
        data = load_json(RATCHET_STATE, {"positions": {}})
        return data.get("positions", {})

    def _save_state(self):
        save_json(RATCHET_STATE, {
            "positions":    self._state,
            "last_update":  datetime.now(timezone.utc).isoformat(),
        })

    def start(self):
        self._running = True
        t = threading.Thread(target=self._loop, daemon=True, name="RatchetManager")
        t.start()
        log.info("🔒 RatchetManager démarré (poll=%ds)", POLL_INTERVAL)
        log.info("   Paliers actifs: %d niveaux de $%.2f à $%.2f",
                 len(RATCHET_LEVELS),
                 RATCHET_LEVELS[0][0],
                 RATCHET_LEVELS[-1][0])

    def stop(self):
        self._running = False
        log.info("RatchetManager arrêté")

    def _loop(self):
        while self._running:
            try:
                self._check_positions()
            except Exception as e:
                log.error("Erreur loop: %s", e)
            time.sleep(POLL_INTERVAL)

    def _check_positions(self):
        """Vérifie toutes les positions ouvertes et applique le cliquet."""
        status = load_json(STATUS_FILE, {})
        positions = status.get("positions", status.get("open_positions", []))

        if not positions:
            # Nettoyer les positions fermées de l'état
            self._cleanup_closed_positions([])
            return

        commands_to_send = []

        for pos in positions:
            ticket = str(pos.get("ticket", pos.get("id", "")))
            if not ticket:
                continue

            result = self._process_position(pos, ticket)
            if result:
                commands_to_send.append(result)

        # Envoyer les commandes SL à MT5
        if commands_to_send:
            self._send_sl_commands(commands_to_send)

        # Nettoyer les positions fermées
        open_tickets = {str(p.get("ticket", p.get("id", ""))) for p in positions}
        self._cleanup_closed_positions(open_tickets)

        self._save_state()

    def _process_position(self, pos: Dict, ticket: str) -> Optional[Dict]:
        """
        Analyse une position et détermine si le SL doit être modifié.
        Retourne une commande de modification SL ou None.
        """
        # FIX v7.05 : compatibilité status.json (sym/price/lot/pnl)
        symbol     = pos.get("sym",        pos.get("symbol", "")).upper()
        trade_type = pos.get("type", "buy").lower()
        entry      = float(pos.get("price", pos.get("price_open", pos.get("entry", 0))))
        current_sl = float(pos.get("sl", 0))
        volume     = float(pos.get("lot",   pos.get("volume",    pos.get("lots", 0.01))))
        profit     = float(pos.get("pnl",   pos.get("profit",    0)))

        if entry <= 0:
            return None

        # Initialiser le suivi de cette position
        if ticket not in self._state:
            self._state[ticket] = {
                "level_index":   -1,    # Aucun palier atteint
                "locked_profit": 0.0,
                "entry_price":   entry,
                "symbol":        symbol,
                "type":          trade_type,
                "volume":        volume,
            }

        state = self._state[ticket]
        current_level = state["level_index"]

        # Chercher le prochain palier à atteindre
        new_level_index = current_level
        new_locked      = state["locked_profit"]
        trigger_level   = None

        for i, (threshold, locked) in enumerate(RATCHET_LEVELS):
            if i <= current_level:
                continue  # Palier déjà atteint
            if profit >= threshold:
                new_level_index = i
                new_locked      = locked
                trigger_level   = (threshold, locked)
            else:
                break  # Les paliers sont triés, inutile de continuer

        # Aucun nouveau palier atteint
        if new_level_index == current_level:
            return None

        # Calculer le nouveau SL en prix
        new_sl_price = self._profit_to_sl_price(
            entry, trade_type, new_locked, volume, symbol
        )

        if new_sl_price is None:
            return None

        # Vérifier que le nouveau SL est meilleur que l'actuel
        if trade_type == "buy":
            if current_sl > 0 and new_sl_price <= current_sl:
                return None  # Ne jamais reculer le SL sur un BUY
        else:
            if current_sl > 0 and new_sl_price >= current_sl:
                return None  # Ne jamais reculer le SL sur un SELL

        # Mettre à jour l'état
        old_level = current_level
        self._state[ticket]["level_index"]   = new_level_index
        self._state[ticket]["locked_profit"] = new_locked

        # Log et Discord
        threshold_hit, locked_amount = trigger_level
        level_name = (
            "🛡️ Break-Even" if locked_amount == 0
            else f"🔒 Verrouille +${locked_amount:.2f}"
        )

        log.info(
            "🎯 CLIQUET | %s #%s | Profit: +$%.2f >= $%.2f | %s | SL → %.5f",
            symbol, ticket, profit, threshold_hit, level_name, new_sl_price
        )

        send_discord(
            f"🎯 **Cliquet activé !** | {symbol} #{ticket}\n"
            f"Profit actuel: `+${profit:.2f}` | Palier: `${threshold_hit:.2f}` atteint\n"
            f"{level_name} | Nouveau SL: `{new_sl_price:.5f}`"
        )

        return {
            "action":   "modify_sl",
            "ticket":   int(ticket),
            "symbol":   symbol,
            "new_sl":   round(new_sl_price, 5),
            "reason":   f"RATCHET_L{new_level_index}",
            "ts":       datetime.now(timezone.utc).isoformat(),
        }

    def _profit_to_sl_price(
        self,
        entry: float,
        trade_type: str,
        locked_profit: float,
        volume: float,
        symbol: str,
    ) -> Optional[float]:
        """
        Convertit un montant de profit en prix SL.
        Pour simplifier, utilise la relation linéaire prix/profit.
        """
        try:
            # Valeur d'un pip selon le symbole
            pip_value = self._get_pip_value(symbol, volume)
            if pip_value <= 0:
                return None

            # Pips correspondant au profit verrouillé
            pips_to_lock = locked_profit / pip_value

            # Taille d'un pip pour ce symbole
            pip_size = self._get_pip_size(symbol)

            if trade_type == "buy":
                # SL au-dessus de l'entrée de pips_to_lock pips
                return entry + (pips_to_lock * pip_size)
            else:
                # SL en-dessous de l'entrée de pips_to_lock pips
                return entry - (pips_to_lock * pip_size)

        except Exception as e:
            log.debug("Erreur calcul SL: %s", e)
            return None

    @staticmethod
    def _get_pip_value(symbol: str, volume: float) -> float:
        """Valeur approximative d'un pip pour 1 lot."""
        pip_values = {
            "XAUUSD": 1.00 * volume,     # Or: $1/pip/lot
            "EURUSD": 10.0 * volume,     # Majeurs: $10/pip/lot
            "GBPUSD": 10.0 * volume,
            "AUDUSD": 10.0 * volume,
            "NZDUSD": 10.0 * volume,
            "USDCAD": 10.0 * volume,
            "USDCHF": 10.0 * volume,
            "USDJPY": 9.1  * volume,     # JPY: ~$9.1/pip/lot
            "USDJPYF": 9.1 * volume,
        }
        return pip_values.get(symbol, 10.0 * volume)

    @staticmethod
    def _get_pip_size(symbol: str) -> float:
        """Taille d'un pip pour ce symbole."""
        if "JPY" in symbol:
            return 0.01
        if "XAU" in symbol or "GOLD" in symbol:
            return 0.01
        if "BTC" in symbol or "ETH" in symbol:
            return 1.0
        return 0.0001  # Majeurs standard

    def _send_sl_commands(self, commands: List[Dict]):
        """
        Écrit les commandes SL dans python_commands.json
        pour que l'EA MQL5 les exécute.
        """
        existing = load_json(COMMANDS_FILE, {"commands": [], "processed": []})
        existing_cmds = existing.get("commands", [])

        # Ajouter les nouvelles commandes
        for cmd in commands:
            # Éviter les doublons
            already = any(
                c.get("ticket") == cmd["ticket"] and
                c.get("action") == cmd["action"]
                for c in existing_cmds
            )
            if not already:
                existing_cmds.append(cmd)

        save_json(COMMANDS_FILE, {
            "commands":   existing_cmds,
            "processed":  existing.get("processed", []),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })

        log.info("📤 %d commande(s) SL envoyée(s) à MT5", len(commands))

    def _cleanup_closed_positions(self, open_tickets: set):
        """Supprime de l'état les positions qui sont maintenant fermées."""
        closed = [t for t in self._state if t not in open_tickets]
        for ticket in closed:
            state = self._state.pop(ticket)
            log.info(
                "🏁 Position fermée: #%s %s | Profit verrouillé: +$%.2f",
                ticket, state.get("symbol", ""), state.get("locked_profit", 0)
            )

    def get_summary(self) -> str:
        """Retourne un résumé des positions sous surveillance."""
        if not self._state:
            return "Aucune position sous surveillance."

        lines = ["📊 **Positions sous cliquet :**"]
        for ticket, state in self._state.items():
            level_idx = state.get("level_index", -1)
            locked    = state.get("locked_profit", 0)
            symbol    = state.get("symbol", "?")

            if level_idx < 0:
                status = "⏳ En attente palier 1 (+$1.00)"
            elif locked == 0:
                status = "🛡️ Break-Even actif"
            else:
                status = f"🔒 +${locked:.2f} verrouillé"

            next_level = ""
            next_idx = level_idx + 1
            if next_idx < len(RATCHET_LEVELS):
                next_thr = RATCHET_LEVELS[next_idx][0]
                next_level = f"| Prochain palier: +${next_thr:.2f}"

            lines.append(f"  #{ticket} {symbol} — {status} {next_level}")

        return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════
# POINT D'ENTRÉE
# ══════════════════════════════════════════════════════════════════════

def main():
    import signal

    manager = RatchetManager()
    manager.start()

    def _shutdown(sig, frame):
        log.info("Signal reçu — arrêt propre...")
        manager.stop()
        exit(0)

    signal.signal(signal.SIGINT,  _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    log.info("=" * 60)
    log.info("  RATCHET MANAGER ACTIF")
    log.info("=" * 60)

    try:
        cycle = 0
        while True:
            time.sleep(60)
            cycle += 1
            if cycle % 5 == 0:  # Toutes les 5 minutes
                summary = manager.get_summary()
                log.info(summary)
    except KeyboardInterrupt:
        manager.stop()


if __name__ == "__main__":
    main()
