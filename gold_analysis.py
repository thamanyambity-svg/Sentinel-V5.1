"""
gold_analysis.py — Analyse automatique XAUUSD 1h avant l'Overnight Hedge
Lancé automatiquement par run_all.sh à 19h55 GMT+0 (20h55 Paris)
Écrit : gold_analysis.json  →  lu par dashboard + Antigravity
"""

import json, os, time, datetime, sys
from pathlib import Path
from mt5_context import get_current_mt5_context

BASE = Path(__file__).parent

# ── Chemin vers les fichiers MT5 ──────────────────────────────
MT5_PATH = os.environ.get(
    "MT5_PATH",
    os.path.expanduser(
        "~/Library/Application Support/net.metaquotes.wine.metatrader5"
        "/drive_c/users/user/AppData/Roaming/MetaQuotes/Terminal/Common/Files"
    ),
)

def find(f):
    p = Path(MT5_PATH) / f
    if p.exists(): return p
    p2 = BASE / f
    if p2.exists(): return p2
    return None

def write_json(filename, data):
    """Écrit dans le dossier local ET dans MT5 Common Files."""
    local = BASE / filename
    with open(local, "w") as f:
        json.dump(data, f, indent=2)
    mt5 = Path(MT5_PATH) / filename
    try:
        with open(mt5, "w") as f:
            json.dump(data, f, indent=2)
    except:
        pass  # MT5 pas accessible, pas grave

def load_ticks():
    p = find("ticks_v3.json")
    if not p: return []
    try:
        return json.loads(p.read_text())
    except:
        return []

def load_history():
    p = find("trade_history.json")
    if not p: return []
    try:
        d = json.loads(p.read_text())
        return d.get("trades", [])
    except:
        return []

