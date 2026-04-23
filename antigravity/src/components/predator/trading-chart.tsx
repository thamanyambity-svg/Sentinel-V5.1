import React from 'react';
import { ComposedChart, Line, Bar, XAxis, YAxis, CartesianGrid, ResponsiveContainer, Cell } from 'recharts';

export function TradingChart({ currentPrice, rawData }: { currentPrice: number, rawData?: any[] }) {
  // Use real data from the API if available, otherwise fallback
  const data = React.useMemo(() => {
    if (rawData && rawData.length > 0) {
      // Calculate simple moving averages (optional if not provided)
      let ma1Sum = 0;
      let ma2Sum = 0;
      return rawData.map((d, index, arr) => {
         // Simple 5-period MA
         const period1 = 5;
         const period2 = 10;
         const p1Slice = arr.slice(Math.max(0, index - period1 + 1), index + 1);
         const p2Slice = arr.slice(Math.max(0, index - period2 + 1), index + 1);
         
         const ma1 = p1Slice.reduce((sum, item) => sum + item.close, 0) / p1Slice.length;
         const ma2 = p2Slice.reduce((sum, item) => sum + item.close, 0) / p2Slice.length;
         
         return {
            ...d,
            ma1,
            ma2,
         };
      });
    }

    // Fallback if no real data yet
    const arr = [];
    let p = currentPrice || 2445.93;
    const now = new Date();
    for (let i = 40; i >= 0; i--) {
      // random walk
      const change = (Math.random() - 0.5) * 5;
      const open = p;
      const close = p + change;
      const high = Math.max(open, close) + Math.random() * 2;
      const low = Math.min(open, close) - Math.random() * 2;
      
      const isUp = close >= open;

      const timeStr = new Date(now.getTime() - i * 5 * 60000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
      
      // Moving averages mock
      const ma1 = p - 2;
      const ma2 = p - 5;

      arr.push({ time: timeStr, open, close, high, low, isUp, ma1, ma2, volume: Math.random() * 100 });
      p = close;
    }
    return arr;
  }, [currentPrice]);

  // A custom shape for the bar to look like a candlestick (body + wicks)
  const CandlestickShape = (props: any) => {
    const { x, y, width, height, open, close, high, low, isUp } = props;
    const bodyTop = Math.min(open, close);
    const bodyBottom = Math.max(open, close);
    
    // We get actual screen Y coordinates via payload if we scaled properly, 
    // but building an exact pixel-perfect OHLC wick inside a generic Bar shape can be complex without Y scale.
    // For visual similarity to the mockup, we will just use a generic Bar with gradient colors, 
    // and rely on the height calculated by Recharts.
    // The mockup uses thick bars that transition colors.

    const fillY = isUp ? "url(#colorUp)" : "url(#colorDown)";
    
    return (
      <rect 
        x={x} 
        y={y} 
        width={width} 
        height={Math.max(2, height)} 
        fill={fillY} 
        rx={1} 
      />
    );
  };

  return (
    <div className="w-full h-full bg-[#1b1c23] border border-[#2a2c35] rounded-xl relative p-4 flex flex-col shadow-lg overflow-hidden">
      
      <div className="flex justify-between items-center mb-2 z-10">
         <span className="text-xl font-bold"></span>
         <div className="flex gap-2">
            <span className="text-[#6b7280]">⤢</span>
            <span className="text-[#6b7280]">⋮</span>
         </div>
      </div>

      <div className="flex-1 w-full relative min-h-[400px]">
        {/* Main Chart */}
        <div className="absolute inset-0 pb-12">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={data} margin={{ top: 20, right: 30, left: 20, bottom: 20 }}>
              <defs>
                <linearGradient id="colorUp" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#d4a350" stopOpacity={1}/>
                  <stop offset="100%" stopColor="#9a6e30" stopOpacity={1}/>
                </linearGradient>
                <linearGradient id="colorDown" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#8b5cf6" stopOpacity={1}/>
                  <stop offset="100%" stopColor="#6d28d9" stopOpacity={1}/>
                </linearGradient>
              </defs>

              <CartesianGrid strokeDasharray="3 3" stroke="#2a2c35" vertical={false} />
              <XAxis dataKey="time" stroke="#6b7280" tick={{fontSize: 9}} tickLine={false} axisLine={false} minTickGap={30} dy={10} />
              <YAxis 
                 domain={['dataMin - 1', 'dataMax + 1']} 
                 stroke="#6b7280" 
                 tick={{fontSize: 9}} 
                 tickLine={false} 
                 axisLine={false} 
                 orientation="right" 
                 tickFormatter={(val) => `$${val.toFixed(2)}`} 
                 dx={10}
              />
              
              {/* Using a Bar to simulate candle bodies */}
              <Bar dataKey="close" shape={<CandlestickShape />} isAnimationActive={false} />
              
              <Line type="monotone" dataKey="ma1" stroke="#d4a350" strokeWidth={1} dot={false} isAnimationActive={false} />
              <Line type="monotone" dataKey="ma2" stroke="#8b5cf6" strokeWidth={1} dot={false} isAnimationActive={false} />
            </ComposedChart>
          </ResponsiveContainer>
        </div>

        {/* Volume Mock (positioned slightly above the axis) */}
        <div className="absolute bottom-[60px] left-0 right-0 h-16 px-6 opacity-30 pointer-events-none">
           <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={data} margin={{ top: 0, right: 30, left: 20, bottom: 0 }}>
                <Bar dataKey="volume" isAnimationActive={false}>
                  {data.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.isUp ? '#d4a350' : '#8b5cf6'} />
                  ))}
                </Bar>
              </ComposedChart>
           </ResponsiveContainer>
        </div>
      </div>

      {/* Buttons - standard flex container */}
      <div className="flex justify-center items-center gap-6 mt-4 mb-2 z-20 shrink-0">
        <button className="bg-[#10b981] hover:bg-[#059669] text-white font-black px-10 py-3 rounded-xl shadow-[0_0_15px_rgba(16,185,129,0.3)] transition-all uppercase tracking-widest text-sm">
          BUY
        </button>
        <button className="bg-red-500 hover:bg-red-600 text-white font-black px-10 py-3 rounded-xl shadow-[0_0_15px_rgba(239,68,68,0.3)] transition-all uppercase tracking-widest text-sm">
          SELL
        </button>
      </div>

    </div>
  );
}
