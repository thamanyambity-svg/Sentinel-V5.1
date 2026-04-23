// components/VerdictCard.tsx
import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Colors, Typography, Spacing } from '../constants/Colors';
import { MLSignal } from '../types';
import Card from './Card';

interface VerdictCardProps {
  signal: MLSignal;
}

export default function VerdictCard({ signal }: VerdictCardProps) {
  const sentimentColor =
    signal.sentiment === 'BULLISH'
      ? Colors.bullish
      : signal.sentiment === 'BEARISH'
      ? Colors.bearish
      : Colors.neutral;

  return (
    <Card
      style={[
        styles.card,
        {
          borderColor:
            signal.sentiment === 'BULLISH'
              ? `rgba(16, 185, 129, 0.2)`
              : signal.sentiment === 'BEARISH'
              ? `rgba(239, 68, 68, 0.2)`
              : `rgba(245, 158, 11, 0.2)`,
        },
      ]}
    >
      <Text style={styles.label}>MANUS AI BIAS VERDICT</Text>
      <Text style={[styles.sentiment, { color: sentimentColor }]}>
        {signal.sentiment}
      </Text>
      <View style={styles.confidenceContainer}>
        <Text style={styles.label}>Confiance</Text>
        <View style={styles.confidenceBar}>
          <View
            style={[
              styles.confidenceFill,
              {
                width: `${signal.confidence}%`,
                backgroundColor: sentimentColor,
              },
            ]}
          />
        </View>
      </View>
      <Text style={[styles.mono, { marginTop: Spacing.md }]}>
        {signal.confidence}% • {signal.symbol}
      </Text>
    </Card>
  );
}

const styles = StyleSheet.create({
  card: {
    marginHorizontal: Spacing.md,
    marginVertical: Spacing.md,
    alignItems: 'center',
  },
  label: {
    fontSize: Typography.label.fontSize,
    fontWeight: '600',
    color: Colors.textSecondary,
    marginBottom: Spacing.md,
    textTransform: 'uppercase',
    letterSpacing: 1,
  },
  sentiment: {
    fontSize: 32,
    fontWeight: '700',
    marginBottom: Spacing.md,
  },
  confidenceContainer: {
    width: '100%',
    marginVertical: Spacing.md,
  },
  confidenceBar: {
    height: 4,
    backgroundColor: Colors.borderColor,
    borderRadius: 2,
    overflow: 'hidden',
    marginTop: Spacing.sm,
  },
  confidenceFill: {
    height: '100%',
  },
  mono: {
    fontSize: Typography.mono.fontSize,
    fontWeight: '600',
    color: Colors.textPrimary,
  },
});
