from bot.state.deriv_flag import enable_deriv, disable_deriv, is_deriv_enabled


def deriv_status():
    return "🟢 Deriv ENABLED" if is_deriv_enabled() else "🔴 Deriv DISABLED"


def deriv_enable():
    enable_deriv()
    return "⚠️ Deriv activé (runtime)"


def deriv_disable():
    disable_deriv()
    return "🛑 Deriv désactivé"
