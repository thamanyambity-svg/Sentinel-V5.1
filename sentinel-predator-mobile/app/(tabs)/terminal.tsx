import { View, ScrollView, SafeAreaView } from "react-native";
import { useColors } from "@/hooks/use-colors";
import { HeaderTrading } from "@/components/header-trading";
import { GlassCard } from "@/components/ui/glass-card";
import { TerminalText } from "@/components/ui/terminal-text";
import { IconSymbol } from "@/components/ui/icon-symbol";

const MOCK_SCANNER = [
  { pair: "XAUUSD", price: "2034.12", change: "+0.45%", trend: "up", volume: "High" },
  { pair: "EURUSD", price: "1.08542", change: "-0.12%", trend: "down", volume: "Mid" },
  { pair: "GBPUSD", price: "1.26781", change: "+0.02%", trend: "up", volume: "Low" },
  { pair: "NAS100", price: "17845.20", change: "+1.24%", trend: "up", volume: "Extreme" },
  { pair: "USDJPY", price: "148.241", change: "+0.54%", trend: "up", volume: "Mid" },
];

export default function TerminalScreen() {
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
          <TerminalText variant="matrix" size="xs">REAL-TIME ASSET RADAR</TerminalText>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4 }}>
            <TerminalText variant="primary" size="lg" className="font-bold uppercase">TERMINAL </TerminalText>
            <TerminalText variant="cyan" size="lg" className="font-bold uppercase">SCANNER</TerminalText>
          </View>
        </View>
        <IconSymbol name="antenna.radiowaves.left.and.right" color={colors.primary} size={18} />
      </View>

      <ScrollView style={{ flex: 1 }} contentContainerStyle={{ padding: 16 }}>
        <View style={{ flexDirection: 'row', paddingHorizontal: 16, marginBottom: 8, opacity: 0.4 }}>
          <View style={{ flex: 1 }}><TerminalText variant="matrix" size="xs">SYMBOL</TerminalText></View>
          <View style={{ flex: 1 }}><TerminalText variant="matrix" size="xs">PRICE</TerminalText></View>
          <View style={{ width: 80 }}><TerminalText variant="matrix" size="xs">DELTA</TerminalText></View>
        </View>

        {MOCK_SCANNER.map((item, idx) => (
          <GlassCard key={idx} className="mb-2" style={{ flexDirection: 'row', alignItems: 'center', padding: 16 }}>
            <View style={{ flex: 1 }}>
              <TerminalText variant="primary" size="sm" className="font-bold">{item.pair}</TerminalText>
              <TerminalText variant="matrix" size="xs">VOL: {item.volume}</TerminalText>
            </View>
            <View style={{ flex: 1 }}>
              <TerminalText variant="ticker" size="md">{item.price}</TerminalText>
            </View>
            <View style={{ width: 80, alignItems: 'flex-end' }}>
              <View style={{
                paddingHorizontal: 8, paddingVertical: 2, borderRadius: 2,
                backgroundColor: item.trend === 'up' ? 'rgba(16,185,129,0.05)' : 'rgba(239,68,68,0.05)',
                borderWidth: 1, borderColor: item.trend === 'up' ? 'rgba(16,185,129,0.2)' : 'rgba(239,68,68,0.2)'
              }}>
                <TerminalText variant={item.trend === 'up' ? 'success' : 'error'} size="xs" className="font-bold">
                  {item.change}
                </TerminalText>
              </View>
            </View>
          </GlassCard>
        ))}

        <View style={{ marginTop: 24 }}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 8, opacity: 0.3 }}>
            <View style={{ width: 6, height: 6, borderRadius: 3, backgroundColor: colors.primary }} />
            <TerminalText variant="matrix" size="xs">PREDATOR CORE FEED CONNECTED</TerminalText>
          </View>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}
