# Patch Spec: Sentinel_v5_2_ULTIMATE.mq5

## Scope
Update `Sentinel_v5_2_ULTIMATE.mq5` to:
1. Enrich trade-close reports with entry telemetry:
- `rsi_at_entry`
- `atr_at_entry`
- `spread_at_entry`
2. Add `Streak Guard` position-sizing control:
- If `consecutive_losses >= 1`, lot size is halved (`x0.5`).

## Files
- Modified: `Sentinel_v5_2_ULTIMATE.mq5`
- Added: `docs/PATCH_SPEC_SENTINEL_V52_REPORTS_STREAK_GUARD.md`

## Report Schema Changes
### Existing close report fields retained
- `event`, `ticket`, `symbol`, `type`, `volume`
- `entry_price`, `exit_price`, `profit`
- `spread_at_exit`, `atr_at_exit`
- `duration_seconds`, `exit_reason`
- `entry_time`, `exit_time`
- `consecutive_losses`, `comment`
- compatibility keys: `reason`, `time`

### New fields
- `rsi_at_entry` (double)
- `atr_at_entry` (double)
- `spread_at_entry` (int)

## Implementation Details
### Entry telemetry capture
- Added in-memory telemetry store keyed by `POSITION_TICKET`.
- Captured at successful entry for both:
  - internal scalper (`OnTick` Buy/Sell)
  - bridge-driven orders (`ExecuteTrade`)
- Sources:
  - RSI: `iRSI(symbol, _Period, RSIPeriod, PRICE_CLOSE)`
  - ATR: `iATR(symbol, _Period, ATRPeriod)`
  - Spread: `SYMBOL_SPREAD`

### Report write flow
- New close path `CloseWithReport(ticket, reason)`:
  1. Snapshot open-position data + entry telemetry
  2. Close position via `trade.PositionClose(ticket)`
  3. Update streak counter from realized close snapshot
  4. Write enriched `report_<ticket>.json`
  5. Remove telemetry entry

### Consecutive loss tracking
- Added runtime counter: `consecutiveLossesCount`
- On each successful close report:
  - `profit < 0` => increment
  - `profit >= 0` => reset to 0
- Report field `consecutive_losses` now comes from this counter.

### Streak Guard sizing rule
- Internal scalper entries:
  - `currentLot = BaseLotSize * adaptiveLotMultiplier`
  - If `consecutiveLossesCount >= 1`: `currentLot *= 0.5`
- Bridge entries (`ExecuteTrade`):
  - incoming `volume` is halved under same condition

## Added Inputs/Helpers
- New input: `ATRPeriod` (default `14`)
- New helpers:
  - `ReadCurrentRSI(symbol)`
  - `ReadCurrentATR(symbol)`
  - telemetry CRUD: save/load/remove by ticket

## Backward Compatibility
- `GenerateReport(ticket, reason)` kept as fallback minimal writer.
- `reason` and `time` keys preserved in enriched report JSON.

## Operational Validation Checklist
1. Open a trade and close at `TARGET_REACHED`.
2. Confirm `report_<ticket>.json` includes:
   - `rsi_at_entry`, `atr_at_entry`, `spread_at_entry`.
3. Force one losing close (`TIME_EXIT`/`MAX_LOSS` path).
4. Open next trade and verify lot/volume is halved.
5. Close with profit and verify streak resets (`consecutive_losses=0` on subsequent winning report).

## Known Constraints
- Entry telemetry is in-memory; EA restart before close may lose stored entry indicators.
- Fallback behavior in that case:
  - `rsi_at_entry` uses current RSI
  - `atr_at_entry` uses current ATR
  - `spread_at_entry` falls back to current spread
