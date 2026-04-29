import { View, Text, TouchableOpacity, Dimensions, Platform } from "react-native";
import { Link } from "expo-router";
import { useColors } from "@/hooks/use-colors";
import { IconSymbol } from "./ui/icon-symbol";

const isDesktop = Platform.OS === 'web';

interface HeaderTradingProps {
  balance: number;
  equity: number;
  marginLevel: number;
  marketOpen: boolean;
}

export function HeaderTrading({
  balance,
  equity,
  marginLevel,
  marketOpen,
}: HeaderTradingProps) {
  const colors = useColors();

  const formatCurrency = (value: number) =>
    new Intl.NumberFormat("fr-FR", {
      style: "currency",
      currency: "USD",
      minimumFractionDigits: 2,
    }).format(value);

  const marginColor =
    marginLevel > 80
      ? colors.error
      : marginLevel > 50
        ? colors.warning
        : colors.success;

  return (
    <View
      className="border-b"
      style={{ backgroundColor: colors.background, borderBottomColor: colors.border }}
    >
      {/* Top Bar: Brand & Status */}
      <View className={isDesktop ? "px-10 py-8 flex-row items-center justify-between" : "px-6 py-5 flex-row items-center justify-between"}>
        <View className="flex-row items-center gap-6">
          <View className={isDesktop ? "w-16 h-16 rounded-xl items-center justify-center bg-primary/10 border border-primary/20" : "w-10 h-10 rounded-lg items-center justify-center bg-primary/10 border border-primary/20"}>
            <Text className={isDesktop ? "text-3xl font-bold" : "text-xl font-bold"} style={{ color: colors.primary, fontFamily: 'Inter_900Black' }}>P</Text>
          </View>
          <View>
            <Text className={isDesktop ? "text-2xl tracking-tighter uppercase" : "text-sm tracking-tighter uppercase"} style={{ color: colors.foreground, fontFamily: 'Inter_900Black' }}>
              SENTINEL <Text style={{ color: colors.primary }}>PREDATOR</Text>
            </Text>
            <View className="flex-row items-center gap-1.5 opacity-40">
              <View className={isDesktop ? "w-3 h-3 rounded-full" : "w-1.5 h-1.5 rounded-full"} style={{ backgroundColor: marketOpen ? colors.success : colors.error }} />
              <Text className={isDesktop ? "text-[12px] uppercase tracking-widest" : "text-[8px] uppercase tracking-widest"} style={{ color: colors.foreground, fontFamily: 'Inter_600SemiBold' }}>
                {marketOpen ? "Live Terminal Operational" : "Session Terminated"}
              </Text>
            </View>
          </View>
        </View>

        <View className="flex-row items-center gap-8">
          <Link href="/(tabs)/settings" asChild>
            <TouchableOpacity className={isDesktop ? "w-14 h-14 items-center justify-center rounded-xl bg-white/5 border border-white/10" : "w-10 h-10 items-center justify-center rounded-lg bg-white/5 border border-white/10"}>
              <IconSymbol name="gearshape.fill" color={colors.foreground} size={isDesktop ? 28 : 18} />
            </TouchableOpacity>
          </Link>
          <View className="items-end">
            <Text className={isDesktop ? "text-[42px] font-mono font-black" : "text-[14px] font-mono font-black"} style={{ color: colors.foreground, fontFamily: 'JetBrainsMono_600SemiBold' }}>
              {formatCurrency(balance)}
            </Text>
            <Text className={isDesktop ? "text-[12px] uppercase tracking-widest opacity-30" : "text-[7px] uppercase tracking-widest opacity-30"} style={{ color: colors.foreground, fontFamily: 'Inter_600SemiBold' }}>
              Institutional Account Balance
            </Text>
          </View>
        </View>
      </View>

      {/* High Density Metric Bar */}
      <View
        className={isDesktop ? "px-10 py-6 flex-row justify-between bg-white/5" : "px-6 py-3 flex-row justify-between bg-white/5"}
        style={{ borderTopColor: colors.border, borderTopWidth: 1 }}
      >
        <View className="gap-1.5">
          <Text className={isDesktop ? "text-[14px] uppercase font-bold tracking-widest opacity-40" : "text-[7px] uppercase font-bold tracking-widest opacity-40"} style={{ color: colors.foreground, fontFamily: 'Inter_600SemiBold' }}>
            Available Equity
          </Text>
          <Text className={isDesktop ? "text-[24px] font-mono" : "text-[11px] font-mono"} style={{ color: colors.primary, fontFamily: 'JetBrainsMono_600SemiBold' }}>
            {formatCurrency(equity)}
          </Text>
        </View>

        <View className="gap-1.5 items-end">
          <Text className={isDesktop ? "text-[14px] uppercase font-bold tracking-widest opacity-40" : "text-[7px] uppercase font-bold tracking-widest opacity-40"} style={{ color: colors.foreground, fontFamily: 'Inter_600SemiBold' }}>
            Margin Utilization
          </Text>
          <Text className={isDesktop ? "text-[24px] font-mono" : "text-[11px] font-mono"} style={{ color: marginColor, fontFamily: 'JetBrainsMono_600SemiBold' }}>
            {marginLevel.toFixed(1)}%
          </Text>
        </View>
      </View>
    </View>
  );
}
