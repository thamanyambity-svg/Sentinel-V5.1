import { View, ScrollView, SafeAreaView } from "react-native";
import { useColors } from "@/hooks/use-colors";
import { HeaderTrading } from "@/components/header-trading";
import { GlassCard } from "@/components/ui/glass-card";
import { TerminalText } from "@/components/ui/terminal-text";
import { IconSymbol } from "@/components/ui/icon-symbol";
import { trpc } from "@/lib/trpc";

export default function DashboardScreen() {
  const colors = useColors();
  const { data: bias } = trpc.getMacroBias.useQuery();

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.background }}>
      <HeaderTrading 
        balance={125430.82} 
        equity={127890.15} 
        marginLevel={12.4} 
        marketOpen={true} 
      />
      
      <ScrollView className="flex-1" contentContainerStyle={{ padding: 16 }}>
        {/* TOP POD: CORE AI INTELLIGENCE */}
        <GlassCard className="p-4 mb-4 border-l-4 border-l-primary glow-cyan">
          <View className="flex-row justify-between items-start mb-4">
            <View>
              <TerminalText variant="matrix" size="xs">SYSTEM STATUS</TerminalText>
              <TerminalText variant="primary" size="lg" className="font-bold">MANUS AI INTELLIGENCE</TerminalText>
            </View>
            <View className="items-end">
              <TerminalText variant="ticker" size="lg">98.2%</TerminalText>
              <TerminalText variant="matrix" size="xs">CONFIDENCE</TerminalText>
            </View>
          </View>
          
          <View className="h-px bg-white/10 mb-4" />
          
          <View className="flex-row justify-between">
            <View className="items-center">
              <IconSymbol name="bolt.fill" color={colors.primary} size={16} />
              <TerminalText variant="matrix" size="xs" className="mt-1">AUTOPILOT</TerminalText>
              <TerminalText variant="ticker" size="sm" className="text-success">ACTIVE</TerminalText>
            </View>
            <View className="items-center">
              <IconSymbol name="shield.fill" color={colors.success} size={16} />
              <TerminalText variant="matrix" size="xs" className="mt-1">RISK LEVEL</TerminalText>
              <TerminalText variant="ticker" size="sm" className="text-success">LOW</TerminalText>
            </View>
            <View className="items-center">
              <IconSymbol name="clock.fill" color={colors.muted} size={16} />
              <TerminalText variant="matrix" size="xs" className="mt-1">UPTIME</TerminalText>
              <TerminalText variant="ticker" size="sm">144H 21M</TerminalText>
            </View>
          </View>
        </GlassCard>

        {/* MID PODS: RISK & SENTIMENT GRID */}
        <View className="flex-row gap-4 mb-4">
          <GlassCard className="p-4 flex-1">
            <TerminalText variant="matrix" size="xs" className="mb-2">MARKET RISK</TerminalText>
            <TerminalText variant="ticker" size="xl" className="text-warning">30</TerminalText>
            <View className="h-1 bg-white/5 mt-2 rounded-full overflow-hidden">
              <View className="h-full bg-warning w-1/3" />
            </View>
            <TerminalText variant="matrix" size="xs" className="mt-2 opacity-30">VIX SENTIMENT: 15.0</TerminalText>
          </GlassCard>
          
          <GlassCard className="p-4 flex-1">
            <TerminalText variant="matrix" size="xs" className="mb-2">TRADE CYCLE</TerminalText>
            <TerminalText variant="ticker" size="xl" className="text-success">ACTIVE</TerminalText>
            <TerminalText variant="matrix" size="xs" className="mt-2 text-primary opacity-60">NEXT REBAL: 02:20:00</TerminalText>
          </GlassCard>
        </View>

        {/* BOTTOM POD: BIAS REASONING */}
        <GlassCard className="p-4 overflow-hidden relative">
          {/* Subtle background icon */}
          <View className="absolute -right-4 -bottom-4 opacity-5">
            <IconSymbol name="doc.text.fill" color={colors.foreground} size={120} />
          </View>

          <View className="flex-row items-center gap-2 mb-3">
            <IconSymbol name="brain.head.profile" color={colors.primary} size={14} />
            <TerminalText variant="matrix" size="xs">INSTITUTIONAL MACRO BIAS</TerminalText>
          </View>
          
          <TerminalText variant="primary" size="sm" className="leading-5 mb-4">
            {bias?.recommendation || "Analyzing global liquidity flow... Momentum indicators show latent bullish divergence on H4 timeframes... Monitoring Fed policy impact targets."}
          </TerminalText>

          <View className="flex-row gap-2">
            <View className="px-2 py-0.5 bg-success/10 border border-success/20 rounded">
              <TerminalText variant="success" size="xs" className="font-bold uppercase">Bullish</TerminalText>
            </View>
            <View className="px-2 py-0.5 bg-white/5 border border-white/10 rounded">
              <TerminalText variant="matrix" size="xs">XAUUSD</TerminalText>
            </View>
          </View>
        </GlassCard>
      </ScrollView>
    </SafeAreaView>
  );
}
