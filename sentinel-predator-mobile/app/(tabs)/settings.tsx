import { View, ScrollView, SafeAreaView, Switch, Pressable } from "react-native";
import { useColors } from "@/hooks/use-colors";
import { HeaderTrading } from "@/components/header-trading";
import { GlassCard } from "@/components/ui/glass-card";
import { TerminalText } from "@/components/ui/terminal-text";
import { IconSymbol } from "@/components/ui/icon-symbol";

export default function SettingsScreen() {
  const colors = useColors();

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.background }}>
      <HeaderTrading 
        balance={125430.82} 
        equity={127890.15} 
        marginLevel={12.4} 
        marketOpen={true} 
      />
      
      <View className="px-6 py-4 flex-row items-center justify-between border-b border-white/5">
        <View>
          <TerminalText variant="matrix" size="xs">SYSTEM CONFIGURATION</TerminalText>
          <TerminalText variant="primary" size="lg" className="font-bold uppercase">PARAMETERS <Text style={{ color: colors.primary }}>HUB</Text></TerminalText>
        </View>
        <IconSymbol name="cpu.fill" color={colors.primary} size={18} />
      </View>

      <ScrollView className="flex-1" contentContainerStyle={{ padding: 16 }}>
        {/* NETWORK STATUS POD */}
        <GlassCard className="p-4 mb-6 flex-row items-center justify-between bg-success/5 border-success/20">
          <View className="flex-row items-center gap-3">
            <View className="w-2 h-2 rounded-full bg-success" />
            <View>
              <TerminalText variant="primary" size="sm" className="font-bold">MT5 BRIDGE LINKED</TerminalText>
              <TerminalText variant="matrix" size="xs" className="opacity-60">LATENCY: 12ms // PORT: 3000</TerminalText>
            </View>
          </View>
          <IconSymbol name="checkmark.shield.fill" color={colors.success} size={20} />
        </GlassCard>

        {/* CORE TOGGLES POD */}
        <TerminalText variant="matrix" size="xs" className="mb-4 opacity-40">AUTOMATION & RISK ENGINE</TerminalText>
        <GlassCard className="mb-6 overflow-hidden">
          {[
            { label: "AI AUTOPILOT ENABLED", desc: "Allow Manus to execute trades", active: true },
            { label: "EMERGENCY CIRCUIT BREAKER", desc: "Stop all activity on 5% drawdown", active: true },
            { label: "HEDGE MODE (DYNAMIC)", desc: "Enable automated counter-positions", active: false },
          ].map((item, idx) => (
            <View key={idx} className={`p-4 flex-row items-center justify-between ${idx !== 2 ? 'border-b border-white/5' : ''}`}>
              <View className="flex-1 mr-4">
                <TerminalText variant="primary" size="sm" className="font-bold">{item.label}</TerminalText>
                <TerminalText variant="matrix" size="xs" className="opacity-40">{item.desc}</TerminalText>
              </View>
              <Switch 
                value={item.active} 
                trackColor={{ false: '#30363d', true: colors.primary }}
                thumbColor="#fff"
              />
            </View>
          ))}
        </GlassCard>

        {/* ACCOUNT POD */}
        <TerminalText variant="matrix" size="xs" className="mb-4 opacity-40">INSTITUTIONAL CREDENTIALS</TerminalText>
        <GlassCard className="p-4 mb-6">
          <View className="flex-row items-center justify-between mb-4">
            <View>
              <TerminalText variant="matrix" size="xs" className="opacity-40">ACCOUNT ID</TerminalText>
              <TerminalText variant="ticker" size="sm">SENTINEL-X-9942</TerminalText>
            </View>
            <View className="items-end">
              <TerminalText variant="matrix" size="xs" className="opacity-40">TIER</TerminalText>
              <TerminalText variant="cyan" size="sm" className="font-black">INSTITUTIONAL</TerminalText>
            </View>
          </View>
          
          <Pressable className="w-full py-3 items-center justify-center bg-white/5 border border-white/10 rounded">
            <TerminalText variant="primary" size="xs" className="font-bold">EXPORT PERFORMANCE LOGS (.JSON)</TerminalText>
          </Pressable>
        </GlassCard>

        <View className="items-center py-4 opacity-10">
          <TerminalText variant="matrix" size="xs">BUILD 5.1.0-PREDATOR // KERNEL v9.42</TerminalText>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}
