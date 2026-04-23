#!/usr/bin/env python3
"""Rapport trades manuels du 10 avril 2026"""
import re

MT5_LOG = "/Users/macbookpro/Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/Program Files/MetaTrader 5/logs/20260410.log"

data = open(MT5_LOG, 'rb').read()
text = data.decode('utf-16-le', errors='ignore')
lines = text.split('\n')

deals = []
for l in lines:
    if 'deal' in l.lower() and 'done' in l.lower():
        m = re.search(r'(\d{2}:\d{2}:\d{2})\.\d+.*deal #(\d+)\s+(buy|sell)\s+(\S+)\s+(\S+)\s+at\s+(\S+)\s+done.*order #(\d+)', l, re.IGNORECASE)
        if m:
            deals.append({
                'time': m.group(1),
                'deal': m.group(2),
                'side': m.group(3).upper(),
                'volume': float(m.group(4)),
                'symbol': m.group(5),
                'price': float(m.group(6)),
                'order': m.group(7)
            })

# === XAUUSD ===
xau = [d for d in deals if d['symbol']=='XAUUSD']
positions = []
closed = []
for d in xau:
    if d['side'] == 'BUY':
        matched = False
        for i, p in enumerate(positions):
            if p['side'] == 'SELL':
                pnl = (p['price'] - d['price']) * d['volume'] * 100
                closed.append({'entry': p, 'exit': d, 'pnl': round(pnl, 2)})
                positions.pop(i)
                matched = True
                break
        if not matched:
            positions.append(d)
    else:
        matched = False
        for i, p in enumerate(positions):
            if p['side'] == 'BUY':
                pnl = (d['price'] - p['price']) * d['volume'] * 100
                closed.append({'entry': p, 'exit': d, 'pnl': round(pnl, 2)})
                positions.pop(i)
                matched = True
                break
        if not matched:
            positions.append(d)

total_pnl = sum(c['pnl'] for c in closed)
winners = [c for c in closed if c['pnl'] > 0]
losers = [c for c in closed if c['pnl'] < 0]
bes = [c for c in closed if c['pnl'] == 0]

R = "\033[91m"; G = "\033[92m"; Y = "\033[93m"; C = "\033[96m"; B = "\033[1m"; X = "\033[0m"

print(f"\n{B}{C}{'='*65}{X}")
print(f"{B}{C}   RAPPORT TRADES MANUELS — 10 AVRIL 2026 — Compte 101573422{X}")
print(f"{B}{C}{'='*65}{X}")
print(f"\n{B}Total deals dans le log MT5: {len(deals)}{X}")

print(f"\n{B}═══ XAUUSD (SCALPING MANUEL) ═══{X}")
print(f"  Round-trips: {len(closed)}")
print(f"  Gagnants: {G}{len(winners)}{X} | Perdants: {R}{len(losers)}{X} | BE: {Y}{len(bes)}{X}")
wr = len(winners)/len(closed)*100 if closed else 0
print(f"  Win Rate: {B}{wr:.1f}%{X}")
col = G if total_pnl >= 0 else R
print(f"  PnL total: {col}{B}${total_pnl:+.2f}{X}")
avg_win = sum(c['pnl'] for c in winners)/len(winners) if winners else 0
avg_loss = sum(c['pnl'] for c in losers)/len(losers) if losers else 0
print(f"  Gain moyen: {G}${avg_win:+.2f}{X} | Perte moy: {R}${avg_loss:+.2f}{X}")
gross_win = sum(c['pnl'] for c in winners)
gross_loss = sum(c['pnl'] for c in losers)
pf = abs(gross_win/gross_loss) if gross_loss else float('inf')
print(f"  Profit Factor: {B}{pf:.2f}{X}")

# By session
from collections import defaultdict
sessions = defaultdict(list)
for c in closed:
    h = int(c['entry']['time'][:2])
    if h < 2: s = 'Nuit (00-02h)'
    elif h < 7: s = 'Asia (02-07h)'
    elif h < 13: s = 'London (07-13h)'
    elif h < 17: s = 'NY AM (13-17h)'
    elif h < 20: s = 'NY PM (17-20h)'
    else: s = 'Nuit (20-00h)'
    sessions[s].append(c)

print(f"\n{B}PAR SESSION:{X}")
for s in ['Nuit (00-02h)', 'Asia (02-07h)', 'London (07-13h)', 'NY AM (13-17h)', 'NY PM (17-20h)', 'Nuit (20-00h)']:
    if s in sessions:
        sc = sessions[s]
        sp = sum(c['pnl'] for c in sc)
        sw = len([c for c in sc if c['pnl'] > 0])
        swr = sw/len(sc)*100
        col = G if sp >= 0 else R
        print(f"  {s:<18} {len(sc):>3} trades | WR:{swr:>5.1f}% | PnL:{col}${sp:+.2f}{X}")

# Top trades
sorted_c = sorted(closed, key=lambda x: x['pnl'], reverse=True)
print(f"\n{B}TOP 5 MEILLEURS:{X}")
for c in sorted_c[:5]:
    e, x2 = c['entry'], c['exit']
    print(f"  {G}${c['pnl']:+.2f}{X} | {e['side']} @ {e['price']} ({e['time']}) -> {x2['side']} @ {x2['price']} ({x2['time']})")

print(f"\n{B}TOP 5 PIRES:{X}")
for c in sorted_c[-5:]:
    e, x2 = c['entry'], c['exit']
    print(f"  {R}${c['pnl']:+.2f}{X} | {e['side']} @ {e['price']} ({e['time']}) -> {x2['side']} @ {x2['price']} ({x2['time']})")

# USDJPY (bot)
usdjpy = [d for d in deals if d['symbol']=='USDJPY']
if usdjpy:
    print(f"\n{B}═══ USDJPY (BOT Aladdin) ═══{X}")
    for d in usdjpy:
        print(f"  {d['time']} | {d['side']} {d['volume']} @ {d['price']}")

# Volatility
vol = [d for d in deals if 'Volatility' in d['symbol']]
if vol:
    print(f"\n{B}═══ Volatility 100 Index ═══{X}")
    v_buy = [d for d in vol if d['side']=='BUY']
    v_sell = [d for d in vol if d['side']=='SELL']
    if v_buy and v_sell:
        vpnl = (v_buy[0]['price'] - v_sell[0]['price']) * v_sell[0]['volume']
        col = G if vpnl >= 0 else R
        print(f"  SELL {v_sell[0]['volume']} @ {v_sell[0]['price']} ({v_sell[0]['time']}) -> BUY {v_buy[0]['volume']} @ {v_buy[0]['price']} ({v_buy[0]['time']})")
        print(f"  PnL: {col}${vpnl:+.2f}{X}")

# Open positions
if positions:
    print(f"\n{B}{Y}═══ POSITIONS RESTEES OUVERTES ═══{X}")
    for p in positions:
        print(f"  {p['time']} | {p['side']} {p['volume']} {p['symbol']} @ {p['price']}")

print(f"\n{B}{C}{'='*65}{X}\n")
