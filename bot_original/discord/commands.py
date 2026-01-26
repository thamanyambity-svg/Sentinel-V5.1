from bot.journal.logger import load_trades
from bot.journal.metrics import win_rate, expectancy
from bot.risk.series import series_status
from bot.journal.audit import audit

from bot.state.pending import (
    set_pending_trade,
    get_pending_trade,
    clear_trade,
    confirm_trade
)

from bot.state.override import (
    enable_force,
    disable_force,
    is_force_enabled
)

from bot.state.deriv_flag import (
    enable_deriv,
    disable_deriv,
    is_deriv_enabled
)

from bot.config.runtime import (
    set_active_broker,
    get_active_broker
)

# =========================
# /status
# =========================
def status_command():
    trade = get_pending_trade()

    lines = [
        f"Broker actif : **{get_active_broker().upper()}**",
        f"Deriv : **{'ON' if is_deriv_enabled() else 'OFF'}**",
        f"Force : **{'ON' if is_force_enabled() else 'OFF'}**"
    ]

    if trade:
        lines.append(f"⏳ Trade en attente → {trade['asset']} {trade['side']}")
    else:
        lines.append("✅ Aucun trade en attente")

    return "\n".join(lines)


# =========================
# /broker
# =========================
def broker_command(name):
    set_active_broker(name)
    audit("BROKER_CHANGED", context={"broker": name})
    return f"🔁 Broker actif changé → **{name.upper()}**"


# =========================
# /deriv
# =========================
def deriv_command(mode):
    if mode == "on":
        enable_deriv()
        audit("DERIV_ENABLED")
        return "🔓 Deriv ACTIVÉ"
    else:
        disable_deriv()
        audit("DERIV_DISABLED")
        return "🔒 Deriv DÉSACTIVÉ"


# =========================
# /force
# =========================
def force_command(mode):
    if mode == "on":
        enable_force()
        audit("FORCE_ENABLED")
        return "⚠️ FORCE MODE ACTIVÉ (1 trade)"
    else:
        disable_force()
        audit("FORCE_DISABLED")
        return "✅ FORCE MODE DÉSACTIVÉ"


# =========================
# /propose
# =========================
def propose_command():
    if get_pending_trade():
        return "⛔ Un trade est déjà en attente"

    trades = load_trades()
    series = series_status(trades)

    market = {
        "asset": "V75",
        "side": "BUY",
        "score": 74
    }

    risk = {
        "allowed": series["allowed"],
        "reason": series["reason"]
    }

    stats = {
        "win_rate": win_rate(trades),
        "expectancy": expectancy(trades),
        "samples": len(trades)
    }

    if not risk["allowed"]:
        audit("TRADE_BLOCKED", context=risk)
        return f"⛔ Trade bloqué : {risk['reason']}"

    decision = {**market, "summary": stats}
    set_pending_trade(decision)

    audit("TRADE_PROPOSED", context=decision)

    return f"📌 Trade proposé → {market['asset']} {market['side']}"


# =========================
# /confirm
# =========================
def confirm_command():
    trade = get_pending_trade()
    if not trade:
        return "ℹ️ Aucun trade à confirmer"

    confirm_trade()
    audit("TRADE_CONFIRMED", context=trade)
    return "✅ Trade confirmé"


# =========================
# /reject
# =========================
def reject_command():
    trade = get_pending_trade()
    if not trade:
        return "ℹ️ Aucun trade à rejeter"

    clear_trade()
    audit("TRADE_REJECTED", context=trade)
    return "❌ Trade rejeté"
