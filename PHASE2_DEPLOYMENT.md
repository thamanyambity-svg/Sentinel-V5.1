# 🚀 PHASE 2: LIVE TRADING DEPLOYMENT GUIDE
## V9.2 XAUUSD Trading System (22 Features + Kill Switches)

---

## 📋 PHASE 2 OBJECTIVES

**Goal:** Accumulate 100+ real XAUUSD trades to validate orderflow features
**Timeline:** 2-3 weeks
**Position Size:** 0.01-0.05 lots (small, conservative)
**Success Criteria:** Sharpe ↑ from 0.09 → 0.13+

---

## ✅ PRE-DEPLOYMENT CHECKLIST

### EA Readiness
- [ ] Aladdin V7.19 compiled with trailing stop fixes
- [ ] MT5 bridge connected (status.json exists and updates)
- [ ] V9.2 models in MT5 path:
  - `sentinel_xgb_model.joblib` (139KB, 22 features)
  - `sentinel_scaler.joblib` (1KB)

### Python Environment
- [ ] xgboost==3.2.0 installed
- [ ] scikit-learn available (StandardScaler)
- [ ] sentinel_ml.py, sentinel_pipeline.py, phase2_monitor.py all present

### Account Setup
- [ ] Fresh XAUUSD account or small balance ($1000-5000)
- [ ] Leverage: 1:100 minimum
- [ ] Spread monitoring enabled
- [ ] VPS/stable connection configured

---

## 🎯 DEPLOYMENT STEPS

### Step 1: Verify System Status (5 minutes)

```bash
# Check models are deployed
ls -lh sentinel_*.joblib

# Verify MT5 bridge
python3 -c "import json; s=json.load(open('status.json')); print(f'MT5: {s[\"trading\"]}, Balance: ${s[\"balance\"]}')"

# Test signal pipeline
python3 sentinel_pipeline.py --predict
```

Expected output:
```
✅ Models: sentinel_xgb_model.joblib (139K) + sentinel_scaler.joblib (1K)
✅ MT5: trading=True, Balance=$1001.03
✅ Pipeline: BUY/SELL signal generated with kill switches=OK
```

### Step 2: Configure Position Sizing (10 minutes)

In Aladdin_Pro_V7_19_Live.mq5, set conservative parameters:

```mql5
// Around line ~120
input double LOT_SIZE = 0.01;           // Start micro: 0.01 lots
input int    MAX_POSITIONS = 1;         // One trade at a time
input double RISK_PER_TRADE = 0.5;      // 0.5% account risk

// Trailing stop (already fixed in this version)
input double Trail_ATR_Activation = 0.5;  // Activate at +1.5 pips (was 1.0)
input double Trail_ATR_Step = 0.25;       // Trailing increment (was 0.5)
```

### Step 3: Start Live Trading (Day 1 Morning)

```bash
# 1. Restart EA in MT5 Editor
# Menu → Tools → MetaQuotes → Open EA Editor
# Open Aladdin_Pro_V7_19_Live.mq5
# Click Compile (Ctrl+F9)
# Drag to chart (XAUUSD H1 or M5)

# 2. Monitor from Python
python3 phase2_monitor.py --dashboard

# Expected output:
# Status: Phase 2 - Live Trading
# Live Trades: 0/100 (0.0%)
```

### Step 4: Daily Monitoring Routine

**Every morning (15 min):**

```bash
# Check daily performance
python3 phase2_monitor.py --daily

# Output example:
# 2026-04-05:
#    trades: 3
#    wins: 2
#    win_rate: 66.7%
#    daily_pnl: +45.20
```

**Every week (30 min):**

```bash
# Analyze feature effectiveness
python3 phase2_monitor.py --feature-impact

# Output shows which features (delta, absorption, EMA, RSI, MACD)
# are predictive of winners vs losers
```

**Every 2 weeks (1 hour):**

```bash
# Full dashboard review
python3 phase2_monitor.py --status

# Decision points:
# - If Sharpe > 0.13 after 100 trades → APPROVE NIVEAU 2
# - If Sharpe ~0.09 after 100 trades → KEEP ORDERFLOW, drop marginal features
# - If Sharpe < 0.08 after 100 trades → ROLLBACK to 15 features
```

---

## 📊 LIVE DATA LOGGING

### What's Automatically Logged

Each completed trade records:
```json
{
  "ticket": 1,
  "symbol": "XAUUSD",
  "type": "buy",
  "volume": 0.01,
  "price_open": 4572.18,
  "price_close": 4572.80,
  "pnl": +62.0,
  "duration": 900,
  "time_open": 1712318400,
  "closed": true,

  // V9.2 Features (22 total)
  // Bloc 0 — Trend Confirmation
  "ema_20": 4565.43,
  "ema_50": 4568.92,
  "ema_slope": 0.234,
  "rsi": 52.1,
  "macd_histogram": 1.23,

  // Bloc 5 — Orderflow (V9.1)
  "delta": 0.62,
  "absorption": 1,

  // ... + 15 other features ...
}
```

### Manual Data Enrichment (if needed)

If MT5 logging fails, can backfill from trade_history.json:

```bash
# Generate synthetic training data if needed
python3 << 'EOF'
import json
import numpy as np

# Load existing trades
with open('trade_history.json') as f:
    trades = json.load(f)

# Add Phase 2 trades here as they arrive
# EA should auto-log via OnTradeTransaction()

with open('trade_history.json', 'w') as f:
    json.dump(trades, f, indent=2)
EOF
```

