import { NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';

export async function POST(req: Request) {
    // 1. SÉCURITÉ : Vérifier que c'est bien Sentinel qui parle
    const authHeader = req.headers.get('authorization');
    if (authHeader !== `Bearer ${process.env.SENTINEL_API_SECRET}`) {
        return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }

    try {
        const body = await req.json();

        // 2. ENREGISTREMENT DB (Pour le Dashboard Client)
        const trade = await prisma.tradeSignal.create({
            data: {
                ticket: body.ticket,
                symbol: body.symbol,
                type: body.type,
                openPrice: body.open_price,
                closePrice: body.close_price,
                profit: body.profit,
                duration: body.duration,
                // V9 Analytics
                v9Confluence: body.v9_confluence ?? null,
                v9MlProb: body.v9_ml_prob ?? null,
                v9Regime: body.v9_regime ?? null,
            }
        });

        return NextResponse.json({ success: true, id: trade.id });

    } catch (error) {
        console.error("Erreur Sentinel Webhook:", error);
        // On renvoie 200 même en cas d'erreur de doublon pour ne pas bloquer le bot Python
        return NextResponse.json({ received: true, note: "Duplicate or Error" }, { status: 200 });
    }
}
