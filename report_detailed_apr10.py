#!/usr/bin/env python3
"""Rapport DETAILLE de chaque position — 10 avril 2026"""
import re
from collections import defaultdict

MT5_LOG = "/Users/macbookpro/Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/Program Files/MetaTrader 5/logs/20260410.log"

data = open(MT5_LOG, 'rb').read()
text = data.decode('utf-16-le', errors='ignore')
lines = text.split('\n')

# Parse ALL deals
deals = []
for l in lines:
    if 'deal' in l.lower() and 'done' in l.lower():
        m = re.search(r'(\d{2}:\d{2}:\d{2})\.(\d+).*deal #(\d+)\s+(buy|sell)\s+(\S+)\s+(\S+)\s+at\s+(\S+)\s+done.*order #(\d+)', l, re.IGNORECASE)
        if m:
            deals.append({
                'time': m.group(1),
                'ms': m.group(2),
                'deal': m.group(3),
                'side': m.group(4).upper(),
                'volume': float(m.group(5)),
                'symbol': m.group(6),
                'price': float(m.group(7)),
                'order': m.group(8)
            })

# Parse modify/failed lines for SL/TP context
sl_tp = {}
for l in lines:
    m2 = re.search(r'(\d{2}:\d{2}:\d{2}).*modify #(\d+).*sl:\s*[\d.]+.*->\s*sl:\s*([\d.]+),\s*tp:\s*([\d.]+)\s+done', l, re.IGNORECASE)
    if m2:
        sl_tp[m2.group(2)] = {'sl': float(m2.group(3)), 'tp': float(m2.group(4))}

# Also parse "No money" fails
no_money = []
for l in lines:
    if 'No money' in l:
        m3 = re.search(r'(\d{2}:\d{2}:\d{2}).*failed.*?(buy|sell)\s+(\S+)\s+(\S+)', l, re.IGNORECASE)
        if m3:
            no_money.append({'time': m3.group(1), 'side': m3.group(2).upper(), 'vol': m3.group(3), 'sym': m3.group(4)})

def time_to_sec(t):
    h, m, s = t.split(':')
    return int(h)*3600 + int(m)*60 + int(s)

def duration_str(secs):
    if secs < 0: secs += 86400
    if secs < 60: return f"{secs}s"
    elif secs < 3600: return f"{secs//60}m{secs%60:02d}s"
    else: return f"{secs//3600}h{(secs%3600)//60:02d}m"

def session_name(t):
    h = int(t[:2])
    if h < 2: return "NUIT"
    elif h < 7: return "ASIA"
    elif h < 9: return "LONDON-OPEN"
    elif h < 13: return "LONDON"
    elif h < 15: return "NY-OPEN"
    elif h < 17: return "NY-AM"
    elif h < 20: return "NY-PM"
    elif h < 23: return "NUIT-US"
    else: return "NUIT"

def trend_from_pnl_and_side(entry_side, entry_price, exit_price):
    move = exit_price - entry_price
    if abs(move) < 0.5: return "RANGE"
    if move > 0: return "HAUSSIER"
    return "BAISSIER"

R = "\033[91m"; G = "\033[92m"; Y = "\033[93m"; C = "\033[96m"; B = "\033[1m"; X = "\033[0m"; W = "\033[97m"; M = "\033[95m"

print(f"\n{B}{C}{'='*90}{X}")
print(f"{B}{C}   RAPPORT DÉTAILLÉ — TOUTES LES POSITIONS — 10 AVRIL 2026{X}")
print(f"{B}{C}   Compte 101573422 — DerivBVI-Server-02{X}")
print(f"{B}{C}{'='*90}{X}")

# ==============================
# Group by symbol
# ==============================
by_symbol = defaultdict(list)
for d in deals:
    by_symbol[d['symbol']].append(d)

grand_total_pnl = 0
grand_total_trades = 0

