'use client';
import { useState } from 'react';

const sections = [
  {
    id: '1',
    title: 'Résumé Analytique',
    icon: '📝',
    content: "L'or montre des signes de force relative malgré la hausse des rendements. Le pivot de la Fed est anticipé, créant un support solide à 2030$. La demande des banques centrales reste structurellement haussière.",
  },
  {
    id: '2',
    title: 'Analyse Technique XAU/USD',
    icon: '📈',
    content: "Formation d'un \"Bull Flag\" sur le H4. RSI à 58 — de la marge pour une extension vers 2050$. Support clé à 2025$. Résistance immédiate à 2040$ puis 2055$. Signal: ACHAT sur rupture de 2040$.",
  },
  {
    id: '3',
    title: 'Contexte Macro / VIX',
    icon: '🌍',
    content: "VIX à 17.48 indique une complaisance modérée. Une rupture des 18.50 du VIX pourrait accélérer la fuite vers la sécurité (Or). Dollar Index sous pression — favorise l'or.",
  },
  {
    id: '4',
    title: 'Sentiment du Marché',
    icon: '🎯',
    content: "Retail Sentiment: 65% Short (signal contrarian haussier). Institutionnel: Accumulation discrète détectée via Open Interest CME. Le déséquilibre offre/demande favorise une sortie par le haut.",
  },
  {
    id: '5',
    title: 'Plan de Trading Validé',
    icon: '🛡️',
    content: "BUY Zone: 2028–2033$ | TP1: 2045$ | TP2: 2058$ | SL: sous 2020$. Risk/Reward: 1:2.5. Taille position recommandée: 0.01–0.05 lot selon capital.",
  },
];

export default function IntelligencePage() {
  const [expandedId, setExpandedId] = useState<string | null>('1');

  return (
    <div className="min-h-screen bg-[#0d1117] p-4 max-w-4xl mx-auto w-full">
      <div className="mb-6">
        <h1 className="text-2xl font-black text-white tracking-tight">Dossier Predator</h1>
        <p className="text-[10px] uppercase font-bold tracking-[0.3em] text-cyan-400">
          Intelligence Artificielle V1.0 · Manus AI
        </p>
      </div>

      <div className="flex flex-col gap-3">
        {sections.map(section => (
          <div
            key={section.id}
            className="bg-[#161b22] border border-[#30363d] rounded-xl overflow-hidden hover:border-cyan-500/30 transition-colors"
          >
            <button
              onClick={() => setExpandedId(expandedId === section.id ? null : section.id)}
              className="w-full p-4 flex justify-between items-center text-left"
            >
              <div className="flex items-center gap-3">
                <span className="text-lg">{section.icon}</span>
                <span className={`font-bold text-sm ${expandedId === section.id ? 'text-cyan-400' : 'text-[#e2e8f0]'}`}>
                  {section.title}
                </span>
              </div>
              <span className={`text-[#8b949e] transition-transform duration-200 ${expandedId === section.id ? 'rotate-180' : ''}`}>▼</span>
            </button>

            {expandedId === section.id && (
              <div className="px-4 pb-4 border-t border-[#30363d]">
                <p className="text-sm text-[#8b949e] leading-relaxed mt-3">
                  {section.content}
                </p>
              </div>
            )}
          </div>
        ))}
      </div>

      <div className="mt-8 p-6 rounded-2xl bg-cyan-950/30 border border-cyan-500/20 flex flex-col items-center gap-2">
        <span className="text-xs font-black text-cyan-400 uppercase tracking-widest">
          ⚡ Analyse Générée par Manus AI
        </span>
        <span className="text-[10px] text-[#8b949e]">
          Dernière mise à jour: Automatique (toutes les 15 minutes)
        </span>
      </div>
    </div>
  );
}
