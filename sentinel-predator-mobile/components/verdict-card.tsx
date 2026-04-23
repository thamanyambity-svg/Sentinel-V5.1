import { View, Text } from "react-native";
import { useColors } from "@/hooks/use-colors";

type VerdictType = "BULLISH" | "NEUTRAL" | "BEARISH";

interface VerdictCardProps {
  verdict: VerdictType;
  confidence: number;
}

export function VerdictCard({ verdict, confidence }: VerdictCardProps) {
  const colors = useColors();

  const verdictColor = {
    BULLISH: colors.success,
    NEUTRAL: colors.warning,
    BEARISH: colors.error,
  }[verdict];

  return (
    <View
      className="rounded-2xl p-8 items-center gap-6 shadow-2xl relative overflow-hidden"
      style={{
        backgroundColor: colors.surface,
        borderColor: `${verdictColor}40`,
        borderWidth: 1.5,
      }}
    >
      {/* Background Glow Effect */}
      <View 
        className="absolute -top-20 -right-20 w-40 h-40 rounded-full opacity-10" 
        style={{ backgroundColor: verdictColor }}
      />

      <View className="items-center gap-1">
        <Text className="text-[10px] font-black uppercase tracking-[0.3em] opacity-40" style={{ color: colors.foreground }}>
          Manus AI Intelligence
        </Text>
        <View className="h-[1px] w-8" style={{ backgroundColor: verdictColor }} />
      </View>

      <View className="items-center">
        <Text
          className="text-6xl font-black tracking-tighter uppercase"
          style={{ 
            color: verdictColor,
            textShadowColor: `${verdictColor}80`,
            textShadowOffset: { width: 0, height: 0 },
            textShadowRadius: 15
          }}
        >
          {verdict}
        </Text>
      </View>

      <View className="w-full gap-4">
        <View className="flex-row justify-between items-end">
          <Text className="text-[9px] font-black uppercase opacity-40" style={{ color: colors.foreground }}>
            Confidence Level
          </Text>
          <Text className="text-xs font-mono font-black" style={{ color: verdictColor }}>
            {confidence.toFixed(0)}%
          </Text>
        </View>
        
        <View
          className="w-full h-2 rounded-full overflow-hidden bg-black/40"
          style={{ borderColor: colors.border, borderWidth: 1 }}
        >
          <View
            className="h-full rounded-full"
            style={{
              width: `${confidence}%`,
              backgroundColor: verdictColor,
              shadowColor: verdictColor,
              shadowOffset: { width: 0, height: 0 },
              shadowRadius: 10,
              shadowOpacity: 0.8
            }}
          />
        </View>
      </View>
    </View>
  );
}
