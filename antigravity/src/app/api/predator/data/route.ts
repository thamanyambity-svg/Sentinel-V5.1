import { NextResponse } from 'next/server';
import fs from 'fs';
import path from "path";

export async function GET() {
  const MACRO_BIAS_PATH = "/Users/macbookpro/Downloads/bot_project/macro_bias.json";

  try {
    if (!fs.existsSync(MACRO_BIAS_PATH)) {
      return NextResponse.json({ error: "File not found" }, { status: 404 });
    }

    const fileContent = fs.readFileSync(MACRO_BIAS_PATH, 'utf-8');
    const data = JSON.parse(fileContent);

    // Map confidence string to numeric percentage
    const confidenceMap: Record<string, number> = {
      HIGH: 85, MEDIUM: 60, LOW: 35,
    };
    const confidenceRaw = data.confidence || 'MEDIUM';
    const confidenceNum = typeof confidenceRaw === 'number'
      ? confidenceRaw
      : (confidenceMap[confidenceRaw.toUpperCase()] ?? 60);

    // Normalize verdict: BUY_GOLD / SELL_GOLD -> BULLISH / BEARISH
    const rawVerdict = (data.verdict || 'NEUTRAL').toUpperCase();
    const verdictMap: Record<string, string> = {
      BUY_GOLD: 'BULLISH', SELL_GOLD: 'BEARISH',
      BULLISH: 'BULLISH', BEARISH: 'BEARISH', NEUTRAL: 'NEUTRAL',
      ACHAT: 'BULLISH', VENTE: 'BEARISH',
    };
    const verdict = verdictMap[rawVerdict] ?? 'NEUTRAL';

    // Estimate margin level from equity/balance
    const balance = data.balance || 0;
    const equity = data.equity || 0;
    const marginLevel = balance > 0 ? (equity / balance) * 100 : 0;

    return NextResponse.json({
      account: {
        balance,
        equity,
        marginLevel,
        marketOpen: true,
        goldPrice: data.gold_price || 0,
      },
      verdict: {
        bias: verdict,
        confidence: confidenceNum,
        reason: data.reason || '',
      },
      risk: {
        marketRisk: typeof data.risk === 'number' ? data.risk : 30,
        vix: data.vix || 15.0,
      },
      positions: (data.positions || []).map((p: any) => ({
        ticket: p.ticket || p.id || Math.random(),
        symbol: p.symbol || 'XAUUSD',
        type: p.type || 'BUY',
        volume: p.volume || p.size || 0,
        profit: p.profit || p.pnl || 0,
        sl: p.sl || null,
      })),
      chartData: (data.charts?.['5m'] || []).slice(-50).map((c: any) => {
         // Create Moving Average placeholders or calculate them if not provided
         return {
            time: new Date(c.time * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
            open: c.open,
            close: c.close,
            high: c.high,
            low: c.low,
            isUp: c.close >= c.open,
            volume: Math.random() * 100, // Volume placeholder if missing
         };
      }),
      logs: [
        { time: new Date().toLocaleTimeString(), symbol: 'SYS', msg: `Connexion MT5 active — Balance: $${balance.toFixed(2)}`, type: 'info' },
        { time: new Date().toLocaleTimeString(), symbol: 'AI', msg: `Manus Verdict: ${verdict} (Risk: ${data.risk || 30}/100)`, type: 'Alerte' },
        ...(data.chart_ticks || []).slice(-10).reverse().map((t: any) => ({
          time: new Date(t.time * 1000).toLocaleTimeString(),
          symbol: 'XAU/USD',
          msg: `Tick Price: ${t.price.toFixed(2)}`,
          type: 'Tick'
        }))
      ]
    });
  } catch (error) {
    console.error("Error reading MT5 bridge:", error);
    return NextResponse.json({ error: "Internal Server Error" }, { status: 500 });
  }
}
