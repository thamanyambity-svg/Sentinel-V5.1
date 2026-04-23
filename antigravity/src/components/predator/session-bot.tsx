'use client';

import { useState, useEffect } from 'react';

interface SessionBotProps {
  isActive: boolean;
  countdownSeconds: number;
}

export function SessionBot({ isActive, countdownSeconds }: SessionBotProps) {
  const [seconds, setSeconds] = useState(countdownSeconds);

  useEffect(() => {
    const timer = setInterval(() => {
      setSeconds((prev) => (prev > 0 ? prev - 1 : 0));
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  const formatTime = (s: number) => {
    const hours = Math.floor(s / 3600);
    const minutes = Math.floor((s % 3600) / 60);
    const secs = s % 60;
    return [hours, minutes, secs].map(v => String(v).padStart(2, '0')).join(':');
  };

  return (
    <div className="bg-[#1b1c23] rounded-xl p-5 border border-[#2a2c35] flex flex-col gap-4 shadow-lg w-full">
      <div className="flex justify-between items-center w-full">
         <span className="text-[11px] font-black uppercase tracking-widest text-[#e2e8f0]">
           Execution Guard
         </span>
         <span className="text-[#6b7280]">⋮</span>
      </div>

      <div className="bg-[#21232c] rounded-lg p-3 flex flex-col gap-3 border border-[#2a2c35]">
         <span className="text-[10px] font-bold text-[#8b949e] tracking-widest uppercase">
            CYCLE D'AUTORISATION (07H-23H)
         </span>

         <div className={`px-3 py-2 rounded flex items-center border ${isActive ? 'bg-[#10b981]/10 border-[#10b981]/20' : 'bg-red-500/10 border-red-500/20'}`}>
            <span className={`text-[11px] font-black tracking-widest uppercase ${isActive ? 'text-[#10b981]' : 'text-red-500'}`}>
               SÉCURITÉ: {isActive ? 'BOT ACTIF' : 'BOT INACTIF'}
            </span>
         </div>
      </div>

      <div className="flex justify-between items-center px-1">
         <span className="text-[11px] text-[#8b949e] font-bold uppercase tracking-widest">
            LIVE COUNTDOWN :
         </span>
         <span className="text-[17px] font-mono font-black text-white tracking-widest drop-shadow-[0_0_8px_rgba(255,255,255,0.3)]">
            {formatTime(seconds)}
         </span>
      </div>
    </div>
  );
}
