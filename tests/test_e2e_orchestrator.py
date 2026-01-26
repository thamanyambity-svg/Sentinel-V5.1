from bot.workflow.orchestrator import run_orchestrator
from bot.state.pending import set_pending_trade, confirm_trade, clear_trade
from bot.state.override import enable_force, disable_force
from bot.state.deriv_flag import enable_deriv, disable_deriv
from bot.config.runtime import set_active_broker
from bot.state.risk import reset_daily_limits


def setup_function():
    clear_trade()
    disable_force()
    disable_deriv()
    set_active_broker("paper")
    reset_daily_limits()


def test_idle():
    assert run_orchestrator() is None


def test_paper_execution():
    set_pending_trade({"asset": "V75", "side": "BUY", "amount": 10})
    confirm_trade()
    result = run_orchestrator()
    assert result["status"] == "EXECUTED"
    assert result["broker"] == "PAPER"


def test_deriv_off_fallback_paper():
    set_active_broker("deriv")
    set_pending_trade({"asset": "V75", "side": "BUY"})
    confirm_trade()
    result = run_orchestrator()
    assert result["broker"] == "PAPER"


def test_deriv_safe_execution():
    set_active_broker("deriv")
    enable_deriv()
    set_pending_trade({"asset": "V75", "side": "SELL"})
    confirm_trade()
    result = run_orchestrator()
    assert result["broker"] == "DERIV_SAFE"


def test_invalid_trade_rejected():
    set_active_broker("deriv")
    enable_deriv()
    set_pending_trade({"asset": "", "side": "BUY"})
    confirm_trade()
    result = run_orchestrator()
    assert result["status"] == "REJECTED"


def test_force_execution():
    enable_force()
    set_pending_trade({"asset": "INVALID", "side": "BUY"})
    confirm_trade()
    result = run_orchestrator()
    assert result["status"] == "EXECUTED"