for symbol in sorted(by_symbol.keys()):
    sym_deals = by_symbol[symbol]
    
    print(f"\n{B}{M}{'─'*90}{X}")
    print(f"{B}{M}   {symbol} — {len(sym_deals)} deals{X}")
    print(f"{B}{M}{'─'*90}{X}")
    
    # Pair positions
    positions_stack = []
    closed = []
    
    if 'Volatility' in symbol:
        # Special: pair sell->buy
        sells = [d for d in sym_deals if d['side'] == 'SELL']
        buys = [d for d in sym_deals if d['side'] == 'BUY']
        for i in range(min(len(sells), len(buys))):
            s, b = sells[i], buys[i]
            pnl = (b['price'] - s['price']) * s['volume']
            closed.append({'entry': s, 'exit': b, 'pnl': round(pnl, 2)})
    else:
        for d in sym_deals:
            if d['side'] == 'BUY':
                matched = False
                for i, p in enumerate(positions_stack):
                    if p['side'] == 'SELL':
                        if symbol in ['XAUUSD', 'GOLD']:
                            pnl = (p['price'] - d['price']) * d['volume'] * 100
                        elif symbol == 'USDJPY':
                            pnl = (d['price'] - p['price']) * d['volume'] * 100000 / d['price'] * -1
                            # Simplified: for 0.01 lot USDJPY
                            pnl = (p['price'] - d['price']) * d['volume'] * 1000 / d['price'] * 100
                        else:
                            pnl = (p['price'] - d['price']) * d['volume'] * 100000
                        closed.append({'entry': p, 'exit': d, 'pnl': round(pnl, 2)})
                        positions_stack.pop(i)
                        matched = True
                        break
                if not matched:
                    positions_stack.append(d)
            else:
                matched = False
                for i, p in enumerate(positions_stack):
                    if p['side'] == 'BUY':
                        if symbol in ['XAUUSD', 'GOLD']:
                            pnl = (d['price'] - p['price']) * d['volume'] * 100
                        elif symbol == 'USDJPY':
                            pnl = (d['price'] - p['price']) * d['volume'] * 1000 / d['price'] * 100
                        else:
                            pnl = (d['price'] - p['price']) * d['volume'] * 100000
                        closed.append({'entry': p, 'exit': d, 'pnl': round(pnl, 2)})
                        positions_stack.pop(i)
                        matched = True
                        break
                if not matched:
                    positions_stack.append(d)
    
    # Print each position in detail
    print(f"\n  {B}{W}{'#':>4} {'ENTRÉE':^10} {'SORTIE':^10} {'DURÉE':>8} {'TYPE':>6} {'VOL':>5} {'PRIX ENTRÉE':>12} {'PRIX SORTIE':>12} {'PnL($)':>9} {'PIPS':>7} {'TENDANCE':>10} {'SESSION':>12}{X}")
    print(f"  {'─'*120}")
    
    sym_pnl = 0
    sym_wins = 0
    sym_losses = 0
    
    for idx, c in enumerate(closed, 1):
        e = c['entry']
        x = c['exit']
        pnl = c['pnl']
        sym_pnl += pnl
        
        dur_sec = time_to_sec(x['time']) - time_to_sec(e['time'])
        dur = duration_str(dur_sec)
        
        if symbol in ['XAUUSD', 'GOLD']:
            pips = abs(x['price'] - e['price']) * 10
        elif symbol == 'USDJPY':
            pips = abs(x['price'] - e['price']) * 100
        else:
            pips = abs(x['price'] - e['price']) * 10000
        
        trend = trend_from_pnl_and_side(e['side'], e['price'], x['price'])
        sess = session_name(e['time'])
        
        if pnl > 0:
            col = G
            sym_wins += 1
            result = "WIN"
        elif pnl < 0:
            col = R
            sym_losses += 1
            result = "LOSS"
        else:
            col = Y
            result = "BE"
        
        sl_info = sl_tp.get(e['order'], {})
        sl_str = f" SL:{sl_info['sl']}" if sl_info.get('sl') else ""
        tp_str = f" TP:{sl_info['tp']}" if sl_info.get('tp') and sl_info['tp'] > 0 else ""
        
        print(f"  {col}{idx:>4} {e['time']:>10} {x['time']:>10} {dur:>8} {e['side']:>6} {e['volume']:>5.2f} {e['price']:>12.2f} {x['price']:>12.2f} {pnl:>+9.2f} {pips:>6.1f}p {trend:>10} {sess:>12}{X}{sl_str}{tp_str}")
    
    # Summary for this symbol
    wr = sym_wins / len(closed) * 100 if closed else 0
    avg_dur_sec = sum(time_to_sec(c['exit']['time']) - time_to_sec(c['entry']['time']) for c in closed) / len(closed) if closed else 0
    
    print(f"  {'─'*120}")
    col = G if sym_pnl >= 0 else R
    print(f"  {B}TOTAL {symbol}: {len(closed)} trades | WR: {wr:.1f}% ({sym_wins}W/{sym_losses}L) | PnL: {col}${sym_pnl:+.2f}{X} | Durée moy: {duration_str(int(avg_dur_sec))}")
    
    # Show remaining open positions
    if positions_stack:
        print(f"\n  {Y}{B}⚠ POSITIONS OUVERTES:{X}")
        for p in positions_stack:
            print(f"    {Y}{p['time']} | {p['side']} {p['volume']} @ {p['price']} (order #{p['order']}){X}")
    
    grand_total_pnl += sym_pnl
    grand_total_trades += len(closed)

# ==============================
# GRAND TOTAL
# ==============================
print(f"\n{B}{C}{'='*90}{X}")
print(f"{B}{C}   RÉSUMÉ GLOBAL — 10 AVRIL 2026{X}")
print(f"{B}{C}{'='*90}{X}")

col = G if grand_total_pnl >= 0 else R
print(f"\n  {B}Positions fermées: {grand_total_trades}{X}")
print(f"  {B}PnL total journée: {col}${grand_total_pnl:+.2f}{X}")

# No money events
if no_money:
    print(f"\n  {R}{B}⚠ REJETS 'No Money' ({len(no_money)}):{X}")
    for nm in no_money:
        print(f"    {R}{nm['time']} | {nm['side']} {nm['vol']} {nm['sym']}{X}")

# Timeline - distribution per 30min
print(f"\n  {B}ACTIVITÉ PAR TRANCHE DE 30 MIN:{X}")
all_closed = []
for symbol in by_symbol:
    sym_deals2 = by_symbol[symbol]
    # rebuild closed for all
for d in deals:
    all_closed.append(d)

time_slots = defaultdict(int)
for d in deals:
    h = int(d['time'][:2])
    m = int(d['time'][3:5])
    slot = f"{h:02d}:{0 if m < 30 else 30:02d}"
    time_slots[slot] += 1

for slot in sorted(time_slots):
    count = time_slots[slot]
    bar = "█" * min(count, 60)
    print(f"    {slot} | {bar} {count}")

print(f"\n{B}{C}{'='*90}{X}\n")
