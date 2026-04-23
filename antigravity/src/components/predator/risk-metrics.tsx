'use client';

interface RiskMetricsProps {
  marketRisk: number;
  vixFear: number;
}

export function RiskMetrics({ marketRisk, vixFear }: RiskMetricsProps) {
  const getRiskColor = (risk: number, limit = 70) => {
    if (risk > limit) return "text-red-400";
    if (risk > limit / 2) return "text-amber-400";
    return "text-emerald-400";
  };

  const CircularGauge = ({ value, max, label, color }: { value: number, max: number, label: string, color: string }) => {
    const radius = 35;
    const circumference = 2 * Math.PI * radius;
    const strokeDashoffset = circumference - (value / max) * circumference;

    return (
      <div className="flex flex-col items-center">
        <span className="text-[9px] uppercase font-black tracking-widest text-[#8b949e] mb-2">{label}</span>
        <div className="relative flex items-center justify-center w-24 h-24">
          {/* Background circle */}
          <svg className="w-full h-full transform -rotate-90" viewBox="0 0 96 96">
            <circle
              cx="48"
              cy="48"
              r={radius}
              stroke="#2a2c35"
              strokeWidth="6"
              fill="transparent"
            />
            {/* Progress circle */}
            <circle
              cx="48"
              cy="48"
              r={radius}
              stroke={color}
              strokeWidth="6"
              fill="transparent"
              strokeDasharray={circumference}
              strokeDashoffset={strokeDashoffset}
              strokeLinecap="round"
              className="transition-all duration-1000 ease-out"
            />
          </svg>
          <div className="absolute inset-0 flex items-center justify-center">
            <span className="text-xl font-black text-white">{value.toFixed(value % 1 === 0 ? 0 : 2)}</span>
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="bg-[#1b1c23] border border-[#2a2c35] rounded-xl p-5 shadow-lg w-full flex flex-col gap-4">
      <div className="flex justify-between items-center w-full">
         <span className="text-[11px] font-black uppercase tracking-widest text-[#e2e8f0]">
           Global Risk Indicators
         </span>
         <span className="text-[#6b7280]">⋮</span>
      </div>
      
      <div className="grid grid-cols-2 gap-4 w-full justify-items-center">
        <CircularGauge value={marketRisk} max={100} label="Market Risk" color={marketRisk > 70 ? "#ef4444" : "#10b981"} />
        <CircularGauge value={vixFear} max={50} label="Vix Fear Index" color="#d4a350" />
      </div>
    </div>
  );
}
