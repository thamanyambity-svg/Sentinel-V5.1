import { View, ScrollView, SafeAreaView, Pressable } from "react-native";
import { useColors } from "@/hooks/use-colors";
import { HeaderTrading } from "@/components/header-trading";
import { GlassCard } from "@/components/ui/glass-card";
import { TerminalText } from "@/components/ui/terminal-text";
import { IconSymbol } from "@/components/ui/icon-symbol";

export default function TradeScreen() {
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
          <TerminalText variant="matrix" size="xs">DIRECT EXECUTION</TerminalText>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4 }}>
            <TerminalText variant="primary" size="lg" className="font-bold uppercase">TRADE </TerminalText>
            <TerminalText variant="cyan" size="lg" className="font-bold uppercase">CONSOLE</TerminalText>
          </View>
        </View>
        <IconSymbol name="terminal.fill" color={colors.primary} size={18} />
      </View>

      <ScrollView style={{ flex: 1 }} contentContainerStyle={{ padding: 16 }}>
        {/* ASSET SELECTOR POD */}
        <GlassCard className="mb-4" style={{ padding: 16, borderLeftWidth: 4, borderLeftColor: colors.primary }}>
          <TerminalText variant="matrix" size="xs" className="mb-2">SELECT ACTIVE TERMINAL</TerminalText>
          <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
            {["XAUUSD", "EURUSD", "GBPUSD", "NAS100"].map((pair) => (
              <Pressable
                key={pair}
                style={{
                  paddingHorizontal: 16, paddingVertical: 8, borderRadius: 2,
                  backgroundColor: pair === 'XAUUSD' ? 'rgba(8,145,178,0.2)' : 'rgba(255,255,255,0.05)',
                  borderWidth: 1, borderColor: pair === 'XAUUSD' ? colors.primary : 'rgba(255,255,255,0.1)'
                }}
              >
                <TerminalText variant={pair === 'XAUUSD' ? 'cyan' : 'primary'} size="sm" className="font-bold">{pair}</TerminalText>
              </Pressable>
            ))}
          </View>
        </GlassCard>

        {/* EXECUTION PARAMS POD */}
        <GlassCard className="mb-6" style={{ padding: 24, alignItems: 'center' }}>
          <TerminalText variant="matrix" size="xs" className="mb-4">LOT SIZE / VOLUME</TerminalText>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 32 }}>
            <Pressable style={{ width: 40, height: 40, borderRadius: 20, backgroundColor: 'rgba(255,255,255,0.05)', alignItems: 'center', justifyContent: 'center', borderWidth: 1, borderColor: 'rgba(255,255,255,0.1)' }}>
              <IconSymbol name="minus" color={colors.foreground} size={20} />
            </Pressable>
            <View style={{ alignItems: 'center' }}>
              <TerminalText variant="ticker" size="xl" style={{ fontSize: 48, lineHeight: 56, color: colors.primary }}>0.10</TerminalText>
              <TerminalText variant="matrix" size="xs" style={{ opacity: 0.3 }}>STANDARD LOTS</TerminalText>
            </View>
            <Pressable style={{ width: 40, height: 40, borderRadius: 20, backgroundColor: 'rgba(255,255,255,0.05)', alignItems: 'center', justifyContent: 'center', borderWidth: 1, borderColor: 'rgba(255,255,255,0.1)' }}>
              <IconSymbol name="plus" color={colors.foreground} size={20} />
            </Pressable>
          </View>

          <View style={{ flexDirection: 'row', gap: 24, marginTop: 32, width: '100%' }}>
            <View style={{ flex: 1 }}>
              <TerminalText variant="error" size="xs" style={{ marginBottom: 4 }}>STOP LOSS</TerminalText>
              <TerminalText variant="ticker" size="md">AUTO-GUARD</TerminalText>
            </View>
            <View style={{ flex: 1, alignItems: 'flex-end' }}>
              <TerminalText variant="success" size="xs" style={{ marginBottom: 4 }}>TAKE PROFIT</TerminalText>
              <TerminalText variant="ticker" size="md">DYNAMIC</TerminalText>
            </View>
          </View>
        </GlassCard>

        {/* ORDER BUTTONS */}
        <View style={{ flexDirection: 'row', gap: 16, marginBottom: 24 }}>
          <Pressable style={{ flex: 1, backgroundColor: 'rgba(239,68,68,0.2)', borderWidth: 1, borderColor: colors.error, padding: 24, borderRadius: 4, alignItems: 'center' }}>
            <TerminalText variant="error" size="lg" className="font-bold" style={{ letterSpacing: 4 }}>SELL</TerminalText>
            <TerminalText variant="error" size="xs" style={{ opacity: 0.6 }}>SHORT MARKET</TerminalText>
          </Pressable>
          <Pressable style={{ flex: 1, backgroundColor: 'rgba(16,185,129,0.2)', borderWidth: 1, borderColor: colors.success, padding: 24, borderRadius: 4, alignItems: 'center' }}>
            <TerminalText variant="success" size="lg" className="font-bold" style={{ letterSpacing: 4 }}>BUY</TerminalText>
            <TerminalText variant="success" size="xs" style={{ opacity: 0.6 }}>LONG MARKET</TerminalText>
          </Pressable>
        </View>

        <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, opacity: 0.3 }}>
          <TerminalText variant="matrix" size="xs">INSTITUTIONAL ALADDIN BRIDGE ACTIVE</TerminalText>
          <View style={{ width: 4, height: 4, borderRadius: 2, backgroundColor: colors.success }} />
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}
