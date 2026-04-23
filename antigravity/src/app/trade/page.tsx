'use client';
import { useState } from 'react';

export default function TradePage() {
  const [orderType, setOrderType] = useState<'BUY' | 'SELL'>('BUY');
  const [lotSize, setLotSize] = useState('0.01');
  const [sl, setSl] = useState('');
  const [tp, setTp] = useState('');

  const isBuy = orderType === 'BUY';

  return (
    <div className="min-h-screen bg-[#0d1117] p-4 max-w-md mx-auto w-full flex flex-col gap-6">
      {/* Symbol Header */}
      <div className="flex flex-col items-center pt-6 pb-2">
        <div className="text-4xl font-black text-white tracking-tighter">XAUUSD</div>
        <div className="text-xs font-mono font-bold text-cyan-400 tracking-widest">GOLD SPOT / USD</div>
      </div>

      {/* Buy/Sell Selector */}
      <div className="grid grid-cols-2 gap-3">
        <button
          onClick={() => setOrderType('BUY')}
          className={`py-4 rounded-xl font-black text-sm border-2 transition-all ${
            isBuy
              ? 'bg-emerald-500/10 border-emerald-500 text-emerald-400'
              : 'bg-[#161b22] border-[#30363d] text-[#8b949e] hover:border-[#8b949e]'
          }`}
        >
          ▲ ACHETER
        </button>
        <button
          onClick={() => setOrderType('SELL')}
          className={`py-4 rounded-xl font-black text-sm border-2 transition-all ${
            !isBuy
              ? 'bg-red-500/10 border-red-500 text-red-400'
              : 'bg-[#161b22] border-[#30363d] text-[#8b949e] hover:border-[#8b949e]'
          }`}
        >
          ▼ VENDRE
        </button>
      </div>

      {/* Order Parameters */}
      <div className="bg-[#161b22] border border-[#30363d] rounded-2xl p-6 flex flex-col gap-5">
        <div>
          <label className="block text-[9px] font-black uppercase tracking-widest text-[#8b949e] mb-2">Volume (Lots)</label>
          <input
            type="number"
            value={lotSize}
            onChange={e => setLotSize(e.target.value)}
            step="0.01"
            min="0.01"
            className="w-full text-2xl font-black font-mono bg-transparent border-b border-[#30363d] pb-2 text-white focus:border-cyan-500 outline-none transition-colors"
          />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-[9px] font-black uppercase tracking-widest text-[#8b949e] mb-2">Stop Loss</label>
            <input
              type="number"
              value={sl}
              onChange={e => setSl(e.target.value)}
              placeholder="0.00"
              className="w-full text-sm font-mono bg-transparent border-b border-[#30363d] pb-2 text-red-400 focus:border-red-500 outline-none transition-colors"
            />
          </div>
          <div>
            <label className="block text-[9px] font-black uppercase tracking-widest text-[#8b949e] mb-2">Take Profit</label>
            <input
              type="number"
              value={tp}
              onChange={e => setTp(e.target.value)}
              placeholder="0.00"
              className="w-full text-sm font-mono bg-transparent border-b border-[#30363d] pb-2 text-emerald-400 focus:border-emerald-500 outline-none transition-colors"
            />
          </div>
        </div>
      </div>

      {/* Execute Button */}
      <button
        className={`w-full py-5 rounded-2xl font-black text-lg transition-all hover:scale-[1.02] active:scale-[0.98] shadow-lg ${
          isBuy
            ? 'bg-emerald-500 hover:bg-emerald-400 text-[#0d1117]'
            : 'bg-red-500 hover:bg-red-400 text-white'
        }`}
      >
        {isBuy ? '▲' : '▼'} PLACER L'ORDRE {orderType}
      </button>

      <p className="text-center text-[9px] text-[#8b949e] px-4 leading-relaxed">
        En plaçant cet ordre, vous acceptez les conditions de risque du marché XAU/USD.
        Sentinel Predator surveille en continu les positions.
      </p>
    </div>
  );
}
