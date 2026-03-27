import { prisma } from '@/lib/prisma';
import ProfitChart from '@/components/dashboard/ProfitChart';
import { format } from 'date-fns';

export const dynamic = 'force-dynamic'; // Important : Pour ne pas mettre en cache les résultats

export default async function DashboardPage() {
    // 1. Récupérer les 50 derniers trades de Sentinel
    const trades = await prisma.tradeSignal.findMany({
        orderBy: { closedAt: 'asc' }, // Ordre chronologique pour le graphique
        take: 50,
    });

    // 2. V9 Analytics
    const v9Trades = trades.filter(t => t.v9Confluence !== null);
    const avgConfluence = v9Trades.length > 0
        ? v9Trades.reduce((s, t) => s + (t.v9Confluence ?? 0), 0) / v9Trades.length
        : 0;
    const avgMlProb = v9Trades.length > 0
        ? v9Trades.reduce((s, t) => s + (t.v9MlProb ?? 0), 0) / v9Trades.length
        : 0;
    const regimeCounts = v9Trades.reduce((acc, t) => {
        if (t.v9Regime) acc[t.v9Regime] = (acc[t.v9Regime] || 0) + 1;
        return acc;
    }, {} as Record<string, number>);
    const dominantRegime = Object.entries(regimeCounts).sort((a, b) => b[1] - a[1])[0]?.[0] ?? '—';

    return (
        <div className="p-8 bg-gray-50 min-h-screen font-sans">
            <div className="max-w-4xl mx-auto">
                <div className="flex justify-between items-center mb-6">
                    <h1 className="text-2xl font-bold text-gray-900">Tableau de Bord Investisseur</h1>
                    <div className="text-sm text-gray-500 bg-white px-3 py-1 rounded-full shadow-sm border">
                        Live Status: <span className="text-green-500 font-bold">● Synchronized</span>
                    </div>
                </div>

                {/* V9 Stats Cards */}
                <div className="grid grid-cols-3 gap-4 mb-8">
                    <div className="bg-white p-4 rounded-xl shadow-sm border">
                        <div className="text-xs text-gray-500 uppercase">V9 Confluence Moy.</div>
                        <div className="text-2xl font-bold text-blue-600">{(avgConfluence * 100).toFixed(0)}%</div>
                    </div>
                    <div className="bg-white p-4 rounded-xl shadow-sm border">
                        <div className="text-xs text-gray-500 uppercase">V9 ML Accuracy</div>
                        <div className="text-2xl font-bold text-green-600">{(avgMlProb * 100).toFixed(0)}%</div>
                    </div>
                    <div className="bg-white p-4 rounded-xl shadow-sm border">
                        <div className="text-xs text-gray-500 uppercase">Régime Dominant</div>
                        <div className="text-2xl font-bold">{dominantRegime}</div>
                    </div>
                </div>

                {/* Le Graphique Live */}
                <div className="mb-8">
                    <ProfitChart trades={trades} />
                </div>

                {/* Liste des derniers trades */}
                <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
                    <table className="w-full text-sm text-left">
                        <thead className="bg-gray-50 text-gray-500 uppercase text-xs">
                            <tr>
                                <th className="px-6 py-3">Symbole</th>
                                <th className="px-6 py-3">Type</th>
                                <th className="px-6 py-3">Profit</th>
                                <th className="px-6 py-3">ML Score</th>
                                <th className="px-6 py-3">Confluence</th>
                                <th className="px-6 py-3">Régime</th>
                                <th className="px-6 py-3">Heure</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-100">
                            {trades.length === 0 ? (
                                <tr>
                                    <td colSpan={7} className="px-6 py-8 text-center text-gray-400">
                                        En attente du premier trade de Sentinel...
                                    </td>
                                </tr>
                            ) : (
                                trades.slice().reverse().slice(0, 5).map((t) => (
                                    <tr key={t.id} className="hover:bg-gray-50 transition-colors">
                                        <td className="px-6 py-4 font-medium text-gray-900">{t.symbol}</td>
                                        <td className="px-6 py-4">
                                            <span className={`px-2 py-1 rounded text-xs font-bold ${t.type === 'BUY' ? 'bg-blue-50 text-blue-600' : 'bg-orange-50 text-orange-600'}`}>
                                                {t.type}
                                            </span>
                                        </td>
                                        <td className={`px-6 py-4 font-bold ${t.profit >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                                            {t.profit > 0 ? '+' : ''}{t.profit.toFixed(2)}$
                                        </td>
                                        <td className="px-6 py-4">
                                            {t.v9MlProb !== null ? (
                                                <span className={`font-mono text-sm ${t.v9MlProb > 0.6 ? 'text-green-600' : 'text-yellow-600'}`}>
                                                    {(t.v9MlProb * 100).toFixed(0)}%
                                                </span>
                                            ) : <span className="text-gray-300">—</span>}
                                        </td>
                                        <td className="px-6 py-4">
                                            {t.v9Confluence !== null ? (
                                                <div className="w-16 bg-gray-200 rounded-full h-2">
                                                    <div className="bg-blue-600 h-2 rounded-full" style={{ width: `${t.v9Confluence * 100}%` }} />
                                                </div>
                                            ) : <span className="text-gray-300">—</span>}
                                        </td>
                                        <td className="px-6 py-4">
                                            {t.v9Regime ? (
                                                <span className={`px-2 py-1 rounded text-xs font-bold ${
                                                    t.v9Regime === 'TREND' ? 'bg-green-50 text-green-600' :
                                                    t.v9Regime === 'RANGE' ? 'bg-yellow-50 text-yellow-600' :
                                                    'bg-red-50 text-red-600'
                                                }`}>{t.v9Regime}</span>
                                            ) : <span className="text-gray-300">—</span>}
                                        </td>
                                        <td className="px-6 py-4 text-gray-400">{format(new Date(t.closedAt), 'HH:mm')}</td>
                                    </tr>
                                ))
                            )}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    );
}
