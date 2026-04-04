"""
MT5 Bridge - Interface principale pour main.py (status, reset_risk, execute_trade).
"""
import json
import os
import time
import uuid
import logging

logger = logging.getLogger("MT5_BRIDGE")

from bot.bridge.mt5_path_resolver import resolve_mt5_files_path

DEFAULT_PATH = os.path.expanduser(
    "~/Library/Application Support/net.metaquotes.wine.metatrader5"
    "/drive_c/users/user/AppData/Roaming/MetaQuotes/Terminal/Common/Files"
)
MT5_ROOT_PATH = os.getenv("MT5_FILES_PATH", DEFAULT_PATH)


class MT5Bridge:
    def __init__(self, root_path=None):
        if root_path is not None:
            self.root_path = root_path
        else:
            _exp = os.getenv("MT5_FILES_PATH", "").strip() or None
            self.root_path, _ = resolve_mt5_files_path(_exp)
        self.MT5_ROOT_PATH = self.root_path
        self.command_path = os.path.join(self.root_path, "Command")
        self.status_file = os.path.join(self.root_path, "status.json")
        self.m5_bars_file = os.path.join(self.root_path, "m5_bars.json")
        self.metrics_file = os.path.join(self.root_path, "metrics.json")
        self.ack_file = os.path.join(self.root_path, "ack.json")
        if os.path.exists(self.root_path) and not os.path.exists(self.command_path):
            try:
                os.makedirs(self.command_path, exist_ok=True)
            except Exception:
                pass

    def _read_json_file(self, path, default=None):
        if default is None:
            default = {}
        try:
            if os.path.isfile(path):
                with open(path, "r") as f:
                    return json.load(f)
        except Exception as e:
            logger.debug("read_json_file(%s): %s", path, e)
        return default

    def get_raw_status(self):
        return self._read_json_file(self.status_file, default={})

    def reset_risk(self):
        cmd = {"action": "RESET_RISK", "token": "ALADDIN_SECRET_2025"}
        path = os.path.join(self.command_path, "cmd_reset_%s.json" % int(time.time()))
        tmp = path + ".tmp"
        try:
            with open(tmp, "w") as f:
                json.dump(cmd, f)
            os.replace(tmp, path)
            logger.info("Reset risk command sent")
        except Exception as e:
            logger.error("reset_risk: %s", e)

    def write_action_plan(self, asset, side, volume, multiplier=1.0, score=0.85):
        """Standard format for Aladdin V7 Trap Hunter."""
        cmd = {
            "decision": side,      # "BUY" / "SELL"
            "asset": asset,
            "lot_multiplier": float(multiplier),
            "kelly_risk": 1.0,     # Default risk factor
            "spm_score": float(score),
            "volume": str(volume),  # Fallback
            "token": "ALADDIN_SECRET_2025"
        }
        
        name = "action_plan.json"
        path = os.path.join(self.root_path, name)
        tmp = path + ".tmp"
        try:
            with open(tmp, "w") as f:
                json.dump(cmd, f)
            os.replace(tmp, path)
            logger.info("⚡ Action Plan written: %s %s (score=%.2f)", side, asset, score)
            return True
        except Exception as e:
            logger.error("write_action_plan error: %s", e)
            return False

    def execute_trade(self, order_cmd):
        asset = order_cmd.get("asset", "")
        side = str(order_cmd.get("side", "BUY")).upper()
        if side not in ("BUY", "SELL"):
            return {"ok": False, "error": "invalid_side", "side": side}
            
        volume = float(order_cmd.get("volume", 0.01))
        multiplier = order_cmd.get("ai_risk_multiplier", 1.0)
        score = order_cmd.get("ai_confidence_score", 0.85)
        
        # 1. Write the modern action_plan.json (Root)
        self.write_action_plan(asset, side, volume, multiplier, score)
        
        # 2. Write the legacy command file (Command/ folder) for backward compatibility
        legacy_cmd = {
            "action": "TRADE",
            "type": side,
            "symbol": asset,
            "volume": str(volume),
            "token": "ALADDIN_SECRET_2025"
        }
        if order_cmd.get("sl"): legacy_cmd["sl"] = str(order_cmd["sl"])
        if order_cmd.get("tp"): legacy_cmd["tp"] = str(order_cmd["tp"])
        
        name = "cmd_%s_%s.json" % (int(time.time()), uuid.uuid4().hex[:8])
        path = os.path.join(self.command_path, name)
        tmp = path + ".tmp"
        try:
            with open(tmp, "w") as f:
                json.dump(legacy_cmd, f)
            os.replace(tmp, path)
            # Return "action_plan.json" because that's what the EA consumes and deletes
            return {"ok": True, "command_file": "action_plan.json", "command_path": os.path.join(self.root_path, "action_plan.json")}
        except Exception as e:
            logger.error("execute_trade legacy: %s", e)
            return {"ok": False, "error": str(e)}

    def send_order(self, symbol, side, volume=0.01, sl=0.0, tp=0.0):
        """Même contrat que mt5_interface_v2 — DerivBroker.execute()."""
        res = self.execute_trade(
            {"asset": symbol, "side": side, "volume": volume, "sl": sl, "tp": tp}
        )
        return bool(isinstance(res, dict) and res.get("ok"))

    def write_ai_bias(self, signal, trend, reason):
        if not self.root_path or not os.path.exists(self.root_path):
            return
        bias_file = os.path.join(self.root_path, "ai_bias.json")
        tmp = bias_file + ".tmp"
        try:
            with open(tmp, "w") as f:
                json.dump({
                    "signal": (signal or "WAIT").upper(),
                    "trend": (trend or "RANGING").upper(),
                    "reason": reason or "N/A",
                    "updated": time.time(),
                }, f)
            os.replace(tmp, bias_file)
        except Exception as e:
            logger.error("write_ai_bias: %s", e)

    def get_status_mtime(self):
        try:
            return os.path.getmtime(self.status_file)
        except Exception:
            return 0

    def get_m5_bars(self):
        # M5 bars are exported by the EA in a dedicated file, not in status.json.
        payload = self._read_json_file(self.m5_bars_file, default={})
        return payload.get("symbols", {})

    def get_tick_data(self):
        ticks_file = os.path.join(self.root_path, "ticks_v3.json")
        data = self._read_json_file(ticks_file, default=[])
        # If it's a list (Sentinal V7.19 format), wrap it in a dict with 'symbols' key
        if isinstance(data, list):
            return {"symbols": {item.get("sym"): item for item in data if "sym" in item}}
        return data

    def get_bridge_metrics(self):
        return self._read_json_file(self.metrics_file, default={})

    def get_metrics(self):
        """Alias pour bot.main_xm_only (même contenu que metrics.json)."""
        return self.get_bridge_metrics()

    def get_pending_command_count(self):
        try:
            return len([f for f in os.listdir(self.command_path) if f.endswith(".json")])
        except Exception:
            return 0

    def wait_command_ack(self, command_file, timeout_sec=2.0, poll_sec=0.2):
        """
        Visibility helper: waits briefly to see if MT5 consumed the command file.
        Consumed means the command file disappeared.
        """
        # Try root first (for action_plan.json), then fallback to Command/ folder
        path = os.path.join(self.root_path, command_file)
        if not os.path.exists(path):
            path = os.path.join(self.command_path, command_file)
            
        deadline = time.time() + max(0.0, float(timeout_sec))

        while time.time() < deadline:
            if not os.path.exists(path):
                metrics = self.get_bridge_metrics()
                return {
                    "acked": True,
                    "command_file": command_file,
                    "pending_commands": metrics.get("pending_commands", self.get_pending_command_count()),
                }
            time.sleep(max(0.05, float(poll_sec)))

        metrics = self.get_bridge_metrics()
        return {
            "acked": False,
            "command_file": command_file,
            "pending_commands": metrics.get("pending_commands", self.get_pending_command_count()),
        }

    def send_tudor_trade(self, symbol, type, strategy, pattern, signal_strength, stop_loss_pips, ai_risk_multiplier, ai_confidence_score, volume=None, extra=None):
        order_cmd = {
            "asset": symbol,
            "side": type,
            "volume": volume if volume is not None else (0.50 if "Volatility" in symbol else 0.10),
            "sl": 0.0,
            "tp": 0.0,
            "comment": strategy
        }
        # Merge QuantumHedge extra fields (stop_loss_points, HEDGE_QUANTUM comment)
        if extra and isinstance(extra, dict):
            order_cmd.update(extra)
        return self.execute_trade(order_cmd)
