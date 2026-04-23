import json
import os
import time
import logging
import uuid
import sys
# --- MANUAL VALIDATION FUNCTION ---
def validate_trade_command(data):
    required = ["action", "symbol", "type", "volume"]
    for field in required:
        if field not in data:
            raise ValueError(f"Missing field: {field}")
    
    if data["action"] != "TRADE":
        raise ValueError("Invalid action")
    
    if data["type"] not in ["BUY", "SELL"]:
        raise ValueError("Invalid trade type")
        
    try:
        float(data["volume"])
    except:
        raise ValueError("Volume must be a number")
    return True

# --- CONFIGURATION ---
# Use Env Var or Fallback (UPDATED TO PROGRAM FILES PATH)
DEFAULT_PATH = "/Users/macbookpro/Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/Program Files/MetaTrader 5/MQL5/Files"
MT5_ROOT_PATH = os.getenv("MT5_FILES_PATH", DEFAULT_PATH)
COMMAND_PATH = os.path.join(MT5_ROOT_PATH, "Command")
STATUS_FILE = os.path.join(MT5_ROOT_PATH, "status.json")

logger = logging.getLogger("MT5_BRIDGE")
# Ensure standard output for running as script
if __name__ == "__main__":
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

class MT5Bridge:
    def __init__(self, root_path=None):
        self.root_path = root_path or MT5_ROOT_PATH
        self.command_path = os.path.join(self.root_path, "Command")
        self.status_file = os.path.join(self.root_path, "status.json")
        self._ensure_structure()
        self.SYMBOL_MAP = {
            "R_100": "Volatility 100 Index",
            "R_75": "Volatility 75 Index",
            "R_50": "Volatility 50 Index",
            "R_25": "Volatility 25 Index",
            "R_10": "Volatility 10 Index",
            "1HZ100V": "Volatility 100 (1s) Index",
            "1HZ75V": "Volatility 75 (1s) Index",
            "1HZ50V": "Volatility 50 (1s) Index",
            "1HZ25V": "Volatility 25 (1s) Index",
            "1HZ10V": "Volatility 10 (1s) Index", # Added this line based on context
            "1HZ100": "Volatility 100 (1s) Index",
            "STP": "Step Index",
            # EXNESS/AVATRADE MAPPING
            "EURUSD": "EURUSD",
            "GOLD": "GOLD",
            "XAUUSD": "XAUUSD",
        }

    def _ensure_structure(self):
        if not os.path.exists(MT5_ROOT_PATH):
             logger.error(f"❌ ROOT NOT FOUND: {MT5_ROOT_PATH}")
             return
             
        if not os.path.exists(COMMAND_PATH):
            try:
                os.makedirs(COMMAND_PATH)
                logger.info(f"✅ 'Command' folder created: {COMMAND_PATH}")
            except Exception as e:
                logger.error(f"❌ Failed to create Command folder: {e}")

    def send_order(self, symbol, side, volume=0.01, sl=0.0, tp=0.0):
        """ Sends an order (Outbound) """
        final_symbol = self.SYMBOL_MAP.get(symbol, symbol)
        
        # --- MINIMUM TRADE VALUE CONSTRAINT ($3 USD) ---
        # Approximate price per lot for different symbol types
        APPROX_PRICES = {
            "Volatility 10": 10,       # ~$10 per lot
            "Volatility 25": 200,      # ~$200 per lot
            "Volatility 50": 60,       # ~$60 per lot
            "Volatility 75": 250000,   # ~$250,000 per lot
            "Volatility 100": 1100,    # ~$1,100 per lot
            "EURUSD": 1.08,
            "XAUUSD": 2000,
            "GOLD": 2000,
            "BTCUSD": 100000,
            "ETHUSD": 3000,
        }

        
        # Determine approximate price
        approx_price = 100  # Default fallback
        for key, price in APPROX_PRICES.items():
            if key in final_symbol:
                approx_price = price
                break
        
        # Calculate trade value
        trade_value = float(volume) * approx_price
        MIN_TRADE_USD = 0.10
        
        if trade_value < MIN_TRADE_USD:
            logger.error(f"❌ TRADE REJECTED: ${trade_value:.2f} < minimum ${MIN_TRADE_USD:.2f}")
            logger.error(f"   Symbol: {final_symbol}, Volume: {volume}")
            return False
        
        # --- VOLUME SAFETY OVERRIDE ---
        # R_10 and R_100 (1s) require larger lots (min 0.50 usually)
        # Fix: Broaden string match to catch 'Volatility 10 (1s) Index'
        if ("Volatility 10" in final_symbol or "Volatility 100" in final_symbol) and float(volume) < 0.50:
            logger.warning(f"⚠️ Adjusted volume for {final_symbol} from {volume} to 0.50 (Min Req)")
            volume = 0.50

        command = {
            "action": "TRADE",
            "symbol": final_symbol,
            "type": side.upper(),
            "volume": str(volume),
            "sl": str(sl),
            "tp": str(tp),
            "comment": "Bot-Alpha"
        }
        
        # --- SECURITY VALIDATION ---
        try:
            validate_trade_command(command)
        except ValueError as e:
            logger.critical(f"⛔ SECURITY ALERT: Invalid Command Structure! {e}")
            return False

        # Unique Filename (UUID)
        filename = f"cmd_{int(time.time())}_{uuid.uuid4().hex[:8]}.json"
        
        try:
            # Atomic Write
            tmp_path = os.path.join(self.command_path, filename + ".tmp")
            final_path = os.path.join(self.command_path, filename)
            
            with open(tmp_path, 'w') as f:
                json.dump(command, f)
            os.rename(tmp_path, final_path)
            
            logger.info(f"📨 Order Deposited: {side} {final_symbol} -> {filename} (${trade_value:.2f})")
            return True
        except Exception as e:
            logger.error(f"❌ Order Send Error: {e}")
            return False

    def send_tudor_trade(self, symbol, type, strategy="TUDOR_REVERSAL", pattern="AI_SIGNAL",
                        signal_strength=0.8, stop_loss_pips=50,
                        ai_risk_multiplier=1.0, ai_confidence_score=1.0):
        """
        Sends a Specialized Tudor/Aladdin AI Trade Command.
        Supports Risk Multiplier and Confidence Score for Sentinel V5.4.
        """
        # Security: validate symbol and type before writing
        if not symbol or not isinstance(symbol, str):
            logger.warning("Tudor trade rejected: invalid symbol")
            return False
        if str(type).upper() not in ("BUY", "SELL"):
            logger.warning("Tudor trade rejected: invalid type %s", type)
            return False
        try:
            if float(ai_risk_multiplier) <= 0 or float(ai_risk_multiplier) > 10:
                logger.warning("Tudor trade rejected: ai_risk_multiplier out of range")
                return False
        except (TypeError, ValueError):
            pass

        # Mapping symbol
        final_symbol = self.SYMBOL_MAP.get(symbol, symbol)

        # Construct JSON for Aladdin AI
        command = {
            "action": "TUDOR_TRADE",
            "symbol": final_symbol,
            "type": type.upper(), # BUY/SELL
            "strategy": strategy,
            "pattern": pattern,
            "signal_strength": str(signal_strength),
            "stop_loss_pips": str(stop_loss_pips),
            "ai_risk_multiplier": str(ai_risk_multiplier), # NEW: Aladdin Brain -> Muscle
            "ai_confidence_score": str(ai_confidence_score) # NEW: Filter
        }
        
        # Unique Filename
        filename = f"cmd_tudor_{int(time.time())}_{uuid.uuid4().hex[:6]}.json"
        
        # Écrire dans MT5_FILES_PATH + MT5_FILES_PATH_ALT (ex: AppData) pour que l'EA reçoive quel que soit le terminal
        command_paths = [self.command_path]
        alt_path = os.environ.get("MT5_FILES_PATH_ALT")
        if alt_path:
            command_paths.append(os.path.join(alt_path, "Command"))
        
        try:
            payload = json.dumps(command)
            for cmd_dir in command_paths:
                try:
                    os.makedirs(cmd_dir, exist_ok=True)
                    tmp_path = os.path.join(cmd_dir, filename + ".tmp")
                    final_path = os.path.join(cmd_dir, filename)
                    with open(tmp_path, 'w') as f:
                        f.write(payload)
                    os.rename(tmp_path, final_path)
                except Exception as e2:
                    logger.debug("Write to %s: %s", cmd_dir, e2)
            logger.info(f"🧞‍♂️ Aladdin AI Command Sent: {type} {final_symbol} | Risk: x{ai_risk_multiplier} | Conf: {ai_confidence_score}")
            # Write action_plan.json at Files root so Aladdin V7.19 EA picks it up
            self.write_action_plan(
                decision=type,
                asset=symbol,
                lot_multiplier=float(ai_risk_multiplier),
                spm_score=float(ai_confidence_score),
                reasoning=f"{strategy} | {pattern}",
            )
            return True
        except Exception as e:
            logger.error(f"❌ Tudor Order Error: {e}")
            return False

    def close_position(self, ticket):
        """ Sends a CLOSE command for a specific ticket """
        command = {
            "action": "CLOSE",
            "ticket": str(ticket)
        }
        
        filename = f"cmd_close_{int(time.time())}_{ticket}.json"
        
        try:
             # Atomic Write
            tmp_path = os.path.join(self.command_path, filename + ".tmp")
            final_path = os.path.join(self.command_path, filename)
            
            with open(tmp_path, 'w') as f:
                json.dump(command, f)
            os.rename(tmp_path, final_path)
            
            logger.info(f"✂️ Close Command Sent: Ticket {ticket}")
            return True
        except Exception as e:
            logger.error(f"❌ Close Command Error: {e}")
            return False

    def reset_risk(self):
        """ Sends a RESET_RISK command to Sentinel EA """
        command = {"action": "RESET_RISK"}
        filename = f"cmd_reset_{int(time.time())}.json"
        try:
            tmp_path = os.path.join(self.command_path, filename + ".tmp")
            final_path = os.path.join(self.command_path, filename)
            with open(tmp_path, 'w') as f:
                json.dump(command, f)
            os.rename(tmp_path, final_path)
            logger.info("🛡️ Reset Risk Command Sent")
            return True
        except Exception as e:
            logger.error(f"❌ Reset Risk Error: {e}")
            return False

    def write_action_plan(self, decision: str, asset: str,
                          lot_multiplier: float = 1.0, spm_score: float = 0.0,
                          reasoning: str = "") -> bool:
        """
        Write action_plan.json at the MT5 Files root so that Aladdin V7.19
        (AladdinPro_V719_TrapHunter.mq5) can pick it up via its OnTimer() bridge.

        Field names match what the EA's ProcessBridgeCommand() expects:
          "decision"      → "BUY" | "SELL" | "IGNORE"
          "asset"         → mapped symbol name (e.g. "XAUUSD")
          "lot_multiplier"→ risk multiplier
          "kelly_risk"    → alias kept for backward-compat with older EA versions
          "spm_score"     → FinBERT / AI confidence score

        Returns:
            True on success, False if the file could not be written.
        """
        final_asset = self.SYMBOL_MAP.get(asset, asset)
        plan = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "asset": final_asset,
            "decision": decision.upper(),
            "lot_multiplier": lot_multiplier,
            "kelly_risk": lot_multiplier,
            "spm_score": spm_score,
            "reasoning": reasoning,
        }
        target = os.path.join(self.root_path, "action_plan.json")
        try:
            tmp = target + ".tmp"
            with open(tmp, 'w') as f:
                json.dump(plan, f)
            os.replace(tmp, target)
            logger.info("📋 action_plan.json → %s %s x%.2f", decision.upper(), final_asset, lot_multiplier)
            return True
        except OSError as e:
            logger.error("❌ write_action_plan: cannot write to %s — check permissions/disk space (%s)", target, e)
            return False
        except Exception as e:
            logger.error("❌ write_action_plan error: %s", e)
            return False

    def write_ai_bias(self, signal: str, trend: str, reason: str):
        """ Write AI bias for EA Scalper to consume """
        bias_file = os.path.join(self.root_path, "ai_bias.json")
        try:
            # Atomic Write
            tmp_bias = bias_file + ".tmp"
            with open(tmp_bias, 'w') as f:
                json.dump({
                    "signal": signal.upper(),
                    "trend": trend.upper(),
                    "reason": reason,
                    "updated": time.time()
                }, f)
            os.rename(tmp_bias, bias_file)
        except Exception as e:
            logger.error(f"❌ AI Bias Write Error: {e}")


    def get_portfolio(self):
        """ READS status report (Inbound) """
        if not os.path.exists(self.status_file):
            return [] # No status file yet
            
        try:
            with open(self.status_file, 'r') as f:
                content = f.read()
                if not content.strip(): return []
                data = json.loads(content)
                return data.get("positions", [])
        except json.JSONDecodeError:
            return [] # Writing in progress
        except Exception as e:
            logger.error(f"⚠️ Status Read Error: {e}")
            return []

    def get_raw_status(self, retries=3, retry_delay=0.05):
        """Returns the FULL status dict (Balance + Positions). Retries on read/JSON race."""
        if not os.path.exists(self.status_file):
            return {}
        for attempt in range(retries):
            try:
                with open(self.status_file, 'r') as f:
                    content = f.read()
                if not content.strip():
                    return {}
                return json.loads(content)
            except json.JSONDecodeError:
                if attempt < retries - 1:
                    time.sleep(retry_delay)
                else:
                    logger.warning("status.json read failed after %d retries (EA writing?)", retries)
                    return {}
            except Exception as e:
                if attempt < retries - 1:
                    time.sleep(retry_delay)
                else:
                    logger.warning("Status Read Error after retries: %s", e)
                    return {}
        return {}

    def get_status_mtime(self):
        """Return last modification time of status.json (for heartbeat)."""
        if not os.path.exists(self.status_file):
            return 0
        try:
            return os.path.getmtime(self.status_file)
        except OSError:
            return 0

    def get_m5_bars(self):
        """Read M5 bars from m5_bars.json (IFVG strategy). Returns { symbol: [ {t,o,h,l,c}, ... ] } or {}."""
        m5_file = os.path.join(self.root_path, "m5_bars.json")
        if not os.path.exists(m5_file):
            return {}
        for _ in range(3):
            try:
                with open(m5_file, "r") as f:
                    data = json.load(f)
                return data.get("symbols", {})
            except json.JSONDecodeError:
                time.sleep(0.05)
            except Exception as e:
                logger.debug("get_m5_bars: %s", e)
                return {}
        return {}

# --- FULL RADAR TEST ---
if __name__ == "__main__":
    bridge = MT5Bridge()
    
    print("--- 📡 RADAR TEST ---")
    print("Reading MT5 Portfolio...")
    
    positions = bridge.get_portfolio()
    if positions:
        print(f"✅ Positions detected: {len(positions)}")
        for p in positions:
            print(f"   🔹 {p.get('symbol')} ({p.get('type')}) | Profit: {p.get('profit')}$ | Ticket: {p.get('ticket')}")
    else:
        print("ℹ️ No active positions (or Sentinel not running).")
