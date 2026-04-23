import { View, Text } from "react-native";
import { useColors } from "@/hooks/use-colors";

interface RiskMetricsProps {
  marketRisk: number;
  vixFear: number;
}

export function RiskMetrics({ marketRisk, vixFear }: RiskMetricsProps) {
  const colors = useColors();

  const getRiskColor = (risk: number) => {
    if (risk > 70) return colors.error;
    if (risk > 40) return colors.warning;
    return colors.success;
  };

  return (
    <View className="flex-row gap-4">
      <View
        className="flex-1 rounded-lg p-4 items-center gap-2"
        style={{
          backgroundColor: colors.surface,
          borderColor: colors.border,
          borderWidth: 1,
        }}
      >
        <Text className="text-[9px] uppercase font-bold" style={{ color: colors.muted }}>
          Market Risk
        </Text>
        <Text
          className="text-2xl font-black"
          style={{ color: getRiskColor(marketRisk) }}
        >
          {marketRisk.toFixed(0)}
        </Text>
        <Text className="text-[8px]" style={{ color: colors.muted }}>/100</Text>
      </View>

      <View
        className="flex-1 rounded-lg p-4 items-center gap-2"
        style={{
          backgroundColor: colors.surface,
          borderColor: colors.border,
          borderWidth: 1,
        }}
      >
        <Text className="text-[9px] uppercase font-bold" style={{ color: colors.muted }}>
          VIX Fear
        </Text>
        <Text
          className="text-2xl font-mono font-black"
          style={{ color: getRiskColor(vixFear * 2) }}
        >
          {vixFear.toFixed(2)}
        </Text>
        <Text className="text-[8px]" style={{ color: colors.muted }}>Index</Text>
      </View>
    </View>
  );
}
