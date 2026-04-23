import { View, ScrollView, SafeAreaView, Pressable } from "react-native";
import { useLocalSearchParams, useRouter } from "expo-router";
import { useColors } from "@/hooks/use-colors";
import { GlassCard } from "@/components/ui/glass-card";
import { TerminalText } from "@/components/ui/terminal-text";
import { IconSymbol } from "@/components/ui/icon-symbol";

export default function PositionDetailScreen() {
  const { id } = useLocalSearchParams();
  const colors = useColors();
  const router = useRouter();

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.background }}>
      {/* HEADER BAR */}
      <View className="px-6 py-4 flex-row items-center justify-between border-b border-white/5">
        <Pressable onPress={() => router.back()} className="flex-row items-center gap-2">
          <IconSymbol name="chevron.left" color={colors.primary} size={18} />
          <TerminalText variant="matrix" size="xs">BACK TO TERMINAL</TerminalText>
        </Pressable>
        <View className="items-end">
          <TerminalText variant="matrix" size="xs">POSITION ID</TerminalText>
          <TerminalText variant="ticker" size="sm">#{id || "77421"}</TerminalText>
        </View>
      </View>

      <ScrollView className="flex-1" contentContainerStyle={{ padding: 16 }}>
        {/* CORE METRICS POD */}
        <GlassCard className="p-6 mb-4 border-l-4 border-l-success glow-cyan">
          <View className="flex-row justify-between items-start mb-6">
            <View>
              <TerminalText variant="primary" size="xl" className="font-black">XAUUSD</TerminalText>
              <TerminalText variant="success" size="xs" className="font-bold tracking-widest">LONG BUY // 0.10 LOTS</TerminalText>
            </View>
            <View className="items-end">
              <TerminalText variant="ticker" size="xl" className="text-success text-[28px]">+$459.20</TerminalText>
              <TerminalText variant="matrix" size="xs">CURRENT P/L</TerminalText>
            </View>
          </View>

          <View className="flex-row justify-between pt-4 border-t border-white/5">
            <View>
              <TerminalText variant="matrix" size="xs">ENTRY PRICE</TerminalText>
              <TerminalText variant="ticker" size="md">2012.45</TerminalText>
            </View>
            <View className="items-end">
              <TerminalText variant="matrix" size="xs">CURRENT PRICE</TerminalText>
              <TerminalText variant="ticker" size="md" className="text-success">2034.12</TerminalText>
            </View>
          </View>
        </GlassCard>

        {/* RISK MAPPING POD */}
        <TerminalText variant="matrix" size="xs" className="mb-3 opacity-40">TECHNICAL RISK MAPPING</TerminalText>
        <GlassCard className="p-4 mb-6">
          <View className="flex-row justify-between items-center mb-1">
            <TerminalText variant="matrix" size="xs" className="text-success">TAKE PROFIT</TerminalText>
            <TerminalText variant="ticker" size="xs">2055.00</TerminalText>
          </View>
          <View className="h-6 bg-white/5 rounded-sm relative justify-center px-1 mb-1">
            <View className="absolute right-0 top-0 bottom-0 w-[40%] bg-success/20 rounded-r-sm" />
            <View className="absolute left-0 top-0 bottom-0 w-[20%] bg-error/20 rounded-l-sm" />
            <View className="w-1.5 h-full bg-primary absolute left-[65%]" />
          </View>
          <View className="flex-row justify-between items-center">
            <TerminalText variant="matrix" size="xs" className="text-error">STOP LOSS</TerminalText>
            <TerminalText variant="ticker" size="xs">1995.00</TerminalText>
          </View>
        </GlassCard>

        {/* AI REASONING LOG */}
        <TerminalText variant="matrix" size="xs" className="mb-3 opacity-40">INSTITUTIONAL EXECUTION LOG</TerminalText>
        <GlassCard className="p-4 mb-6 bg-white/2">
          <View className="flex-row gap-3 mb-3">
            <TerminalText variant="ticker" size="xs" className="opacity-30">14:22:01</TerminalText>
            <TerminalText variant="primary" size="xs" className="flex-1">Order transmitted via Aladdin V7 Bridge.</TerminalText>
          </View>
          <View className="flex-row gap-3 mb-3">
            <TerminalText variant="ticker" size="xs" className="opacity-30">14:22:05</TerminalText>
            <TerminalText variant="primary" size="xs" className="flex-1 text-success font-bold">Execution confirmed at 2012.45 (Zero Slippage).</TerminalText>
          </View>
          <View className="flex-row gap-3">
            <TerminalText variant="ticker" size="xs" className="opacity-30">16:45:12</TerminalText>
            <TerminalText variant="primary" size="xs" className="flex-1 leading-4">Manus AI detected H1 trend confirmation. Trailing SL activated at 2010.00.</TerminalText>
          </View>
        </GlassCard>

        {/* ACTION BUTTONS */}
        <View className="flex-row gap-3">
          <Pressable className="flex-1 py-4 items-center justify-center bg-white/5 border border-white/10 rounded">
            <TerminalText variant="primary" size="xs" className="font-bold">MODIFY SL/TP</TerminalText>
          </Pressable>
          <Pressable className="flex-1 py-4 items-center justify-center bg-error/20 border border-error/40 rounded">
            <TerminalText variant="error" size="xs" className="font-bold uppercase tracking-widest">CLOSE POSITION</TerminalText>
          </Pressable>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}
