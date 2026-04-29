import React from 'react';
import { View, StyleSheet } from 'react-native';
import { useColors } from '@/hooks/use-colors';

interface SparklineProps {
  data: number[];
  width: number;
  height: number;
  color?: string;
}

/**
 * 🚀 PREMIUM PREDATOR SPARKLINE
 * Rendu haute performance sans dépendances SVG.
 * Utilise des barres verticales pour un look "Terminal/Scanner".
 */
export function Sparkline({ data, width, height, color }: SparklineProps) {
  const colors = useColors();
  const activeColor = color || colors.primary;

  if (!data || data.length === 0) return <View style={{ width, height }} />;

  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;

  return (
    <View style={[styles.container, { width, height }]}>
      {data.map((val, idx) => {
        // Normalisation de la hauteur (0 à 100%)
        const normalizedHeight = ((val - min) / range) * height;
        const barWidth = width / data.length - 2;

        return (
          <View
            key={idx}
            style={{
              width: Math.max(2, barWidth),
              height: Math.max(2, normalizedHeight),
              backgroundColor: activeColor,
              borderRadius: 1,
              opacity: 0.3 + (idx / data.length) * 0.7, // Effet de traînée (fade)
              shadowColor: activeColor,
              shadowOffset: { width: 0, height: 0 },
              shadowOpacity: 0.8,
              shadowRadius: 4,
              elevation: 5,
            }}
          />
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    justifyContent: 'space-between',
    paddingBottom: 2,
  },
});
