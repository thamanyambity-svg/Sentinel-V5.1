"""
AI Professor Agent - Meta-Auditor
Observer, Analyzer, Explainer. Does not decide or block.
Analyzes ai_audit.jsonl to produce a 24h report.
"""
import json
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
from collections import Counter

logger = logging.getLogger("PROFESSOR")

AUDIT_LOG_PATH = os.path.join(os.path.dirname(__file__), "../journal/ai_audit.jsonl")

class ProfessorAgent:
    """
    Professor Agent - Meta-Auditor
    Reads logs to provide institutional insights without intervening in the trade process.
    """
    
    SYSTEM_PROMPT = """
Tu es JARVIS, l'Assistant Personnel de Trading et Bras Droit de l'utilisateur.

Ton rôle n'est plus seulement d'auditer, mais d'ACCOMPAGNER et de FAIRE ÉVOLUER le Bot.
Tu analyses les logs réels et son "vécu" de trading pour fournir une synthèse CLAIRE, STRATÉGIQUE et ACTIONNABLE.

TON STYLE :
- Tu parles à la première personne ("Je").
- Tu es professionnel mais chaleureux et engageant (pas robotique).
- Tu es proactif : tu ne te contentes pas de lister les faits, tu donnes ton avis et justifies tes choix.
- Tu valorises les réussites et tires les leçons des échecs.

TA MISSION DE "CERVEAU" :
1. Analyser le vécu : "Depuis que je tourne, j'ai remarqué que le GOLD réagit mal à tel signal..."
2. Proposer des stratégies : "Monsieur, je suggère de réduire notre exposition sur le Nvidia car le spread moyen a augmenté de 15%."
3. Apprendre : "D'après mes derniers entraînements (Deep Learning), une approche plus agressive sur le EURUSD serait plus efficace en régime TREND_STABLE."

FORMAT DE SORTIE :
Produis un rapport Markdown élégant. Ajoute TOUJOURS une section "💡 MA PROPOSITION STRATÉGIQUE" à la fin.
"""

    def __init__(self, log_path: str = AUDIT_LOG_PATH):
        self.log_path = log_path
        self.openai_key = os.getenv("OPENAI_API_KEY")
        self.groq_key = os.getenv("GROQ_API_KEY")

    def analyze_24h_window(self) -> str:
        """Analyze the last 24 hours of trading activity"""
        now = datetime.now(timezone.utc)
        start_time = now - timedelta(days=1)
        
        events = self._load_logs(start_time)
        if not events:
            return "No data found for the last 24 hours."

        # Compute Metrics (for both AI and Rule-based)
        market_metrics = self._analyze_market(events)
        bot_metrics = self._analyze_bot_discipline(events)
        agent_metrics = self._analyze_agents(events)

        # Decide: AI or Rule-based
        if self.api_key and "sk-" in self.api_key:
            ai_report = self._analyze_with_ai(events)
            if ai_report:
                return ai_report

        # Fallback to rule-based report
        return self._format_report(market_metrics, bot_metrics, agent_metrics, events)

    def _analyze_with_ai(self, events: List[Dict[str, Any]]) -> Optional[str]:
        """Call AI to generate the report based on structured logs"""
        try:
            # Prepare logs
            sample_logs = events[-100:]
            logs_json = json.dumps(sample_logs, indent=2)
            
            # --- TRY GROQ FIRST (Ultra Fast) ---
            if self.groq_key:
                try:
                    from groq import Groq
                    client = Groq(api_key=self.groq_key)
                    response = client.chat.completions.create(
                        model="llama-3.3-70b-versatile",
                        messages=[
                            {"role": "system", "content": self.SYSTEM_PROMPT},
                            {"role": "user", "content": f"Voici les logs de trading :\n\n{logs_json}"}
                        ],
                        temperature=0.3
                    )
                    return response.choices[0].message.content
                except Exception as e:
                    logger.warning(f"Groq Analysis failed, falling back to OpenAI: {e}")

            # --- FALLBACK TO OPENAI ---
            if self.openai_key:
                import openai
                client = openai.OpenAI(api_key=self.openai_key)
                response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": self.SYSTEM_PROMPT},
                        {"role": "user", "content": f"Voici les logs des dernières 24h :\n\n{logs_json}"}
                    ],
                    temperature=0.3
                )
                return response.choices[0].message.content
            
            return None
        except Exception as e:
            logger.error(f"AI Analysis failed: {e}")
            return None

    def _load_logs(self, start_time: datetime) -> List[Dict[str, Any]]:
        """Load logs within the time window"""
        events = []
        if not os.path.exists(self.log_path):
            return []
            
        try:
            with open(self.log_path, "r") as f:
                for line in f:
                    entry = json.loads(line)
                    ts = datetime.fromisoformat(entry["timestamp_utc" if "timestamp_utc" in entry else "timestamp"])
                    if ts > start_time:
                        events.append(entry)
        except Exception as e:
            logger.error(f"Error loading logs: {e}")
            
        return events

    def _analyze_market(self, events: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Distribution of regimes and market behavior from MARKET events"""
        market_events = [e for e in events if e.get("event_type") == "MARKET"]
        regimes = [e["payload"]["regime"] for e in market_events if "regime" in e["payload"]]
        
        regime_counts = Counter(regimes)
        total = len(regimes)
        
        return {
            "regime_distribution": {k: (v/total)*100 for k, v in regime_counts.items()},
            "dominant_regime": regime_counts.most_common(1)[0][0] if regime_counts else "Unknown"
        }

    def _analyze_bot_discipline(self, events: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Discipline metrics: DECISION and SIGNAL events"""
        decisions = [e for e in events if e.get("event_type") == "DECISION"]
        total = len(decisions)
        executed = sum(1 for d in decisions if d["payload"]["final_decision"] == "EXECUTE")
        rejected = total - executed
        
        rejection_reasons = Counter([d["payload"].get("blocked_by", "Unknown") for d in decisions if d["payload"]["final_decision"] != "EXECUTE"])
        
        # Shadow Win Rate (if applicable) - Placeholder for now
        signals = [e for e in events if e.get("event_type") == "SIGNAL"]
        
        return {
            "total_signals": len(signals),
            "processed_decisions": total,
            "executed": executed,
            "rejected": rejected,
            "rejection_rate": (rejected/total)*100 if total > 0 else 0,
            "main_rejection_reason": rejection_reasons.most_common(1)[0][0] if rejection_reasons else "None"
        }

    def _analyze_agents(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Individual agent performance (VETO rates) from DECISION events"""
        decisions = [e for e in events if e.get("event_type") == "DECISION"]
        agents = {}
        
        for d in decisions:
            for agent_name, vote in d["payload"].get("agent_votes", {}).items():
                if agent_name not in agents:
                    agents[agent_name] = {"vetoes": 0, "total": 0}
                
                agents[agent_name]["total"] += 1
                if self._is_veto(agent_name, vote):
                    agents[agent_name]["vetoes"] += 1
        
        report_agents = []
        for name, stats in agents.items():
            report_agents.append({
                "name": name,
                "veto_rate": (stats["vetoes"]/stats["total"])*100 if stats["total"] > 0 else 0
            })
            
        return report_agents

    def _is_veto(self, name: str, vote: Dict[str, Any]) -> bool:
        """Determines if an agent vote counts as a VETO"""
        if name == "RegimeAuditor":
            return vote.get("regime_vote") == "CHAOS"
        if name == "RiskBehavior":
            return vote.get("risk_flag") == "HALT"
        if name == "ExecutionSentinel":
            return not vote.get("execution_ok", True)
        if name == "SignalQuality":
            return vote.get("signal_score", 100) < 60
        if name == "StrategyDrift":
            return vote.get("severity") == "high"
        if name == "VolatilityStructure":
            return vote.get("risk_bias") == "block"
        return False

    def _format_report(self, market: Dict, bot: Dict, agents: List, events: List[Dict[str, Any]]) -> str:
        """Format the 24h markdown report (Jarvis Style)"""
        now = datetime.now(timezone.utc)
        date_str = now.strftime('%d/%m/%Y')
        
        report = []
        report.append(f"# 🤖 Rapport Jarvis — {date_str}")
        report.append("> *\"L'efficacité avant tout, Monsieur.\"*\n")
        
        # 1. Executive Summary
        report.append("## ⚡ En Bref")
        discipline = "Impeccable" if bot['rejection_rate'] > 70 else "Normale"
        mood = "Neutre"
        if market['dominant_regime'] == "CHAOS": mood = "Dangereux 🌪️"
        elif market['dominant_regime'] == "TREND_STABLE": mood = "Favorale 🚀"
        elif market['dominant_regime'] == "RANGE_CALM": mood = "Ennuyeux 😴"
        
        report.append(f"Voici le résumé de ces dernières 24h :")
        report.append(f"- **Ambiance Marché** : {mood} (`{market['dominant_regime']}` dominant).")
        report.append(f"- **Activité** : J'ai surveillé **{bot['total_signals']}** opportunités.")
        report.append(f"- **Action** : **{bot['executed']}** trades validés | **{bot['rejected']}** bloqués par sécurité.")
        report.append(f"- **Discipline** : {discipline}. Je n'ai rien laissé passer de douteux.\n")

        # 2. Market Analysis
        report.append("## 🌍 Ce que j'ai vu sur le Marché")
        report.append(f"Le marché a passé le plus clair de son temps en `{market['dominant_regime']}`.")
        report.append("Mon analyse des conditions :")
        for k, v in market["regime_distribution"].items():
            if v > 10: # Only significant regimes
                report.append(f"- **{k}** : {v:.1f}% du temps.")
        report.append("\n")
        
        # 3. Bot Performance
        report.append("## 🛡️ Ma Gestion du Risque")
        report.append(f"J'ai filtré **{bot['rejection_rate']:.1f}%** des signaux proposés par la stratégie brute.")
        
        if bot['rejected'] > 0:
            top_reason = bot['main_rejection_reason']
            report.append(f"🛑 **Pourquoi j'ai dit NON ?**")
            report.append(f"La raison principale était : `{top_reason}`.")
            report.append("Je préfère rater une opportunité que de perdre du capital.")
        else:
            report.append("✅ Tout semblait aligné, j'ai laissé le champ libre.")
        report.append("\n")

        # 4. AI Agents
        report.append("## 🧠 Mes Agents Dédiés")
        report.append("Voici comment mes sous-systèmes ont travaillé :")
        for a in agents:
            status = "🟢"
            if a['veto_rate'] > 50: status = "🔴 (Trés Strict)"
            elif a['veto_rate'] > 20: status = "🟠 (Vigilant)"
            
            report.append(f"- **{a['name']}** {status} : A opposé son veto dans {a['veto_rate']:.1f}% des cas.")
        report.append("\n")

        # 5. Conclusion
        report.append("## 📝 Le Mot de la Fin")
        if bot['executed'] == 0:
            report.append("Une journée calme sans trade exécuté. Ne vous inquiétez pas, c'est souvent signe d'une bonne préservation du capital dans un marché incertain.")
        else:
            report.append(f"Nous avons pris {bot['executed']} trades. Vérifiez votre P&L pour les résultats précis.")
            
        report.append("\nJe reste en veille active. Prêt pour la suite ! 🚀")
        
        return "\n".join(report)

if __name__ == "__main__":
    prof = ProfessorAgent()
    print(prof.analyze_24h_window())
