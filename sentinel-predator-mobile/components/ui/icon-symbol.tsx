import { MaterialIcons } from '@expo/vector-icons';
import React from 'react';
import { OpaqueColorValue, StyleProp, ViewStyle } from 'react-native';

// Mapping SF Symbols names to MaterialIcons
const MAPPING = {
  'house.fill': 'home',
  'terminal.fill': 'code',
  'chart.bar.fill': 'bar-chart',
  'brain.fill': 'psychology',
  'gearshape.fill': 'settings',
} as const;

export type IconSymbolName = keyof typeof MAPPING;

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
  return <MaterialIcons color={color} size={size} name={MAPPING[name]} style={style} />;
}
