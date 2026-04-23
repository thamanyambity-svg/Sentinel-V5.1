'use client';

import { useState, useEffect } from 'react';
import { HeaderTrading } from '../components/predator/header-trading';
import { VerdictCard } from '../components/predator/verdict-card';
import { RiskMetrics } from '../components/predator/risk-metrics';
import { SessionBot } from '../components/predator/session-bot';
import { TradingChart } from '../components/predator/trading-chart';

export default function PredatorHome() {
  const [data, setData] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(true);

  const fetchData = async () => {
    try {
      const res = await fetch('/api/predator/data');
      const json = await res.json();
      if (!json.error) {
        setData(json);
      }
    } catch (e) {
      console.error("Failed to fetch MT5 data", e);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 5000); // 5s refresh
    return () => clearInterval(interval);
  }, []);

  if (isLoading || !data) {
    return (
      <div className="min-h-screen bg-[#0d1117] flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <div className="w-12 h-12 border-4 border-cyan-500/20 border-t-cyan-500 rounded-full animate-spin" />
          <span className="text-cyan-400 font-mono text-xs animate-pulse">
            INITIALISATION SENTINEL PREDATOR...
          </span>
        </div>
      </div>
    );
  }

  return (
    <main className="min-h-screen bg-[#111216] text-[#e2e8f0] flex flex-col p-4 md:p-6 md:pr-8">
      
      {/* Top Header Section */}
      <HeaderTrading 
        balance={data.account.balance}
        equity={data.account.equity}
        marginLevel={data.account.marginLevel}
        marketOpen={data.account.marketOpen}
      />

      {/* Main Grid Layout to match mockup (Left panel ~1/3, Right panel ~2/3) */}
      <div className="flex flex-col xl:flex-row gap-6 w-full max-w-[1800px] mx-auto h-[calc(100vh-120px)]">
        
        {/* Left Column (Widgets) */}
        <div className="w-full xl:w-[400px] flex flex-col gap-6 h-full flex-shrink-0">
          <VerdictCard 
            verdict={data.verdict.bias} 
            confidence={data.verdict.confidence} 
          />
          
          <RiskMetrics 
            marketRisk={data.risk.marketRisk} 
            vixFear={data.risk.vix} 
          />
          
          <SessionBot 
            isActive={data.account.marketOpen} 
            countdownSeconds={3593} 
          />
        </div>

        {/* Right Column (Chart and Actions) */}
        <div className="w-full flex-1 flex flex-col h-full">
           <TradingChart 
             currentPrice={data.account.goldPrice || 2445.93} 
             rawData={data.chartData}
           />
        </div>

      </div>
    </main>
  );
}
