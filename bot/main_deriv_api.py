"""
╔══════════════════════════════════════════════════════════════════════╗
║  SENTINEL V5 — MODE DERIV API DIRECT (DEMO)                        ║
║  Trading Volatility 100 Index via WebSocket API                     ║
║  Pas besoin de MT5 — tout passe par l'API Deriv                     ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import asyncio
import logging
import os
import time
from collections import deque
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv("bot/.env")

from bot.core.logger import get_logger
logger = get_logger("SENTINEL_DERIV_API")

from bot.broker.deriv.client import DerivClient
from bot.telegram_interface.notifier import TelegramNotifier
from bot.journal.experience_logger import experience_logger
from bot.ai_agents.learning_brain import learning_brain
from bot.state.active_trades import add_active_trade, get_active_trades, remove_active_trade
from bot.state.risk.rules.engine import can_execute_trade, register_trade
from bot.state.risk.limits import reset_daily_limits
from bot.core.process_lock import acquire as lock_acquire, release as lock_release
from bot.strategy.ifvg_volatility import get_ifvg_signal
from bot.strategy.volatility_rider import get_volatility_rider_signal
from bot.strategy.rsi_extreme_reversal import get_rsi_extreme_signal
from bot.strategy.volatility_utils import get_atr_sl_pips, get_atr_risk_multiplier

# ── Configuration ────────────────────────────────────────────────
DERIV_SYMBOL = "R_100"                  # Volatility 100 Index
DISPLAY_NAME = "Volatility 100 Index"
STAKE_USD = 0.50                        # Mise par trade (demo)
SCAN_INTERVAL = 10                      # Secondes entre chaque scan
ORDER_COOLDOWN_SEC = 90                 # Min 90s entre 2 ordres
MAX_POSITIONS = 5                       # Max positions ouvertes
CANDLE_COUNT = 100                      # Nombre de bougies à fetch
GRANULARITY_M5 = 300                    # M5 en secondes
TESTING_MODE = os.getenv("TESTING_MODE", "1").strip().lower() in ("1", "true", "yes")

telegram = TelegramNotifier()


def api_candles_to_strategy_format(candles: list) -> list:
    """Convertit les bougies API Deriv vers le format attendu par les strategies."""
    result = []
    for c in candles:
        result.append({
            "o": float(c.get("open", 0)),
            "h": float(c.get("high", 0)),
            "l": float(c.get("low", 0)),
            "c": float(c.get("close", 0)),
            "t": int(c.get("epoch", 0)),
        })
    # Les stratégies attendent [0] = newest
    result.reverse()
    return result


async def check_open_contracts(client: DerivClient) -> dict:
    """Vérifie les positions ouvertes via l'API portfolio."""
    try:
        res = await client.get_portfolio()
        if res and "portfolio" in res:
            contracts = res["portfolio"].get("contracts", [])
            return {str(c.get("contract_id", "")): c for c in contracts}
    except Exception as e:
        logger.error(f"Portfolio check error: {e}")
    return {}


