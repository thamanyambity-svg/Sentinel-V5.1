'use client';

import { useState, useEffect, useRef } from 'react';

export default function TerminalPage() {
  const [logs, setLogs] = useState<any[]>([]);
  const scrollRef = useRef<HTMLDivElement>(null);

  const fetchLogs = async () => {
    try {
      const res = await fetch('/api/predator/data');
      const data = await res.json();
      if (data.logs) {
        setLogs(prev => {
          const newLogs = [...prev];
          data.logs.forEach((log: any) => {
            const exists = newLogs.some(l => l.time === log.time && l.msg === log.msg);
            if (!exists) {
              newLogs.push(log);
            }
          });
          return newLogs.slice(-100); // Keep last 100 logs
        });
      }
    } catch (e) {}
  };

  useEffect(() => {
    fetchLogs();
    const interval = setInterval(fetchLogs, 2000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logs]);

  return (
    <div className="min-h-screen bg-[#0d1117] flex flex-col">
      <div className="p-4 border-b border-[#30363d] bg-[#161b22]">
        <h1 className="text-xl font-black text-white">Predator High-Frequency Scan</h1>
        <p className="text-[10px] uppercase font-bold tracking-widest text-[#8b949e]">
          Institutional Execution Terminal V1.0
        </p>
      </div>

      <div 
        ref={scrollRef}
        className="flex-1 overflow-y-auto p-4 font-mono text-[11px] space-y-1"
      >
        {logs.map((log, index) => (
          <div key={index} className="flex gap-3">
            <span className="text-[#58a6ff] shrink-0">{log.time}</span>
            <span className={`font-bold shrink-0 ${log.type?.includes('Alerte') ? 'text-amber-500' : 'text-emerald-500'}`}>
              [{log.symbol || 'SYS'}]
            </span>
            <span className="text-[#c9d1d9]">{log.msg}</span>
          </div>
        ))}

        {logs.length === 0 && (
          <div className="h-full flex items-center justify-center opacity-20">
            <span className="animate-pulse">WAITING FOR DATA LINK...</span>
          </div>
        )}
      </div>

      <div className="p-2 border-t border-[#30363d] bg-[#0d1117] flex justify-between">
        <span className="text-[9px] text-[#8b949e] font-bold">MODE: PREDATOR_ACTIVE</span>
        <span className="text-[9px] text-emerald-500 font-bold animate-pulse">● CONNECTION STABLE</span>
      </div>
    </div>
  );
}
