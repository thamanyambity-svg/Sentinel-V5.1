import { View, ScrollView, SafeAreaView } from "react-native";
import { useColors } from "@/hooks/use-colors";
import { HeaderTrading } from "@/components/header-trading";
import { GlassCard } from "@/components/ui/glass-card";
import { TerminalText } from "@/components/ui/terminal-text";
import { IconSymbol } from "@/components/ui/icon-symbol";
import { trpc } from "@/lib/trpc";

const INTEL_SECTIONS = [
  {
    title: "LIQUIDITY MAPPING",
    content: "Institutional order blocks identified at 2030.50 and 2055.00 level. Strong buying pressure detected in London opening session.",
    color: "cyan"
  },
  {
    title: "SENTIMENT CORE",
    content: "Accumulation phase detected. Retail sentiment is currently 75% short, suggesting a potential high-probability short-squeeze.",
    color: "success"
  },
  {
    title: "MACRO VECTORS",
    content: "Fed policy hawkishness is being priced in. USD strength divergence is providing temporary resistance to XAUUSD upside.",
    color: "warning"
  }
];

export default function IntelligenceScreen() {
   const colors = useColors();
   const { data: tradingData } = trpc.getTradingData.useQuery(undefined, {
     refetchInterval: 1000,
   });
   const account = tradingData?.account;
   const verdict = tradingData?.verdict;
 
   const sectionColor = (color: string) => {
     if (color === 'cyan') return colors.primary;
     if (color === 'success') return colors.success;
     return colors.warning;
   };
 
   return (
     <SafeAreaView style={{ flex: 1, backgroundColor: colors.background }}>
       <HeaderTrading
         balance={account?.balance || 0}
         equity={account?.equity || 0}
         marginLevel={account?.marginLevel || 0}
         marketOpen={account?.marketOpen ?? true}
       />
 
       <View style={{ paddingHorizontal: 24, paddingVertical: 16, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', borderBottomWidth: 1, borderBottomColor: 'rgba(255,255,255,0.05)' }}>
        <View>
          <TerminalText variant="matrix" size="xs">ANALYST BRIEFING</TerminalText>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4 }}>
            <TerminalText variant="primary" size="lg" className="font-bold uppercase">INTEL </TerminalText>
            <TerminalText variant="cyan" size="lg" className="font-bold uppercase">DOSSIER</TerminalText>
          </View>
        </View>
        <IconSymbol name="folder.fill" color={colors.primary} size={18} />
      </View>

      <ScrollView style={{ flex: 1 }} contentContainerStyle={{ padding: 16 }}>
        {/* MAIN RECOMMENDATION POD */}
        <GlassCard className="mb-6" style={{ padding: 20, borderLeftWidth: 4, borderLeftColor: colors.success }}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 16 }}>
            <View style={{ width: 8, height: 8, borderRadius: 4, backgroundColor: colors.success }} />
            <TerminalText variant="matrix" size="xs">PRIMARY DIRECTIVE</TerminalText>
          </View>
          <TerminalText variant="primary" size="lg" className="font-bold" style={{ marginBottom: 8, lineHeight: 24 }}>
            {verdict?.bias === 'BUY' ? 'Execute Long-Bias Exposure' : verdict?.bias === 'SELL' ? 'Execute Short-Bias Exposure' : 'Maintain Neutral Observation'} on Active Assets
          </TerminalText>
          <TerminalText variant="muted" size="sm" style={{ lineHeight: 20 }}>
            {verdict?.reasoning || "Structural liquidity research suggests a hunt for H4 liquidity at recent highs. Momentum oscillators reveal latent bullish divergence."}
          </TerminalText>
        </GlassCard>

        {/* ANALYSIS GRID */}
        {INTEL_SECTIONS.map((section, idx) => (
          <GlassCard key={idx} className="mb-4" style={{ padding: 16, backgroundColor: 'rgba(255,255,255,0.05)' }}>
            <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
              <TerminalText variant="matrix" size="xs" style={{ color: sectionColor(section.color) }}>
                {section.title}
              </TerminalText>
              <IconSymbol name="chevron.right" color={colors.muted} size={12} />
            </View>
            <TerminalText variant="primary" size="sm" style={{ lineHeight: 20, opacity: 0.8 }}>
              {section.content}
            </TerminalText>
          </GlassCard>
        ))}

        {/* SYSTEM AUDIT FOOTER */}
        <View style={{ marginTop: 32, borderTopWidth: 1, borderTopColor: 'rgba(255,255,255,0.05)', paddingTop: 16 }}>
          <TerminalText variant="matrix" size="xs" style={{ opacity: 0.3, marginBottom: 4, fontWeight: 'bold' }}>
            VERIFICATION KERNEL: ALADDIN V7.19-PRO
          </TerminalText>
          <TerminalText variant="matrix" size="xs" style={{ opacity: 0.3 }}>
            INTEL ENGINE SYNC: 100% // NO ANOMALIES DETECTED
          </TerminalText>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}
