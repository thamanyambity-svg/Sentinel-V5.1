// screens/TerminalScreen.tsx
import React from 'react';
import { View, Text, StyleSheet, ScrollView } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Colors, Typography, Spacing } from '../constants/Colors';

export default function TerminalScreen() {
  const insets = useSafeAreaInsets();

  const terminalLines = [
    { time: '10:33:45', text: 'TICK EURUSD @ 1.0925 (+0.42%) Vol: 245.2K', type: 'info' },
    { time: '10:33:44', text: 'SIGNAL BUY XAUUSD 75% CONF', type: 'signal' },
    { time: '10:33:42', text: 'TICK GBPUSD @ 1.2750 (-0.15%) Vol: 156.8K', type: 'info' },
    { time: '10:33:40', text: 'SCAN COMPLETE: 47 symbols analyzed', type: 'info' },
    { time: '10:33:38', text: 'VIX SPIKE: 18.5 (+2.1%) ⚠️', type: 'warn' },
  ];

  return (
    <View style={[styles.container, { paddingTop: insets.top }]}>
      <View style={styles.header}>
        <Text style={styles.title}>📡 Market Terminal</Text>
      </View>

      <ScrollView style={styles.terminal}>
        {terminalLines.map((line, idx) => (
          <Text
            key={idx}
            style={[
              styles.terminalLine,
              {
                color:
                  line.type === 'signal'
                    ? Colors.bullish
                    : line.type === 'warn'
                    ? Colors.neutral
                    : Colors.primary,
              },
            ]}
          >
            [{line.time}] {line.text}
          </Text>
        ))}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.appBackground,
  },
  header: {
    padding: Spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: Colors.borderColor,
  },
  title: {
    fontSize: Typography.title.fontSize,
    fontWeight: '700',
    color: Colors.textPrimary,
  },
  terminal: {
    flex: 1,
    padding: Spacing.md,
  },
  terminalLine: {
    fontFamily: 'JetBrains Mono',
    fontSize: 11,
    marginBottom: Spacing.sm,
    fontWeight: '500',
  },
});
