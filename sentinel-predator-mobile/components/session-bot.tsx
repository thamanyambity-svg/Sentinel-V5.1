import { View, Text } from "react-native";
import { useColors } from "@/hooks/use-colors";
import { useEffect, useState } from "react";

interface SessionBotProps {
  isActive: boolean;
  countdownSeconds: number;
}

export function SessionBot({ isActive, countdownSeconds }: SessionBotProps) {
  const colors = useColors();
  const [displayTime, setDisplayTime] = useState("00:00:00");

  useEffect(() => {
    const hours = Math.floor(countdownSeconds / 3600);
    const minutes = Math.floor((countdownSeconds % 3600) / 60);
    const seconds = countdownSeconds % 60;
    setDisplayTime(
      `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`
    );
  }, [countdownSeconds]);

  return (
    <View
      className="rounded-lg p-4 gap-3 border-l-4"
      style={{
        backgroundColor: colors.surface,
        borderLeftColor: colors.warning,
      }}
    >
      <View className="flex-row items-start justify-between">
        <View className="flex-1">
          <Text className="text-[9px] uppercase font-bold mb-1" style={{ color: colors.muted }}>
            Cycle d'Autorisation (07h-23h)
          </Text>
          <Text
            className="text-lg font-black tracking-tighter uppercase"
            style={{ color: colors.warning }}
          >
            {isActive ? "BOT ACTIF" : "BOT EN VEILLE"}
          </Text>
        </View>

        <View
          className="w-10 h-10 rounded items-center justify-center"
          style={{
            backgroundColor: `${colors.warning}20`,
          }}
        >
          <Text className="text-lg">⏰</Text>
        </View>
      </View>

      <View
        className="h-px"
        style={{ backgroundColor: colors.border }}
      />

      <View className="gap-1">
        <Text className="text-[8px] uppercase font-black tracking-widest" style={{ color: colors.muted }}>
          Démarrage du trading dans :
        </Text>
        <Text className="text-2xl font-black font-mono tracking-wider" style={{ color: colors.foreground }}>
          {displayTime}
        </Text>
      </View>
    </View>
  );
}
