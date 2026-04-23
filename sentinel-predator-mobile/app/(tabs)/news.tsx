import { View, ScrollView, SafeAreaView } from "react-native";
import { useColors } from "@/hooks/use-colors";
import { HeaderTrading } from "@/components/header-trading";
import { GlassCard } from "@/components/ui/glass-card";
import { TerminalText } from "@/components/ui/terminal-text";
import { IconSymbol } from "@/components/ui/icon-symbol";

const MOCK_NEWS = [
  { time: "14:30", event: "US Core PCE Price Index (MoM)", impact: "HIGH", forecast: "0.4%", actual: "0.3%", status: "success" },
  { time: "15:15", event: "Industrial Production (MoM)", impact: "MID", forecast: "0.1%", actual: "--", status: "muted" },
  { time: "10:00", event: "Consumer Confidence", impact: "HIGH", forecast: "114.8", actual: "110.9", status: "error" },
];

export default function NewsScreen() {
  const colors = useColors();

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.background }}>
      <HeaderTrading
        balance={125430.82}
        equity={127890.15}
        marginLevel={12.4}
        marketOpen={true}
      />

      <View style={{ paddingHorizontal: 24, paddingVertical: 16, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', borderBottomWidth: 1, borderBottomColor: 'rgba(255,255,255,0.05)' }}>
        <View>
          <TerminalText variant="matrix" size="xs">ECONOMIC CALENDAR</TerminalText>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4 }}>
            <TerminalText variant="primary" size="lg" className="font-bold uppercase">NEWS </TerminalText>
            <TerminalText variant="cyan" size="lg" className="font-bold uppercase">RADAR</TerminalText>
          </View>
        </View>
        <IconSymbol name="dot.radiowaves.right" color={colors.primary} size={18} />
      </View>

      <ScrollView style={{ flex: 1 }} contentContainerStyle={{ padding: 16 }}>
        {/* HIGH IMPACT ALERT */}
        <GlassCard className="mb-6" style={{ padding: 16, backgroundColor: 'rgba(239,68,68,0.1)', borderWidth: 1, borderColor: 'rgba(239,68,68,0.3)', borderLeftWidth: 4, borderLeftColor: colors.error }}>
          <TerminalText variant="error" size="xs" style={{ fontWeight: 'bold', marginBottom: 8, letterSpacing: 2 }}>
            CRITICAL VOLATILITY EVENT
          </TerminalText>
          <TerminalText variant="primary" size="md" style={{ fontWeight: 'bold', marginBottom: 4 }}>
            FOMC PRESS CONFERENCE IN 02:45:12
          </TerminalText>
          <TerminalText variant="muted" size="sm" style={{ opacity: 0.7, lineHeight: 18 }}>
            Market expected to experience extreme liquidity fluctuations. Autopilot adjusted to High-Volatility mode.
          </TerminalText>
        </GlassCard>

        <TerminalText variant="matrix" size="xs" style={{ marginBottom: 16, opacity: 0.4 }}>
          INSTITUTIONAL EVENT STREAM
        </TerminalText>

        {MOCK_NEWS.map((news, idx) => (
          <GlassCard key={idx} className="mb-3" style={{ padding: 16 }}>
            <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
                <TerminalText variant="ticker" size="sm">{news.time}</TerminalText>
                <View style={{
                  paddingHorizontal: 8, paddingVertical: 2, borderRadius: 2,
                  backgroundColor: news.impact === 'HIGH' ? 'rgba(239,68,68,0.1)' : 'rgba(245,158,11,0.1)'
                }}>
                  <TerminalText
                    variant={news.impact === 'HIGH' ? 'error' : 'warning'}
                    size="xs"
                    style={{ fontWeight: 'bold' }}
                  >
                    {news.impact}
                  </TerminalText>
                </View>
              </View>
              <IconSymbol name="chart.bar.fill" color={colors.muted} size={14} />
            </View>

            <TerminalText variant="primary" size="sm" style={{ fontWeight: 'bold', marginBottom: 12 }}>
              {news.event}
            </TerminalText>

            <View style={{ flexDirection: 'row', gap: 24, backgroundColor: 'rgba(255,255,255,0.05)', padding: 12, borderRadius: 4 }}>
              <View>
                <TerminalText variant="matrix" size="xs" style={{ opacity: 0.4 }}>FORECAST</TerminalText>
                <TerminalText variant="ticker" size="sm">{news.forecast}</TerminalText>
              </View>
              <View>
                <TerminalText variant="matrix" size="xs" style={{ opacity: 0.4 }}>ACTUAL</TerminalText>
                <TerminalText
                  variant={news.status as any}
                  size="sm"
                  style={{ fontWeight: 'bold' }}
                >
                  {news.actual}
                </TerminalText>
              </View>
            </View>
          </GlassCard>
        ))}

        <View style={{ alignItems: 'center', paddingVertical: 24, opacity: 0.2 }}>
          <TerminalText variant="matrix" size="xs">END OF DAILY CYCLE STREAM</TerminalText>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}
