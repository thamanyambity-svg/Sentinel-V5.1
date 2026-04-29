import { View, ScrollView, SafeAreaView, Pressable, Dimensions, Platform } from "react-native";
import { useColors } from "@/hooks/use-colors";
import { HeaderTrading } from "@/components/header-trading";
import { GlassCard } from "@/components/ui/glass-card";
import { TerminalText } from "@/components/ui/terminal-text";
import { IconSymbol } from "@/components/ui/icon-symbol";
import { trpc } from "@/lib/trpc";

const isDesktop = Platform.OS === 'web';

export default function TradeScreen() {
  const colors = useColors();
  const { data: tradingData } = trpc.getTradingData.useQuery(undefined, {
    refetchInterval: 1000,
  });
  const account = tradingData?.account;
  const tradeMutation = trpc.executeTrade.useMutation();

  const handleTrade = (side: 'BUY' | 'SELL') => {
    console.log(`Executing ${side} order...`);
    tradeMutation.mutate({
      symbol: "XAUUSD",
      side: side,
      volume: 0.1
    }, {
      onSuccess: () => {
        alert(`${side} Order Submitted Successfully`);
      },
      onError: () => {
        alert(`Failed to execute ${side} order`);
      }
    });
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
              <TerminalText variant="ticker" style={{ fontSize: isDesktop ? 84 : 48, lineHeight: isDesktop ? 96 : 56, color: colors.primary }}>0.10</TerminalText>
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
          <Pressable 
            onPress={() => handleTrade('SELL')}
            style={({ pressed }) => ({
              flex: 1, 
              backgroundColor: pressed ? 'rgba(239,68,68,0.4)' : 'rgba(239,68,68,0.2)', 
              borderWidth: 1, 
              borderColor: colors.error, 
              padding: isDesktop ? 48 : 24, 
              borderRadius: 4, 
              alignItems: 'center',
              opacity: tradeMutation.isPending ? 0.5 : 1
            })}
            disabled={tradeMutation.isPending}
          >
            <TerminalText variant="error" size="lg" className="font-bold" style={{ letterSpacing: 4, fontSize: isDesktop ? 32 : 16 }}>SELL</TerminalText>
            <TerminalText variant="error" size="xs" style={{ opacity: 0.6 }}>SHORT MARKET</TerminalText>
          </Pressable>
          
          <Pressable 
            onPress={() => handleTrade('BUY')}
            style={({ pressed }) => ({
              flex: 1, 
              backgroundColor: pressed ? 'rgba(16,185,129,0.4)' : 'rgba(16,185,129,0.2)', 
              borderWidth: 1, 
              borderColor: colors.success, 
              padding: isDesktop ? 48 : 24, 
              borderRadius: 4, 
              alignItems: 'center',
              opacity: tradeMutation.isPending ? 0.5 : 1
            })}
            disabled={tradeMutation.isPending}
          >
            <TerminalText variant="success" size="lg" className="font-bold" style={{ letterSpacing: 4, fontSize: isDesktop ? 32 : 16 }}>BUY</TerminalText>
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
