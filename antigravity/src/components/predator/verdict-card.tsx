'use client';

type VerdictType = "BULLISH" | "NEUTRAL" | "BEARISH";

interface VerdictCardProps {
  verdict: VerdictType | string;
  confidence: number;
}

export function VerdictCard({ verdict, confidence }: VerdictCardProps) {
  const getVerdictTheme = () => {
    switch (verdict) {
      case "BULLISH":
        return { color: "text-emerald-400", bg: "bg-emerald-500/10", border: "border-emerald-500/20", bar: "bg-emerald-500" };
      case "BEARISH":
        return { color: "text-red-400", bg: "bg-red-500/10", border: "border-red-500/20", bar: "bg-red-500" };
      default:
        return { color: "text-amber-400", bg: "bg-amber-500/10", border: "border-amber-500/20", bar: "bg-amber-500" };
    }
  };

  const theme = getVerdictTheme();

  return (
    <div className="bg-[#1b1c23] rounded-xl p-5 border border-[#2a2c35] flex flex-col gap-4 shadow-lg w-full">
      <div className="flex justify-between items-center w-full">
         <span className="text-[11px] font-black uppercase tracking-widest text-[#e2e8f0]">
           Core Intelligence - Manus AI
         </span>
         <span className="text-[#6b7280]">⋮</span>
      </div>

      <div className={`rounded-lg p-3 border flex justify-between items-center ${theme.bg} ${theme.border}`}>
        <div className="flex items-center gap-2">
           <span className="text-[#d4a350]">⚙</span>
           <span className="text-[10px] font-black uppercase tracking-[0.1em] text-[#e2e8f0]">AI Bias Verdict</span>
        </div>
        <span className={`text-[11px] font-black tracking-wider uppercase ${theme.color}`}>
          {verdict}
        </span>
      </div>

      <div className="w-full flex-col flex relative h-7 bg-[#111216] rounded-md overflow-hidden border border-[#2a2c35]">
        <div 
          className={`absolute top-0 bottom-0 left-0 bg-[#d4a350]`} // Changed to gold for the design
          style={{ width: `${confidence}%` }}
        />
        <div className="absolute inset-0 flex items-center px-3 z-10">
           <span className="text-[10px] font-bold text-white tracking-widest">
             CONFIANCE: {confidence.toFixed(1)}%
           </span>
        </div>
      </div>

      <p className="text-[10px] leading-relaxed text-[#8b949e] mt-1 pr-2">
         The current XAU/USD market analysis is current to analyze
         and {verdict.toLowerCase()} specific in the volume for bearing, the
         indicator data and related changes of the current
         market in certain aspects and global markets.
      </p>
    </div>
  );
}
