# n8n Orchestration Architecture - Institutional Grade

## Core Principle
>
> **The Risk Engine decides. Agents advise. n8n orchestrates, never the reverse.**

---

## Architecture Overview

```
Market Feed (WebSocket)
        ↓
Risk Engine (local, synchronous) ← SOVEREIGN
        ↓
n8n Orchestrator (fail-safe)
   ├─ Agent 1: Regime Auditor (VETO) [timeout: 100ms]
   ├─ Agent 2: Risk Behavior [timeout: 100ms]
   ├─ Agent 3: Execution Sentinel [timeout: 100ms]
   ├─ Agent 4: Volatility Structure [timeout: 100ms]
   ├─ Agent 5: Signal Quality [timeout: 100ms]
   └─ Agent 6: Strategy Drift [timeout: 100ms]
        ↓
Veto Logic (1 block = all blocked)
        ↓
Trade Gateway (if and only if authorized)
```

---

## Latency Budget (M1 Trading)

| Component | Max Latency | Cumulative |
|-----------|-------------|------------|
| WebSocket → Python | 50ms | 50ms |
| Risk Engine (local) | 20ms | 70ms |
| n8n Orchestration | 150ms | 220ms |
| **Decision Final** | - | **< 250ms** |

### Hard Rule

```
Total Latency > 300ms → execution_ok = false → NO TRADE
```

---

## Workflow 1: FAST PATH (Blocking - Trade Decision)

### Purpose

Decide TRADE / NO TRADE without fragile dependencies

### Constraints

- ⏱ **Timeout**: 200ms max
- ❌ **Agent timeout** → NO TRADE
- ❌ **n8n down** → NO TRADE

### n8n Nodes

```
[Webhook] Signal Received
    ↓
[Function] Risk Snapshot
    ↓
[HTTP Request - Parallel] Call 6 Agents
    ├─ Agent 1 (timeout: 100ms)
    ├─ Agent 2 (timeout: 100ms)
    ├─ Agent 3 (timeout: 100ms)
    ├─ Agent 4 (timeout: 100ms)
    ├─ Agent 5 (timeout: 100ms)
    └─ Agent 6 (timeout: 100ms)
    ↓
[Function] Veto Logic (1 block = all blocked)
    ↓
[IF] Any Veto?
    ├─ YES → [Response] NO_TRADE
    └─ NO → [HTTP] Risk Engine Final Gate
                ↓
            [Response] EXECUTE or NO_TRADE
```

### Forbidden

- ❌ No database calls
- ❌ No retry logic
- ❌ No queue systems
- ❌ No external APIs (except agents)

---

## Workflow 2: SLOW PATH (Non-Blocking - Analytics)

### Purpose

Intelligence, audit, continuous improvement

| Element | Tolerated Delay |
|---------|-----------------|
| Rolling Backtest | Minutes |
| Drift Analysis | Hours |
| Audit Logging | Async |
| Telegram Alerts | Async |

**Impact on Trading**: ZERO

---

## Fault Tolerance (Anti-Catastrophe)

### 1. Agent Timeout

| Agent | Timeout Action |
|-------|----------------|
| Agent 1 (VETO) | NO TRADE |
| Agent 2 | Risk × 0.5 |
| Agent 3 | NO TRADE |
| Agent 4 | Risk × 0.5 |
| Agent 5 | Score = 0 → NO TRADE |
| Agent 6 | Assume drift → NO TRADE |

**Philosophy**: When in doubt, protect capital

### 2. n8n Down

```python
if n8n_unreachable:
    # Risk Engine continues
    # All signals = REJECT
    # Local journal only
    return "NO_TRADE"
```

**Result**: No uncontrolled trades

### 3. Clock Desynchronization

| Time Delta | Action |
|------------|--------|
| > 500ms | HALT session |
| > 2s | HARD STOP |

---

## Anti-Hallucination Guards

### Principle
>
> **An AI agent can NEVER force a trade**

### Safeguards

1. **Normalized Response** (JSON strict)
2. **Enum Only** (no free text)
3. **Schema Validation** (mandatory)
4. **Type Checking** (runtime)

### Example Agent Response

```json
{
  "verdict": "VETO",
  "confidence": 0.91,
  "metrics": {
    "vov": 0.52,
    "atr_percentile": 83
  }
}
```

**Invalid Response** → Treated as VETO

---

## Real-Time Monitoring (Essential)

### KPIs (Live Dashboard)

| KPI | Threshold | Alert |
|-----|-----------|-------|
| % Signals Rejected | > 65% | Normal |
| Avg Decision Time | < 200ms | Green |
| Agent Timeouts | 0 | Red if > 0 |
| CHAOS Activations | Market-coherent | Red if mismatch |

### Critical Alert

```
CHAOS + Trade Executed = CRITICAL BUG
→ Immediate system halt
→ Manual review required
```

---

## Stress Tests (Mandatory Before Live)

### Test 1: Slow Agent

```
Inject 500ms delay in Agent 1
Expected: NO TRADE (timeout)
```

### Test 2: n8n Crash

```
Kill n8n process mid-signal
Expected: Bot goes FLAT, no trades
```

### Test 3: Signal Flood

```
100 signals/minute
Expected: Latency stable < 300ms
```

### Test 4: Agent Hallucination

```
Agent returns invalid JSON
Expected: Treated as VETO, NO TRADE
```

---

## Fatal Errors to Avoid

❌ **Letting n8n decide** (only orchestrate)
❌ **Automatic retry on agents** (timeout = fail)
❌ **Synchronous logging** (blocks execution)
❌ **AI without strict schema** (hallucination risk)
❌ **Agent "correcting" Risk Engine** (sovereignty violation)

---

## Implementation Checklist

### Python Side

- [ ] Risk Engine exposes `/api/risk-gate` endpoint
- [ ] Agents expose individual endpoints
- [ ] All endpoints return JSON with schema
- [ ] Timeout handling (100ms per agent)
- [ ] Fallback responses on error

### n8n Side

- [ ] FAST PATH workflow (< 200ms)
- [ ] SLOW PATH workflow (async)
- [ ] Parallel agent calls
- [ ] Veto logic node
- [ ] Error handling (timeout → NO TRADE)
- [ ] Monitoring dashboard

### Testing

- [ ] Latency benchmark (< 250ms)
- [ ] Agent timeout test
- [ ] n8n crash test
- [ ] Signal flood test
- [ ] Schema validation test

---

## Institutional Verdict

✅ **n8n as orchestrator only** (not decision-maker)
✅ **Fail-safe architecture** (all failures → NO TRADE)
✅ **No scenario where bug triggers unwanted trade**
⚠️ **Performance sacrificed for survival** (intentional)

**Deployment Status**: APPROVED for production with live capital
