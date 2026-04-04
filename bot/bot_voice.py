"""
Voix du bot : agressive mais sage.
Envoie les décisions clés sur Discord + Telegram avec un ton direct et protecteur.
"""
import asyncio
import time
import logging

logger = logging.getLogger("VOICE")

# Throttle : éviter spam (asset, key) -> last_time
_last_spoke = {}
_THROTTLE_SEC = 300  # 5 min entre 2 messages identiques (asset+key)


async def speak(bot_instance, telegram, msg: str, throttle_key: str = None):
    """
    Envoie un message sur Discord et Telegram.
    Ton : agressif (direct, confiant) mais sage (logique de protection).
    Si throttle_key est fourni, limite à 1 msg / 5 min pour cette clé.
    """
    if throttle_key:
        now = time.time()
        if throttle_key in _last_spoke and (now - _last_spoke[throttle_key]) < _THROTTLE_SEC:
            return
        _last_spoke[throttle_key] = now

    try:
        if hasattr(bot_instance, "log_to_discord"):
            await bot_instance.log_to_discord(msg)
        if telegram:
            await telegram.send_message(msg)
    except Exception as e:
        logger.warning(f"Voice send failed: {e}")


# ─── Messages prédéfinis (agressif mais sage) ───

def rejection_score(asset: str, score: float, conf: float, min_score: float, min_conf: float) -> str:
    return (
        f"🛡️ **BLOCAGE** | {asset}\n"
        f"Score {score:.0f}/{min_score} ou Conf {conf:.2f}/{min_conf} insuffisant.\n"
        f"_On ne force pas. Qualité d'abord._"
    )

def rejection_governance(asset: str, status: str) -> str:
    return (
        f"🛡️ **GOUVERNANCE** | {asset}\n"
        f"{status}\n"
        f"_Circuit breaker actif. Capital protégé._"
    )

def rejection_regime(asset: str, regime: str, reason: str) -> str:
    return (
        f"🛡️ **STOP** | {asset}\n"
        f"Régime {regime}. {reason}\n"
        f"_On reste en cash. Pas de trade contre le marché._"
    )

def rejection_trend(asset: str, regime: str) -> str:
    return (
        f"🛡️ **REFUS** | {asset}\n"
        f"Marché en {regime}. Breakout = piège en range.\n"
        f"_On attend le trend. Patience = edge._"
    )

def rejection_chaos(asset: str, reason: str) -> str:
    return (
        f"🚫 **CHAOS** | {asset}\n"
        f"{reason}\n"
        f"_Cash only. Capital préservé._"
    )

def market_sleeping(asset: str, adx: float = None, range_val: float = None, adx_min: float = 20) -> str:
    if adx is not None:
        return f"😴 **PATIENCE** | {asset} - ADX {adx:.1f} < {adx_min}. Marché endormi. _On attend._"
    r = f" (range {range_val:.3f})" if range_val is not None else ""
    return f"😴 **PATIENCE** | {asset} - Volatilité trop faible{r}. _Pas de signal clair._"

def single_shot_wait(asset: str, symbol: str) -> str:
    return f"🔒 **1 TRADE ACTIF** | {symbol} en cours. _On attend la sortie._"

def daily_limit(c: int, m: int) -> str:
    return (
        f"📊 **LIMITE JOUR** | {c}/{m} trades.\n"
        f"_Discipline. Pas de sur-trading._"
    )

def execution_fire(asset: str, side: str, stake: float, score: float, reason: str = "") -> str:
    r = f"\n_{reason}_" if reason else ""
    return (
        f"🚀 **EXÉCUTION** | {asset} {side} @ ${stake:.2f}\n"
        f"Score {score:.0f}/100. Stratégie validée.{r}"
    )

def execution_manual(asset: str, side: str, stake: float) -> str:
    return f"🔔 **SIGNAL** | {asset} {side} @ ${stake:.2f} — _Validation manuelle requise._"
