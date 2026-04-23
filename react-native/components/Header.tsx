// components/Header.tsx
import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Colors, Typography, Spacing } from '../constants/Colors';
import { AccountData } from '../types';

interface HeaderProps {
  title: string;
  subtitle?: string;
  status?: 'connected' | 'offline';
  account: AccountData;
}

export default function Header({ title, subtitle, status, account }: HeaderProps) {
  const insets = useSafeAreaInsets();

  return (
    <View style={[styles.header, { paddingTop: insets.top }]}>
      <View style={styles.headerTop}>
        <View style={styles.logoContainer}>
          <View style={styles.logoIcon}>
            <Text style={styles.logoText}>SP</Text>
          </View>
          <Text style={styles.title}>{title}</Text>
        </View>
        <View style={[styles.statusDot, { backgroundColor: status === 'connected' ? Colors.bullish : Colors.bearish }]} />
      </View>

      <View style={styles.statsGrid}>
        <View style={styles.statItem}>
          <Text style={styles.label}>Solde</Text>
          <Text style={styles.statValue}>${account.balance.toFixed(2)}</Text>
        </View>
        <View style={styles.statItem}>
          <Text style={styles.label}>Equity</Text>
          <Text style={[styles.statValue, { color: Colors.bullish }]}>
            ${account.equity.toFixed(2)}
          </Text>
        </View>
        <View style={styles.statItem}>
          <Text style={styles.label}>Marge</Text>
          <Text style={styles.statValue}>{account.marginLevel}%</Text>
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  header: {
    paddingHorizontal: Spacing.md,
    paddingBottom: Spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: Colors.borderColor,
    backgroundColor: 'rgba(13, 17, 23, 0.9)',
  },
  headerTop: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: Spacing.md,
  },
  logoContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
  },
  logoIcon: {
    width: 24,
    height: 24,
    borderRadius: 6,
    backgroundColor: Colors.primary,
    justifyContent: 'center',
    alignItems: 'center',
  },
  logoText: {
    color: 'white',
    fontWeight: '700',
    fontSize: 12,
  },
  title: {
    fontSize: Typography.title.fontSize,
    fontWeight: '700',
    color: Colors.textPrimary,
  },
  statusDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  statsGrid: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    gap: Spacing.md,
  },
  statItem: {
    flex: 1,
    alignItems: 'center',
  },
  label: {
    fontSize: Typography.label.fontSize,
    fontWeight: '600',
    color: Colors.textSecondary,
    textTransform: 'uppercase',
    letterSpacing: 1,
  },
  statValue: {
    fontSize: Typography.mono.fontSize,
    fontWeight: '600',
    color: Colors.textPrimary,
    marginTop: Spacing.xs,
  },
});
