'use client';

interface HeaderTradingProps {
  balance: number;
  equity: number;
  marginLevel: number;
  marketOpen: boolean;
}

export function HeaderTrading({
  balance,
  equity,
  marginLevel,
  marketOpen,
}: HeaderTradingProps) {
  const formatCurrency = (value: number) =>
    new Intl.NumberFormat("fr-FR", {
      style: "currency",
      currency: "USD",
      minimumFractionDigits: 2,
    }).format(value);

  const getMarginColor = () => {
    if (marginLevel > 80) return "text-red-500";
    if (marginLevel > 50) return "text-amber-500";
    return "text-emerald-500";
  };

  return (
    <div className="w-full flex justify-between items-center mb-6 pl-2">
      <div className="flex flex-col">
        <span className="text-2xl font-black text-white tracking-widest uppercase">Sentinel</span>
        <span className="text-[10px] text-[#6b7280] font-black uppercase tracking-[0.2em] -mt-1">Institutional Terminal</span>
      </div>

      <div className="flex gap-4">
        {/* Account Info Card */}
        <div className="bg-[#1b1c23] border border-[#2a2c35] rounded-xl px-5 py-3 flex items-center gap-6 shadow-xl relative top-0.5" style={{boxShadow: '0 8px 30px rgba(0,0,0,0.5)'}}>
          <div className="flex flex-col">
            <span className="text-[8px] uppercase tracking-wider text-[#6b7280] mb-0.5">Solde Compte:</span>
            <span className="text-xs font-mono font-medium text-white">{formatCurrency(balance)}</span>
          </div>
          <div className="flex flex-col">
            <span className="text-[8px] uppercase tracking-wider text-[#6b7280] mb-0.5">Capital (Equity):</span>
            <span className="text-xs font-mono font-medium text-white">{formatCurrency(equity)}</span>
          </div>
          <div className="flex flex-col">
            <span className="text-[8px] uppercase tracking-wider text-[#6b7280] mb-0.5">Marge:</span>
            <span className={`text-xs font-mono font-medium ${getMarginColor()}`}>{marginLevel.toFixed(0)}%</span>
          </div>
          {/* Small dropdown icon mock */}
          <div className="ml-2 text-[#6b7280]">
             <svg width="10" height="6" viewBox="0 0 10 6" fill="none"><path d="M1 1L5 5L9 1" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round"/></svg>
          </div>
        </div>

        {/* Live Status Card */}
        {/* Note: The Gold price is displayed in page.tsx right now, we can pass it here to match the image exact layout. */}
        {/* Let's render the container for it, and the parent can pass goldPrice if we want. For now, let's keep it structurally similar to the design. */}
        <div className="bg-[#1b1c23] border border-[#2a2c35] rounded-xl pl-5 pr-3 py-2 flex items-center gap-6 shadow-xl relative top-0.5" style={{boxShadow: '0 8px 30px rgba(0,0,0,0.5)'}}>
          <div className="flex items-center gap-2 text-[10px] font-black uppercase tracking-wider text-[#8b949e]">
             XAU/USD - PRIX OR EN TEMPS RÉEL
          </div>
          
          <div className={`px-2 py-1 rounded-md flex items-center gap-1.5 ${marketOpen ? 'bg-[#10b981]/10 border border-[#10b981]/20' : 'bg-red-500/10 border border-red-500/20'}`}>
            <div className={`w-1.5 h-1.5 rounded-full ${marketOpen ? 'bg-[#10b981]' : 'bg-red-500'} animate-pulse`} />
            <span className={`text-[9px] font-bold tracking-widest ${marketOpen ? 'text-[#10b981]' : 'text-red-500'}`}>
              {marketOpen ? 'LIVE / OPEN' : 'CLOSED'}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
