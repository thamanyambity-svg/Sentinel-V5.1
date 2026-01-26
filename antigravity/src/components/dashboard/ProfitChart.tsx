"use client"; // Obligatoire pour Recharts dans Next.js App Router

import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { format } from 'date-fns';

interface Trade {
    id: string;
    profit: number;
    closedAt: Date;
    symbol: string;
}

export default function ProfitChart({ trades }: { trades: Trade[] }) {
    // 1. Algorithme de calcul du cumulatif (Equity Curve)
    let runningBalance = 0;
    const data = trades.map((t) => {
        runningBalance += t.profit;
        return {
            date: format(new Date(t.closedAt), 'HH:mm'), // Heure formatée
            fullDate: format(new Date(t.closedAt), 'dd/MM HH:mm'),
            profit: t.profit,
            balance: runningBalance, // C'est cette valeur qu'on trace
            symbol: t.symbol
        };
    });

    // Couleur dynamique : Vert si positif, Rouge si négatif
    const isProfitable = runningBalance >= 0;
    const chartColor = isProfitable ? "#10B981" : "#EF4444"; // Emerald vs Red

    return (
        <div className="w-full h-[350px] bg-white p-4 rounded-xl shadow-sm border border-gray-100">
            <div className="flex justify-between items-center mb-4">
                <h3 className="text-lg font-bold text-gray-800">Performance Sentinel V5.2 🦅</h3>
                <span className={`px-3 py-1 rounded-full text-sm font-bold ${isProfitable ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
                    PNL: {runningBalance.toFixed(2)} $
                </span>
            </div>

            <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={data}>
                    <defs>
                        <linearGradient id="colorBalance" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor={chartColor} stopOpacity={0.3} />
                            <stop offset="95%" stopColor={chartColor} stopOpacity={0} />
                        </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#E5E7EB" />
                    <XAxis
                        dataKey="date"
                        stroke="#9CA3AF"
                        fontSize={12}
                        tickLine={false}
                        axisLine={false}
                    />
                    <YAxis
                        stroke="#9CA3AF"
                        fontSize={12}
                        tickLine={false}
                        axisLine={false}
                        tickFormatter={(value) => `${value}$`}
                    />
                    <Tooltip
                        contentStyle={{ backgroundColor: '#1F2937', border: 'none', borderRadius: '8px', color: '#fff' }}
                        itemStyle={{ color: '#fff' }}
                        labelFormatter={() => ''} // On cache le label par défaut
                        formatter={(value: number, name: string, props: any) => [
                            `${value.toFixed(2)}$`,
                            props.payload.symbol
                        ]}
                    />
                    <Area
                        type="monotone"
                        dataKey="balance"
                        stroke={chartColor}
                        strokeWidth={2}
                        fillOpacity={1}
                        fill="url(#colorBalance)"
                    />
                </AreaChart>
            </ResponsiveContainer>
        </div>
    );
}
