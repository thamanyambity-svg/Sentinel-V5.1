// screens/DashboardScreen.tsx
import React, { useEffect } from 'react';
import {
  View,
  ScrollView,
  Text,
  StyleSheet,
  TouchableOpacity,
  RefreshControl,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { NativeStackScreenProps } from '@react-navigation/native-stack';

import { useWS } from '../context/WSContext';
import { Colors, Typography, Spacing } from '../constants/Colors';
import Card from '../components/Card';
import Header from '../components/Header';
import VerdictCard from '../components/VerdictCard';
import PositionItem from '../components/PositionItem';

type RootStackParamList = {
  MainTabs: undefined;
  PositionDetail: { positionId: string };
};

type Props = NativeStackScreenProps<RootStackParamList, 'MainTabs'>;

export default function DashboardScreen({ navigation }: Props) {
  const insets = useSafeAreaInsets();
  const { isConnected, marketData, error } = useWS();
  const [refreshing, setRefreshing] = React.useState(false);

  const onRefresh = React.useCallback(() => {
    setRefreshing(true);
    setTimeout(() => setRefreshing(false), 1000);
  }, []);

  // Mock data if WS unavailable
  const account = marketData?.account || {
    balance: 455.11,
    equity: 467.56,
    marginLevel: 45,
    currency: 'USD',
  };

  const positions = marketData?.positions || [
    {
      id: '1',
      symbol: 'XAUUSD',
      quantity: 1.0,
      entryPrice: 2342.15,
      currentPrice: 2385.50,
      pnl: 45.23,
      pnlPercent: 1.93,
      type: 'LONG',
    },
    {
      id: '2',
      symbol: 'EURUSD',
      quantity: 0.5,
      entryPrice: 1.0975,
      currentPrice: 1.0925,
      pnl: -12.10,
      pnlPercent: -0.42,
      type: 'LONG',
    },
  ];

  const mlSignal = marketData?.mlSignal || {
    sentiment: 'BULLISH',
    confidence: 75,
    symbol: 'XAUUSD',
    reasoning: 'Strong technicals + favorable fundamentals',
    timestamp: new Date().toISOString(),
  };

  return (
    <View style={[styles.container, { paddingTop: insets.top }]}>
      <Header
        title="SENTINEL PREDATOR"
        subtitle="Dashboard"
        status={isConnected ? 'connected' : 'offline'}
        account={account}
      />

      <ScrollView
        style={styles.content}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
        }
      >
        {/* Verdict Card */}
        <VerdictCard signal={mlSignal} />

        {/* Risk Metrics */}
        <View style={styles.metricsGrid}>
          <Card style={styles.metricCard}>
            <Text style={styles.label}>Market Risk</Text>
            <Text style={styles.metricValue}>34</Text>
            <View style={styles.riskBar}>
              <View style={[styles.riskFill, { width: '34%' }]} />
            </View>
          </Card>

          <Card style={styles.metricCard}>
            <Text style={styles.label}>VIX Fear</Text>
            <Text style={styles.metricValue}>18.5</Text>
            <Text style={[styles.label, { color: Colors.bullish, marginTop: Spacing.sm }]}>
              LOW
            </Text>
          </Card>
        </View>

        {/* Bot Status */}
        <Card style={styles.card}>
          <View style={styles.cardHeader}>
            <Text style={styles.label}>🤖 Session Bot</Text>
            <Text style={[styles.mono, { color: Colors.bullish }]}>ACTIF</Text>
          </View>
          <View style={styles.cardRow}>
            <Text style={styles.label}>Prochain Cycle</Text>
            <Text style={styles.mono}>00:23:45</Text>
          </View>
          <View style={styles.cardRow}>
            <Text style={styles.label}>Trades Aujourd'hui</Text>
            <Text style={styles.mono}>3</Text>
          </View>
        </Card>

        {/* Positions */}
        <Text style={[styles.label, { paddingHorizontal: Spacing.md, marginTop: Spacing.lg }]}>
          Positions Ouvertes ({positions.length})
        </Text>

        {positions.map((position) => (
          <TouchableOpacity
            key={position.id}
            onPress={() => navigation.navigate('PositionDetail', { positionId: position.id })}
          >
            <PositionItem position={position} />
          </TouchableOpacity>
        ))}

        {/* Orders */}
        <Text style={[styles.label, { paddingHorizontal: Spacing.md, marginTop: Spacing.lg }]}>
          Ordres Actifs (1)
        </Text>
        <Card style={styles.card}>
          <View style={styles.cardRow}>
            <Text>Buy Limit GBPUSD</Text>
            <Text style={styles.mono}>1.2750</Text>
          </View>
          <View style={styles.cardRow}>
            <Text style={styles.label}>Quantité</Text>
            <Text style={styles.mono}>0.50 lot</Text>
          </View>
        </Card>

        {/* Status */}
        {error && (
          <View style={styles.errorBanner}>
            <Text style={styles.errorText}>⚠️ {error}</Text>
          </View>
        )}

        <View style={{ height: Spacing.lg }} />
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.appBackground,
  },
  content: {
    flex: 1,
    paddingBottom: Spacing.md,
  },
  metricsGrid: {
    flexDirection: 'row',
    paddingHorizontal: Spacing.md,
    gap: Spacing.md,
    marginBottom: Spacing.md,
  },
  metricCard: {
    flex: 1,
  },
  card: {
    marginHorizontal: Spacing.md,
    marginVertical: Spacing.sm,
  },
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: Spacing.md,
  },
  cardRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: Spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: Colors.borderColor,
  },
  label: {
    fontSize: Typography.label.fontSize,
    fontWeight: Typography.label.fontWeight,
    color: Colors.textSecondary,
    textTransform: 'uppercase',
    letterSpacing: 1,
  },
  mono: {
    fontSize: Typography.mono.fontSize,
    fontWeight: Typography.mono.fontWeight,
    color: Colors.textPrimary,
    fontFamily: 'JetBrains Mono',
  },
  metricValue: {
    fontSize: 28,
    fontWeight: '700',
    color: Colors.textPrimary,
    marginVertical: Spacing.sm,
  },
  riskBar: {
    height: 2,
    backgroundColor: Colors.borderColor,
    borderRadius: 1,
    overflow: 'hidden',
    marginTop: Spacing.sm,
  },
  riskFill: {
    height: '100%',
    backgroundColor: Colors.neutral,
  },
  errorBanner: {
    marginHorizontal: Spacing.md,
    marginVertical: Spacing.md,
    padding: Spacing.md,
    backgroundColor: 'rgba(239, 68, 68, 0.1)',
    borderRadius: 8,
    borderLeftWidth: 3,
    borderLeftColor: Colors.bearish,
  },
  errorText: {
    color: Colors.bearish,
    fontSize: 12,
    fontWeight: '500',
  },
});
