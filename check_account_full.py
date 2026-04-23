"""Analyse complète du compte Deriv réel — positions, P&L, balance"""
import asyncio, json, ssl, os
from dotenv import load_dotenv
import websockets

load_dotenv()
TOKEN = os.getenv("DERIV_API_TOKEN")
APP_ID = os.getenv("DERIV_APP_ID", "1089")

async def check():
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    uri = f"wss://ws.derivws.com/websockets/v3?app_id={APP_ID}"

    async with websockets.connect(uri, ssl=ssl_context) as ws:
        # === AUTH ===
        await ws.send(json.dumps({"authorize": TOKEN}))
        auth = json.loads(await ws.recv())
        if "error" in auth:
            print(f"Auth Error: {auth['error']['message']}")
            return

        info = auth["authorize"]
        print(f"Connecte: {info.get('email','?')}")
        print(f"Compte: {info.get('loginid','?')} | Type: {info.get('account_type','?')}")
        print(f"Balance: {info.get('balance','?')} {info.get('currency','?')}")

        # === COMPTES DISPONIBLES ===
        accts = info.get("account_list", [])
        print(f"\nComptes disponibles ({len(accts)}):")
        for a in accts:
            real = "REEL" if not a.get("is_virtual", True) else "DEMO"
            print(f"  - {a['loginid']} | {real} | {a.get('currency','?')}")

        # === PORTFOLIO ===
        await ws.send(json.dumps({"portfolio": 1}))
        port = json.loads(await ws.recv())
        if "portfolio" in port and "contracts" in port["portfolio"]:
            positions = port["portfolio"]["contracts"]
            print(f"\nPositions ouvertes: {len(positions)}")
            for p in positions:
                print(f"  ID: {p.get('contract_id','?')}")
                print(f"    Type: {p.get('contract_type','?')} | Symbol: {p.get('symbol','?')}")
                print(f"    Buy: {p.get('buy_price','?')} | Payout: {p.get('payout','?')}")
                print(f"    Expiry: {p.get('expiry_time','?')}")
        else:
            print("\nAucune position ouverte (portfolio).")

        # === PROPOSAL OPEN CONTRACT (P&L temps réel) ===
        await ws.send(json.dumps({"proposal_open_contract": 1}))
        poc = json.loads(await ws.recv())
        if "proposal_open_contract" in poc:
            contracts = poc["proposal_open_contract"]
            if isinstance(contracts, dict):
                contracts = [contracts] if contracts.get("contract_id") else []
            if contracts:
                print("\nDetails positions avec P&L temps reel:")
                for c in contracts:
                    if isinstance(c, dict) and c.get("contract_id"):
                        profit = float(c.get("profit", 0))
                        direction = "GAIN" if profit >= 0 else "PERTE"
                        print(f"  [{direction}] {c.get('display_name', c.get('symbol','?'))} | {c.get('contract_type','?')}")
                        print(f"    Achat: {c.get('buy_price','?')} | Valeur actuelle: {c.get('bid_price','?')}")
                        print(f"    P&L: {profit} {c.get('currency','')}")
                        print(f"    Entree: {c.get('entry_spot_display_value','?')} | Actuel: {c.get('current_spot_display_value','?')}")
                        print(f"    Date achat: {c.get('date_start','?')} | Expiry: {c.get('date_expiry','?')}")
                        print()
            else:
                print("\nAucun contrat ouvert (proposal_open_contract).")
        else:
            print("\nAucun contrat ouvert.")

        # === DERNIÈRES TRANSACTIONS ===
        await ws.send(json.dumps({"profit_table": 1, "description": 1, "limit": 10, "sort": "DESC"}))
        pt = json.loads(await ws.recv())
        if "profit_table" in pt and "transactions" in pt["profit_table"]:
            txs = pt["profit_table"]["transactions"]
            print(f"\n10 dernieres transactions:")
            total_pnl = 0
            for t in txs:
                buy = float(t.get("buy_price", 0))
                sell = float(t.get("sell_price", 0))
                pnl = sell - buy
                total_pnl += pnl
                direction = "+" if pnl >= 0 else ""
                print(f"  {t.get('shortcode','?')} | Buy: {buy} | Sell: {sell} | PnL: {direction}{pnl:.2f}")
            print(f"  --- Total PnL (10 dernieres): {total_pnl:.2f}")

asyncio.run(check())