---

## ⚠️  KILL SWITCHES — WILL STOP TRADING IF:

| Condition | Threshold | Action |
|-----------|-----------|--------|
| 5 consecutive losses | >= 5 | STOP_TRADING |
| Drawdown | > 10% | REDUCE_SIZE |
| Spread spike | > 100 pips | SKIP_ENTRY |
| ATR spike | > 2x baseline | REDUCE_SIZE |

**Check kill switch status:**
```bash
python3 sentinel_pipeline.py --predict | grep "kill_switches"
```

If triggered:
- Review market conditions
- Check for news/data releases
- Manually restart if conditions normalize
- Do NOT force trades during alerts

---

## 📈 EXPECTED PERFORMANCE MARKERS

### Week 1 (7-10 trades expected)
- Win rate: 50-65% OK
- Sharpe: Not meaningful yet
- Drawdown: < 5%
- Action: Monitoring

### Week 2 (15-25 trades)
- Win rate: 50%+ target
- Sharpe: 0.01-0.05 (improving)
- Drawdown: < 8%
- Action: Monitor for feature trends

### Week 3 (30-50 trades)
- Win rate: 55%+ good
- Sharpe: 0.05-0.15 (evaluating)
- Drawdown: < 10%
- Action: Early signal/direction

### Week 4+ (80-100+ trades)
- DECISION POINT
- Sharpe > 0.13 → UNLOCK NIVEAU 2 ✅
- Sharpe 0.09-0.13 → Keep orderflow, trim 🟡
- Sharpe < 0.08 → Rollback to 15 features ❌

---

## 🔍 TROUBLESHOOTING

### Issue: "No trades after 3 days"

**Probable cause:** Low confluence signals (threshold 0.55 too high)

```bash
# Lower confluence threshold temporarily
# Edit sentinel_pipeline.py line ~55:
# CONFLUENCE_THRESHOLD = 0.50  # From 0.55

python3 sentinel_pipeline.py --retrain
```

### Issue: "5 consecutive losses — Kill Switch Triggered"

**Response:**
1. Check market conditions (news, volatility spike?)
2. Verify spread not abnormal
3. Review kill switch log:
```bash
python3 phase2_monitor.py --kill-switch-log
```
4. If false alarm, restart EA
5. If real market issue, stay out

### Issue: "High Sharpe but losing money"

**Most likely:** Position sizing too large or spread too wide

```bash
# Reduce lot size by 50%
# Edit Aladdin_Pro_V7_19_Live.mq5:
input double LOT_SIZE = 0.005;  # From 0.01
```

### Issue: "Orderflow features (delta, absorption) seem ineffective"

**This is OK:**
- Orderflow edge is subtle without real orderbook
- Might show up in Phase 3+ when combined with MTF alignment
- Keep as-is for validation; can trim later if Sharpe doesn't improve

---

## 📋 DECISION TREE (After 100 trades)

```
Sharpe > 0.13
     ↓
   ✅ YES → UNLOCK NIVEAU 2 (Multi-timeframe bias)
            - Add HTF (H1) bias features (3 new)
            - Add D1 trend direction (1 new)
            - Retrain with 28+ features
     ↑
   NO → Sharpe 0.09-0.13?
        ↓
      ✅ MARGINAL → TRIM & KEEP
                   - Drop MACD (lowest contribution)
                   - Keep delta + absorption (orderflow core)
                   - Keep EMA slope (critical filter)
                   - Retrain with 20 features
        ↓
      NO → Sharpe < 0.08
           ↓
         ❌ FAIL → ROLLBACK
                  - Drop all new features
                  - Return to 15-feature baseline
                  - Investigate root cause
                  - Start Phase 2 from scratch
```

---

## 🎯 SUCCESS METRICS

**Phase 2 is successful if:**
1. ✅ Accumulated 100+ trades in 2-3 weeks
2. ✅ No more than 2× kill switch activations
3. ✅ Sharpe ≥ 0.09 (not negative)
4. ✅ Max drawdown < 15%

**Then proceed to Phase 3:**
- NIVEAU 2: Multi-timeframe bias (if Sharpe > 0.13)
- NIVEAU 3: Advanced orderflow (OFI, volume acceleration)
- NIVEAU 4: Full risk management automation
- NIVEAU 5: Professional validation suite

---

## 📞 SUPPORT

**If system fails:**
1. Check Git commit history
```bash
git log --oneline | head -5
```

2. Verify models are loaded
```bash
python3 -c "from sentinel_ml import SentinelMLModel; m = SentinelMLModel(); print('✅ Model loaded')"
```

3. Review Phase 2 monitor
```bash
python3 phase2_monitor.py --status
```

4. Rollback if needed
```bash
git checkout 9ad1290  # Before kill switches
```

---

## 🎬 FINAL CHECKLIST BEFORE GOING LIVE

- [ ] EA compiled and attached to XAUUSD chart
- [ ] Position size = 0.01 lots
- [ ] Kill switches enabled (should be automatic)
- [ ] phase2_monitor.py copied and executable
- [ ] First trade expected within 2-4 hours
- [ ] Daily monitoring reminder set
- [ ] Decision criteria understood (Sharpe 0.13 gate)

**🚀 Ready to go live with V9.2!**