async def run_deriv_api():
    logger.info("🚀 SENTINEL DERIV API MODE — DEMO — Volatility 100 Index")
    logger.info(f"   Stake: ${STAKE_USD} | Cooldown: {ORDER_COOLDOWN_SEC}s | Max pos: {MAX_POSITIONS}")

    if not lock_acquire():
        logger.critical("❌ Another Sentinel is running. Exiting.")
        return

    client = DerivClient()
    try:
        auth = await client.connect()
        account = auth.get("authorize", {})
        balance = account.get("balance", 0)
        currency = account.get("currency", "USD")
        loginid = account.get("loginid", "?")
        logger.info(f"✅ Connecté: {loginid} | Balance: {balance} {currency}")

        await telegram.send_message(
            f"🚀 *Sentinel DERIV API Demo*\n"
            f"Compte: `{loginid}`\n"
            f"Balance: {balance} {currency}\n"
            f"Asset: {DISPLAY_NAME}\n"
            f"Stake: ${STAKE_USD}"
        )
    except Exception as e:
        logger.critical(f"❌ Connection Deriv échouée: {e}")
        lock_release()
        return

    last_order_time = 0
    balance_start = balance
    last_day = datetime.now(timezone.utc).date()
    price_history = deque(maxlen=10)

    try:
        while True:
            now = time.time()
            today = datetime.now(timezone.utc).date()

            # Reset quotidien
            if today != last_day:
                reset_daily_limits()
                bal_res = await client.get_balance()
                if bal_res:
                    balance_start = bal_res.get("balance", balance_start)
                last_day = today

            # ── A. Balance & positions ───────────────────────────
            bal_data = await client.get_balance()
            if bal_data:
                balance = bal_data.get("balance", balance)

            open_contracts = await check_open_contracts(client)
            open_count = len(open_contracts)

            # ── B. Fetch M5 candles via API ──────────────────────
            candles_raw = await client.get_candles(
                symbol=DERIV_SYMBOL,
                granularity=GRANULARITY_M5,
                count=CANDLE_COUNT,
            )

            if not candles_raw or len(candles_raw) < 20:
                logger.warning(f"⏭️ {DISPLAY_NAME}: Pas assez de données ({len(candles_raw)} candles)")
                await asyncio.sleep(SCAN_INTERVAL)
                continue

            candles = api_candles_to_strategy_format(candles_raw)
            price = candles[0]["c"]
            point = 0.01

            # Données figées ?
            price_history.append(price)
            if len(price_history) >= 5 and len(set(round(p, 4) for p in price_history)) == 1:
                logger.info(f"⏭️ {DISPLAY_NAME}: Prix figé, skip")
                await asyncio.sleep(SCAN_INTERVAL)
                continue

            # ── C. Analyse de signal ─────────────────────────────
            signal = None
            sl_pips = 50
            ai_confidence = 0.75
            strategy_name = "ALADDIN_SCALP"
            pattern_extra = ""

            # 1. Volatility Rider
            vr = get_volatility_rider_signal(DISPLAY_NAME, candles, point=point)
            if vr:
                signal = vr["side"]
                sl_pips = vr.get("sl_pips", 50)
                ai_confidence = vr.get("confidence", 0.78)
                strategy_name = vr.get("strategy", "VOLATILITY_RIDER")
                pattern_extra = vr.get("reason", "VOLARIDER")
                logger.info(f"📐 VolaRider: {signal} | SL {sl_pips} | {pattern_extra}")

            # 2. IFVG
            if not signal and len(candles) >= 20:
                ifvg = get_ifvg_signal(DISPLAY_NAME, candles, point=point)
                if ifvg:
                    signal = ifvg["side"]
                    sl_pips = ifvg.get("sl_pips", 50)
                    ai_confidence = ifvg.get("confidence", 0.75)
                    strategy_name = ifvg.get("strategy", "IFVG_SCALP")
                    pattern_extra = ifvg.get("reason", "IFVG_M5")
                    logger.info(f"📐 IFVG: {signal} | SL {sl_pips} | {pattern_extra}")

            # 3. RSI Extreme Reversal
            if not signal and len(candles) >= 19:
                rsi = get_rsi_extreme_signal(DISPLAY_NAME, candles, point=point)
                if rsi:
                    signal = rsi["side"]
                    sl_pips = rsi.get("sl_pips", 50)
                    ai_confidence = rsi.get("confidence", 0.72)
                    strategy_name = rsi.get("strategy", "RSI_EXTREME_REVERSAL")
                    pattern_extra = rsi.get("reason", "RSI_REV")
                    logger.info(f"📐 RSI Extreme: {signal} | SL {sl_pips} | {pattern_extra}")

            # 4. Fallback trend basique
            if not signal and len(candles) >= 3:
                c0 = candles[0]["c"]
                c1 = candles[1]["c"]
                c2 = candles[2]["c"]
                if c0 > c1 > c2:
                    signal = "BUY"
                    pattern_extra = "TREND_UP_3BAR"
                    ai_confidence = 0.65
                elif c0 < c1 < c2:
                    signal = "SELL"
                    pattern_extra = "TREND_DOWN_3BAR"
                    ai_confidence = 0.65

            logger.info(f"🔍 {DISPLAY_NAME}: {price:.2f} | Signal: {signal or 'NONE'} | Positions: {open_count}/{MAX_POSITIONS}")

            if not signal:
                logger.info(f"💤 {DISPLAY_NAME}: Pas de signal")
                await asyncio.sleep(SCAN_INTERVAL)
                continue

            # ── D. Filtres de risque ─────────────────────────────
            if open_count >= MAX_POSITIONS:
                logger.info(f"⏸️ Max positions ({open_count}/{MAX_POSITIONS})")
                await asyncio.sleep(SCAN_INTERVAL)
                continue

            if (now - last_order_time) < ORDER_COOLDOWN_SEC:
                remaining = int(ORDER_COOLDOWN_SEC - (now - last_order_time))
                logger.info(f"⏸️ Cooldown: encore {remaining}s")
                await asyncio.sleep(SCAN_INTERVAL)
                continue

            if not TESTING_MODE:
                allowed, reason = can_execute_trade({"asset": DISPLAY_NAME})
                if not allowed:
                    logger.info(f"⏸️ Risk gate: {reason}")
                    await asyncio.sleep(SCAN_INTERVAL)
                    continue

            # ── E. Exécution via API Deriv ───────────────────────
            contract_type = "CALL" if signal == "BUY" else "PUT"

            # Log signal avant exécution (learning)
            learning_brain.log_signal(
                DISPLAY_NAME, signal,
                {"price": price, "change_percent": 0, "trend": signal, "spread": 0},
                "MEDIUM", strategy=strategy_name
            )

            logger.info(f"⚡ EXEC {strategy_name} {signal} {DISPLAY_NAME} | Conf: {ai_confidence:.2f}")

            try:
                result = await client.buy_contract(
                    symbol=DERIV_SYMBOL,
                    contract_type=contract_type,
                    amount=STAKE_USD,
                    duration=5,
                    duration_unit="m",
                )

                if "error" in result:
                    err_msg = result["error"].get("message", "Unknown")
                    logger.error(f"❌ Trade rejeté: {err_msg}")
                    await asyncio.sleep(SCAN_INTERVAL)
                    continue

                contract_id = result.get("buy", {}).get("contract_id")
                buy_price = result.get("buy", {}).get("buy_price", STAKE_USD)
                last_order_time = now

                add_active_trade(
                    trade_id=f"deriv_{contract_id}",
                    asset=DISPLAY_NAME,
                    stake=buy_price,
                    duration="5m",
                    metadata={"contract_id": contract_id, "strategy": strategy_name},
                    signal_id=f"{strategy_name}_{int(now)}",
                )
                register_trade({"pnl": 0})

                trade_msg = (
                    f"🧞‍♂️ *{strategy_name}* (API DEMO)\n\n"
                    f"📈 *Marché*: {DISPLAY_NAME}\n"
                    f"🎯 *Action*: {signal} ({contract_type})\n"
                    f"📊 *Pattern*: {pattern_extra}\n"
                    f"💵 *Prix*: {price:.2f}\n"
                    f"💰 *Mise*: ${buy_price}\n"
                    f"🆔 Contract: `{contract_id}`"
                )
                await telegram.send_message(trade_msg)
                logger.info(f"✅ Trade exécuté: {contract_type} | Contract: {contract_id}")

            except Exception as e:
                logger.error(f"❌ Erreur exécution: {e}")

            await asyncio.sleep(SCAN_INTERVAL)

    except KeyboardInterrupt:
        logger.info("🛑 Arrêt manuel")
    except Exception as e:
        logger.critical(f"🔥 FATAL: {e}", exc_info=True)
    finally:
        lock_release()
        await client.close()

        # Report final
        try:
            bal_final = await client.get_balance()
            final_bal = bal_final.get("balance", balance) if bal_final else balance
            pnl = final_bal - balance_start
            await telegram.send_message(
                f"🏁 *Sentinel DERIV API Arrêté*\n"
                f"Balance finale: {final_bal}\n"
                f"P/L session: {pnl:+.2f}"
            )
        except Exception:
            pass


if __name__ == "__main__":
    asyncio.run(run_deriv_api())