def analyze_gold():
    """
    Analyse multi-facteurs XAUUSD pour déterminer la tendance EOD.
    Retourne : { direction, confidence, signals, recommendation }
    """
    ticks  = load_ticks()
    trades = load_history()

    # Récupération du contexte du compte
    context_mgr = get_current_mt5_context(MT5_PATH)
    ctx = context_mgr.refresh()

    # ── 1. Données temps réel depuis ticks_v3.json ────────────
    gold_tick = next((t for t in ticks if t.get("sym") in ["XAUUSD","GOLD","XAUUSDm"]), None)

    signals = []
    score   = 0  # positif = BULLISH, négatif = BEARISH

    if gold_tick:
        rsi      = float(gold_tick.get("rsi", 50))
        adx      = float(gold_tick.get("adx", 20))
        atr      = float(gold_tick.get("atr", 5))
        regime   = int(gold_tick.get("regime", 0))
        ema_fast = float(gold_tick.get("ema_fast", 0))
        ema_slow = float(gold_tick.get("ema_slow", 0))
        bid      = float(gold_tick.get("bid", 0))
        spread   = int(gold_tick.get("spread", 999))

        # Signal 1 : Régime (SuperTrend)
        if regime == 1:
            score += 2
            signals.append({"name": "SuperTrend", "value": "BULLISH", "weight": 2})
        elif regime == -1:
            score -= 2
            signals.append({"name": "SuperTrend", "value": "BEARISH", "weight": -2})
        else:
            signals.append({"name": "SuperTrend", "value": "NEUTRAL", "weight": 0})

        # Signal 2 : EMA alignment
        if ema_fast > 0 and ema_slow > 0:
            ema_diff_pct = (ema_fast - ema_slow) / ema_slow * 100
            if ema_fast > ema_slow:
                w = 2 if ema_diff_pct > 0.1 else 1
                score += w
                signals.append({"name": "EMA_Align", "value": f"BULLISH (+{ema_diff_pct:.3f}%)", "weight": w})
            else:
                w = -2 if ema_diff_pct < -0.1 else -1
                score += w
                signals.append({"name": "EMA_Align", "value": f"BEARISH ({ema_diff_pct:.3f}%)", "weight": w})

        # Signal 3 : RSI
        if rsi >= 70:
            score -= 2  # Overbought -> Bearish Reversal
            signals.append({"name": "RSI", "value": f"{rsi:.1f} OVERBOUGHT (Reversal)", "weight": -2})
        elif rsi <= 30:
            score += 2  # Oversold -> Bullish Reversal
            signals.append({"name": "RSI", "value": f"{rsi:.1f} OVERSOLD (Reversal)", "weight": 2})
        elif rsi >= 55:
            score += 1
            signals.append({"name": "RSI", "value": f"{rsi:.1f} BULLISH", "weight": 1})
        elif rsi <= 45:
            score -= 1
            signals.append({"name": "RSI", "value": f"{rsi:.1f} BEARISH", "weight": -1})
        else:
            signals.append({"name": "RSI", "value": f"{rsi:.1f} NEUTRAL", "weight": 0})

        # Signal 4 : ADX (force de la tendance)
        if adx >= 30:
            signals.append({"name": "ADX", "value": f"{adx:.1f} STRONG (amplificateur x1.5)", "weight": 0})
            score = int(score * 1.5)
        elif adx < 20:
            signals.append({"name": "ADX", "value": f"{adx:.1f} WEAK (signal réduit)", "weight": 0})
            score = int(score * 0.5)
        else:
            signals.append({"name": "ADX", "value": f"{adx:.1f} MODERATE", "weight": 0})

        # Signal 5 : Spread (qualité d'exécution)
        spread_ok = spread <= 120
        signals.append({"name": "Spread", "value": f"{spread} pts {'✓ OK' if spread_ok else '⚠ ÉLEVÉ'}", "weight": 0})

    else:
        signals.append({"name": "DATA", "value": "ticks_v3.json non disponible", "weight": 0})

    # ── 2. Perf récente GOLD (7 derniers jours) ───────────────
    gold_trades = [t for t in trades
                   if t.get("symbol") in ["XAUUSD","GOLD","XAUUSDm"]
                   and time.time() - float(t.get("time_open", 0)) < 86400 * 7]

    if gold_trades:
        recent_pnl  = sum(float(t.get("pnl", 0)) for t in gold_trades)
        recent_wins = sum(1 for t in gold_trades if float(t.get("pnl", 0)) > 0)
        recent_wr   = recent_wins / len(gold_trades) * 100

        # Biais directionnel des trades récents gagnants
        buy_wins  = sum(1 for t in gold_trades if t.get("type") == "buy"  and float(t.get("pnl",0)) > 0)
        sell_wins = sum(1 for t in gold_trades if t.get("type") == "sell" and float(t.get("pnl",0)) > 0)

        signals.append({
            "name": "Recent_GOLD",
            "value": f"{len(gold_trades)} trades | WR={recent_wr:.0f}% | PnL=${recent_pnl:.2f}",
            "weight": 0
        })
        if buy_wins > sell_wins * 1.5:
            score += 1
            signals.append({"name": "Direction_Hist", "value": f"BUY dominant ({buy_wins}W vs {sell_wins}W)", "weight": 1})
        elif sell_wins > buy_wins * 1.5:
            score -= 1
            signals.append({"name": "Direction_Hist", "value": f"SELL dominant ({sell_wins}W vs {buy_wins}W)", "weight": -1})

    # ── 3. Décision finale ────────────────────────────────────
    max_score   = 8
    confidence  = min(abs(score) / max_score * 100, 95)

    if score >= 5:
        direction      = "STRONG BUY"
        recommendation = f"DOMINANTS BUY ({EOD_dominant_count()}x) + HEDGES SELL"
    elif score <= -5:
        direction      = "STRONG SELL"
        recommendation = f"DOMINANTS SELL ({EOD_dominant_count()}x) + HEDGES BUY"
    elif score >= 2:
        direction      = "BUY"
        recommendation = "DOMINANTS BUY (1x) + HEDGES SELL"
    elif score <= -2:
        direction      = "SELL"
        recommendation = "DOMINANTS SELL (1x) + HEDGES BUY"
    else:
        direction      = "NEUTRAL"
        recommendation = "Signal faible — hedge équilibré recommandé. Prudence."
        confidence     = max(confidence, 30)

    # Ajustement selon le contexte (Deriv Real vs Demo)
    if ctx and ctx.get("mode") == "REAL":
        recommendation = "⚠️ [REAL ACCOUNT] " + recommendation
        signals.append({"name": "Account_Mode", "value": f"REAL ({ctx['broker']})", "weight": 0})

    now = datetime.datetime.utcnow()
    result = {
        "timestamp":      now.isoformat() + "Z",
        "ts":             int(time.time()),
        "symbol":         "XAUUSD",
        "direction":      direction,
        "score":          score,
        "confidence":     round(confidence, 1),
        "recommendation": recommendation,
        "signals":        signals,
        "eod_trigger":    "20:55 GMT+0",
        "analysis_done":  True,
        "gold_tick":      gold_tick,
        "context":        ctx
    }

    write_json("gold_analysis.json", result)

    print(f"\n{'═'*50}")
    print(f"  GOLD EOD ANALYSIS — {now.strftime('%H:%M:%S')} UTC")
    if ctx:
        print(f"  Account     : {ctx['broker']} {ctx['mode']} ({ctx['account']})")
    print(f"{'═'*50}")
    print(f"  Direction   : {direction}")
    print(f"  Score       : {score:+d} / {max_score}")
    print(f"  Confidence  : {confidence:.0f}%")
    print(f"  Recommand.  : {recommendation}")
    print(f"{'─'*50}")
    for s in signals:
        w = s['weight']
        icon = "▲" if w > 0 else ("▼" if w < 0 else "●")
        print(f"  {icon} {s['name']:<18} {s['value']}")
    print(f"{'═'*50}\n")

    return result

def EOD_dominant_count():
    return 3  # Correspond à EOD_Dominant_Count dans le bot MQL5

if __name__ == "__main__":
    analyze_gold()
