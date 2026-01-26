from bot.journal.logger import load_trades
from bot.journal.metrics import win_rate, expectancy
from bot.risk.series import series_status
from bot.journal.audit import audit
from bot.ai_agents.professor_agent import ProfessorAgent

from bot.state.pending import get_pending_trade
from bot.state.override import enable_force, disable_force, is_force_enabled
from bot.state.deriv_flag import enable_deriv, disable_deriv, is_deriv_enabled
from bot.config.runtime import set_active_broker, get_active_broker

def status_command():
    trade = get_pending_trade()
    
    from bot.state.active_trades import get_active_trades
    active = get_active_trades()
    active_str = "AUCUN"
    if active:
        active_str = f"{len(active)} en cours ({', '.join([a['asset'] for a in active])})"

    lines = [
        f"🌐 Broker : **{get_active_broker().upper()}**",
        f"🔐 Trading Réel : **{'ACTIVÉ' if is_deriv_enabled() else 'DÉSACTIVÉ'}**",
        f"⚡ Mode Force : **{'ON' if is_force_enabled() else 'OFF'}**",
        f"⏳ Attente Confirm. : **{'OUI' if trade else 'NON'}**",
        f"🏃 En Cours : **{active_str}**"
    ]
    return "\n".join(lines)

def broker_command(name):
    set_active_broker(name)
    return f"🔄 Broker changé en : **{name.upper()}**"

def deriv_command(mode):
    if mode == "on":
        enable_deriv()
        return "🔓 Trading Réel **ACTIVÉ**"
    else:
        disable_deriv()
        return "🔒 Trading Réel **DÉSACTIVÉ**"

def force_command(mode):
    if mode == "on":
        enable_force()
        return "⚠️ **MODE FORCE ACTIVÉ** (Le prochain signal sera validé sans filtres)"
    else:
        disable_force()
        return "✅ **MODE FORCE DÉSACTIVÉ**"

async def balance_command(bot):
    if not hasattr(bot, "deriv_client") or not bot.deriv_client:
        return "❌ Connexion Deriv non initialisée."
    try:
        data = await bot.deriv_client.get_balance()
        if not data: return "❌ Impossible de lire le solde."
        
        bal = data.get("balance", "0.00")
        cur = data.get("currency", "USD")
        acc_id = data.get("id") or data.get("loginid") or "N/A"
        
        # MT5 Balance
        from bot.bridge.mt5_interface import MT5Bridge
        bridge = MT5Bridge()
        raw_status = bridge.get_raw_status()
        mt5_bal = raw_status.get("balance", "N/A")
        if isinstance(mt5_bal, float): mt5_bal = f"{mt5_bal:.2f} USD"
        
        return (
            f"💰 **SOLDE MULTI-AVATAR**\n"
            f"💳 **Options (VRTC)** : `{bal} {cur}`\n"
            f"📉 **MT5 (Sentinel)** : `{mt5_bal}`\n"
            f"🆔 Compte Maître : `{acc_id}`"
        )
    except Exception as e:
        return f"❌ Erreur Balance : {e}"

def daily_command():
    from bot.broker.trade_counter import get_trade_count, get_max_trades
    c, m = get_trade_count(), get_max_trades()
    return f"📈 **STATS DU JOUR**\n🚀 Trades : `{c} / {m}`\n🔋 Restant : `{m - c}`"

def help_command():
    return (
        "🛠️ **Commandes disponibles** :\n"
        "`!status` : État du bot\n"
        "`!balance` : Votre solde Deriv\n"
        "`!daily` : Limite de trades\n"
        "`!deriv on/off` : Activer le trading réel\n"
        "`!broker deriv/paper` : Changer de compte\n"
        "`!force on/off` : Ignorer les filtres\n"
        "`!report` : Rapport AI immédiat"
    )

def professor_command():
    try:
        prof = ProfessorAgent()
        return prof.analyze_24h_window()
    except Exception as e:
        return f"❌ Erreur Rapport : {e}"
