import { View, ScrollView, SafeAreaView, Dimensions, Platform } from "react-native";
import { useColors } from "@/hooks/use-colors";
import { HeaderTrading } from "@/components/header-trading";
import { GlassCard } from "@/components/ui/glass-card";
import { TerminalText } from "@/components/ui/terminal-text";
import { IconSymbol } from "@/components/ui/icon-symbol";
import { trpc } from "@/lib/trpc";
import { Sparkline } from "@/components/ui/sparkline";

const isDesktop = Platform.OS === 'web';

export default function DashboardScreen() {
  const colors = useColors();
  const { data: tradingData, isLoading } = trpc.getTradingData.useQuery(undefined, {
    refetchInterval: 1000, // Refresh every 1 second - DIRECT LINE
  });

  const account = tradingData?.account;
  const verdict = tradingData?.verdict;
  const risk = tradingData?.risk;

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.background }}>
      <HeaderTrading 
        balance={account?.balance || 0} 
        equity={account?.equity || 0} 
        marginLevel={account?.marginLevel || 0} 
        marketOpen={account?.marketOpen ?? true} 
      />
      
      <ScrollView className="flex-1" contentContainerStyle={{ padding: isDesktop ? 32 : 16 }}>
        {/* TOP POD: CORE AI INTELLIGENCE */}
        <GlassCard className={isDesktop ? "p-8 mb-6 border-l-4 border-l-primary" : "p-4 mb-4 border-l-4 border-l-primary"} glowColor={colors.primary} glowIntensity={0.2}>
          <View className="flex-row justify-between items-start mb-6">
            <View>
              <TerminalText variant="matrix" size="xs">SYSTEM CORE STATUS</TerminalText>
              <TerminalText variant="primary" size="lg" className="font-bold" style={{ fontSize: isDesktop ? 32 : 18 }}>MANUS AI INTELLIGENCE</TerminalText>
            </View>
            <View className="items-end">
              <TerminalText variant="ticker" size="lg">{(verdict?.confidence || 0 * 100).toFixed(1)}%</TerminalText>
              <TerminalText variant="matrix" size="xs">CONFIDENCE</TerminalText>
            </View>
          </View>
          
          <View className="h-px bg-white/10 mb-4" />
          
          <View className="flex-row justify-between">
            <View className="items-center">
              <IconSymbol name="bolt.fill" color={colors.primary} size={16} />
              <TerminalText variant="matrix" size="xs" className="mt-1">AUTOPILOT</TerminalText>
              <TerminalText variant="ticker" size="sm" className={account?.marketOpen ? "text-success" : "text-error"}>
                {account?.marketOpen ? "ACTIVE" : "STANDBY"}
              </TerminalText>
            </View>
            <View className="items-center">
              <IconSymbol name="shield.fill" color={colors.success} size={16} />
              <TerminalText variant="matrix" size="xs" className="mt-1">RISK LEVEL</TerminalText>
              <TerminalText variant="ticker" size="sm" className="text-success">LOW</TerminalText>
            </View>
            <View className="items-center">
              <IconSymbol name="clock.fill" color={colors.muted} size={16} />
              <TerminalText variant="matrix" size="xs" className="mt-1">STATUS</TerminalText>
              <TerminalText variant="ticker" size="sm">ONLINE</TerminalText>
            </View>
          </View>
        </GlassCard>

        {/* MID PODS: RISK & SENTIMENT GRID */}
        <View className="flex-row gap-4 mb-4">
          {(() => {
            const riskScore = risk?.marketRisk || 0;
            const dynamicGlowColor = riskScore > 70 ? colors.error : riskScore > 40 ? colors.warning : colors.primary;
            return (
              <GlassCard 
                className="p-4 flex-1" 
                glowColor={dynamicGlowColor} 
                glowIntensity={riskScore > 40 ? 0.6 : 0.3}
              >
                <TerminalText variant="matrix" size="xs" className="mb-2">MARKET RISK</TerminalText>
                <TerminalText variant="ticker" size="xl" className={riskScore > 70 ? "text-error" : (riskScore > 40 ? "text-warning" : "text-primary")}>
                  {riskScore}
                </TerminalText>
                <View className="h-1 bg-white/5 mt-2 rounded-full overflow-hidden">
                  <View className="h-full bg-warning" style={{ width: `${riskScore}%`, backgroundColor: dynamicGlowColor }} />
                </View>
                <TerminalText variant="matrix" size="xs" className="mt-2 opacity-30">VIX: {risk?.vix || "N/A"}</TerminalText>
              </GlassCard>
            );
          })()}
          
          <GlassCard className="p-4 flex-1">
            <TerminalText variant="matrix" size="xs" className="mb-2">TRADE CYCLE</TerminalText>
            <TerminalText variant="ticker" size="xl" className="text-success">
              {tradingData?.positions?.length > 0 ? "ACTIVE" : "IDLE"}
            </TerminalText>
            <TerminalText variant="matrix" size="xs" className="mt-2 text-primary opacity-60">POSITIONS: {tradingData?.positions?.length || 0}</TerminalText>
          </GlassCard>
        </View>

        {/* MARKET TREND POD: SPARKLINE */}
        <GlassCard className="p-4 mb-4">
          <View className="flex-row justify-between items-center mb-4">
            <View>
              <TerminalText variant="matrix" size="xs">LIVE ASSET VOLATILITY</TerminalText>
              <TerminalText variant="primary" size="md" className="font-bold">XAUUSD TREND</TerminalText>
            </View>
            <IconSymbol name="chart.line.uptrend.xyaxes" color={colors.primary} size={16} />
          </View>
          <View className="items-center justify-center py-2">
            <Sparkline data={tradingData?.history?.XAUUSD || [1,2,1.5,3,2.5,1,4,3.5,5]} width={280} height={60} />
          </View>
        </GlassCard>

        {/* BOTTOM POD: BIAS REASONING */}
        <GlassCard className="p-4 overflow-hidden relative">
          <View className="absolute -right-4 -bottom-4 opacity-5">
            <IconSymbol name="brain.head.profile" color={colors.foreground} size={120} />
          </View>

          <View className="flex-row items-center gap-2 mb-3">
            <IconSymbol name="brain.head.profile" color={colors.primary} size={14} />
            <TerminalText variant="matrix" size="xs">INSTITUTIONAL MACRO BIAS</TerminalText>
          </View>
          
          <TerminalText variant="primary" size="sm" className="leading-5 mb-4">
            {verdict?.reasoning || "Analyzing global liquidity flow... Momentum indicators show latent bullish divergence on H4 timeframes..."}
          </TerminalText>

          <View className="flex-row gap-2">
            <View className={`px-2 py-0.5 rounded border ${verdict?.bias === 'BUY' ? 'bg-success/10 border-success/20' : verdict?.bias === 'SELL' ? 'bg-error/10 border-error/20' : 'bg-white/5 border-white/10'}`}>
              <TerminalText variant={verdict?.bias === 'BUY' ? 'success' : verdict?.bias === 'SELL' ? 'error' : 'matrix'} size="xs" className="font-bold uppercase">
                {verdict?.bias || "NEUTRAL"}
              </TerminalText>
            </View>
            <View className="px-2 py-0.5 bg-white/5 border border-white/10 rounded">
              <TerminalText variant="matrix" size="xs">SENTINEL-X</TerminalText>
            </View>
          </View>
        </GlassCard>
      </ScrollView>
    </SafeAreaView>
  );
}
