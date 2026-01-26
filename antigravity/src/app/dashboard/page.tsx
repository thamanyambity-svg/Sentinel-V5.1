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

    return (
        <div className="p-8 bg-gray-50 min-h-screen font-sans">
            <div className="max-w-4xl mx-auto">
                <div className="flex justify-between items-center mb-6">
                    <h1 className="text-2xl font-bold text-gray-900">Tableau de Bord Investisseur</h1>
                    <div className="text-sm text-gray-500 bg-white px-3 py-1 rounded-full shadow-sm border">
                        Live Status: <span className="text-green-500 font-bold">● Synchronized</span>
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
                                <th className="px-6 py-3">Heure</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-100">
                            {trades.length === 0 ? (
                                <tr>
                                    <td colSpan={4} className="px-6 py-8 text-center text-gray-400">
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
