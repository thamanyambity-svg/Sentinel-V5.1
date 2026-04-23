// components/PositionItem.tsx
import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Colors, Typography, Spacing } from '../constants/Colors';
import { Position } from '../types';
import Card from './Card';

interface PositionItemProps {
  position: Position;
}

export default function PositionItem({ position }: PositionItemProps) {
  const isProfitable = position.pnl >= 0;
  const pnlColor = isProfitable ? Colors.bullish : Colors.bearish;

  return (
    <Card style={styles.card}>
      <View style={styles.header}>
        <View
          style={[
            styles.symbolBadge,
            {
              backgroundColor: isProfitable
                ? 'rgba(16, 185, 129, 0.1)'
                : 'rgba(239, 68, 68, 0.1)',
            },
          ]}
        >
          <Text
            style={[
              styles.symbol,
              { color: pnlColor },
            ]}
          >
            {position.symbol}
          </Text>
        </View>
        <Text style={[styles.pnl, { color: pnlColor }]}>
          {isProfitable ? '+' : ''}
          ${position.pnl.toFixed(2)}
        </Text>
      </View>

      <View style={styles.row}>
        <Text style={styles.label}>Prix</Text>
        <Text style={styles.mono}>{position.currentPrice.toFixed(4)}</Text>
      </View>
      <View style={styles.row}>
        <Text style={styles.label}>Change</Text>
        <Text style={[styles.mono, { color: pnlColor }]}>
          {isProfitable ? '+' : ''}
          {position.pnlPercent.toFixed(2)}%
        </Text>
      </View>
    </Card>
  );
}

const styles = StyleSheet.create({
  card: {
    marginHorizontal: Spacing.md,
    marginVertical: Spacing.sm,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: Spacing.md,
  },
  symbolBadge: {
    paddingHorizontal: Spacing.sm,
    paddingVertical: Spacing.xs,
    borderRadius: 4,
  },
  symbol: {
    fontSize: 12,
    fontWeight: '700',
  },
  pnl: {
    fontSize: 14,
    fontWeight: '600',
  },
  row: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: Spacing.xs,
  },
  label: {
    fontSize: Typography.label.fontSize,
    fontWeight: '600',
    color: Colors.textSecondary,
    textTransform: 'uppercase',
    letterSpacing: 1,
  },
  mono: {
    fontSize: Typography.mono.fontSize,
    fontWeight: '600',
    color: Colors.textPrimary,
  },
});
