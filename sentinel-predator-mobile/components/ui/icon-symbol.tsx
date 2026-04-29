import { MaterialIcons } from '@expo/vector-icons';
import React from 'react';
import { OpaqueColorValue, StyleProp, ViewStyle, Dimensions, Platform } from 'react-native';

const isDesktop = Platform.OS === 'web';

// Mapping SF Symbols names to MaterialIcons
const MAPPING = {
  'house.fill': 'home',
  'terminal.fill': 'code',
  'chart.bar.fill': 'bar-chart',
  'brain.fill': 'psychology',
  'gearshape.fill': 'settings',
  'globe.americas.fill': 'public',
  'dot.radiowaves.right': 'sensors',
  'cpu.fill': 'memory',
  'checkmark.shield.fill': 'verified-user',
} as const;

export type IconSymbolName = keyof typeof MAPPING | string;

export function IconSymbol({
  name,
  size = 24,
  color,
  style,
}: {
  name: IconSymbolName;
  size?: number;
  color: string | OpaqueColorValue;
  style?: StyleProp<ViewStyle>;
}) {
  const scaledSize = isDesktop ? size * 1.6 : size;
  return <MaterialIcons color={color} size={scaledSize} name={(MAPPING as any)[name] || name} style={style} />;
}
