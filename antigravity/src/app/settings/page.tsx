'use client';
import { useState } from 'react';

export default function SettingsPage() {
  const [notifications, setNotifications] = useState(true);
  const [autoHedge, setAutoHedge] = useState(false);

  return (
    <div className="min-h-screen bg-[#0d1117] p-4 max-w-4xl mx-auto w-full">
      <div className="mb-6">
        <h1 className="text-2xl font-black text-white">Paramètres</h1>
        <p className="text-[10px] uppercase font-bold tracking-[0.3em] text-[#8b949e]">
          Configuration Sentinel Predator V1.0
        </p>
      </div>

      {/* Account Info */}
      <div className="mb-6">
        <h2 className="text-[10px] font-black uppercase tracking-[0.3em] text-cyan-500/80 ml-1 mb-3">
          Compte de Trading
        </h2>
        <div className="bg-[#161b22] border border-[#30363d] rounded-2xl overflow-hidden">
          {[
            { label: 'Propriétaire', value: 'Alpha Aboubacar Ambity' },
            { label: 'ID Compte MT5', value: '101573422' },
            { label: 'Serveur Courtier', value: 'DerivBVI-Server-02' },
            { label: 'Actif Prioritaire', value: 'XAU/USD (Or)' },
          ].map((row, i, arr) => (
            <div key={row.label} className={`px-4 py-3 flex justify-between items-center ${i < arr.length - 1 ? 'border-b border-[#30363d]' : ''}`}>
              <span className="text-xs text-[#8b949e] font-medium">{row.label}</span>
              <span className="text-xs font-bold text-white font-mono">{row.value}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Bot Preferences */}
      <div className="mb-6">
        <h2 className="text-[10px] font-black uppercase tracking-[0.3em] text-cyan-500/80 ml-1 mb-3">
          Préférences du Bot
        </h2>
        <div className="bg-[#161b22] border border-[#30363d] rounded-2xl overflow-hidden">
          {[
            { label: 'Alertes Push Mobile', state: notifications, onToggle: setNotifications },
            { label: 'Auto-Hedge d\'Urgence', state: autoHedge, onToggle: setAutoHedge },
          ].map((item, i, arr) => (
            <div key={item.label} className={`px-4 py-4 flex justify-between items-center ${i < arr.length - 1 ? 'border-b border-[#30363d]' : ''}`}>
              <span className="text-sm text-[#e2e8f0]">{item.label}</span>
              <button
                onClick={() => item.onToggle(!item.state)}
                className={`relative inline-flex h-6 w-11 rounded-full transition-colors ${item.state ? 'bg-cyan-500' : 'bg-[#30363d]'}`}
              >
                <span className={`inline-block h-4 w-4 rounded-full bg-white shadow transition-transform mt-1 ${item.state ? 'translate-x-6' : 'translate-x-1'}`} />
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* Session Hours */}
      <div className="mb-6">
        <h2 className="text-[10px] font-black uppercase tracking-[0.3em] text-cyan-500/80 ml-1 mb-3">
          Cycle d'Autorisation
        </h2>
        <div className="bg-[#161b22] border border-[#30363d] rounded-2xl p-4 flex justify-between items-center">
          <div>
            <p className="text-sm font-bold text-white">Session Active</p>
            <p className="text-[10px] text-[#8b949e]">Bot autorisé à trader de 07h00 à 23h00 (Heure Locale)</p>
          </div>
          <div className="text-right">
            <p className="text-sm font-mono font-black text-emerald-400">07:00</p>
            <p className="text-[9px] text-[#8b949e]">→ 23:00</p>
          </div>
        </div>
      </div>

      {/* App Version */}
      <div className="text-center mt-10 flex flex-col items-center gap-1">
        <p className="text-[10px] font-mono text-[#8b949e]">SENTINEL PREDATOR MOBILE V1.0.0</p>
        <p className="text-[9px] text-[#30363d]">BUILD 2026.04.20 · Platform Web & Mobile</p>
        <button className="mt-6 text-red-500 font-bold text-sm hover:text-red-400 transition-colors">
          Déconnexion
        </button>
      </div>
    </div>
  );
}
