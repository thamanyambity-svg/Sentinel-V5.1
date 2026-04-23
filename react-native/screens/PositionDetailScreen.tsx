// screens/PositionDetailScreen.tsx
import React from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { NativeStackScreenProps } from '@react-navigation/native-stack';
import { Colors, Typography, Spacing } from '../constants/Colors';
import Card from '../components/Card';

type RootStackParamList = {
  PositionDetail: { positionId: string };
};

type Props = NativeStackScreenProps<RootStackParamList, 'PositionDetail'>;

export default function PositionDetailScreen({ navigation, route }: Props) {
  const insets = useSafeAreaInsets();
  const position = {
    symbol: 'XAUUSD',
    price: 2385.50,
    pnl: 45.23,
    entryPrice: 2342.15,
    quantity: 1.0,
  };

  return (
    <View style={[styles.container, { paddingTop: insets.top }]}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => navigation.goBack()}>
          <Text style={styles.backBtn}>← Retour</Text>
        </TouchableOpacity>
        <Text style={styles.title}>{position.symbol}</Text>
        <Text style={[styles.pnl, { color: Colors.bullish }]}>+${position.pnl.toFixed(2)}</Text>
      </View>

      <ScrollView style={styles.content}>
        <Card>
          <Text style={styles.label}>Prix Actuel</Text>
          <Text style={styles.value}>{position.price.toFixed(2)}</Text>

          <Text style={[styles.label, { marginTop: Spacing.md }]}>Prix d'Entrée</Text>
          <Text style={styles.value}>{position.entryPrice.toFixed(2)}</Text>

          <Text style={[styles.label, { marginTop: Spacing.md }]}>Quantité</Text>
          <Text style={styles.value}>{position.quantity.toFixed(2)} lot</Text>

          <Text style={[styles.label, { marginTop: Spacing.md }]}>P&L Réalisé</Text>
          <Text style={[styles.value, { color: Colors.bullish }]}>+${position.pnl.toFixed(2)}</Text>
        </Card>

        <View style={styles.btnGroup}>
          <TouchableOpacity style={[styles.btn, styles.btnDanger]}>
            <Text style={styles.btnText}>Vendre</Text>
          </TouchableOpacity>
          <TouchableOpacity style={[styles.btn, styles.btnSecondary]}>
            <Text style={styles.btnText}>Ajouter</Text>
          </TouchableOpacity>
        </View>
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
  backBtn: {
    color: Colors.textSecondary,
    marginBottom: Spacing.sm,
  },
  title: {
    fontSize: Typography.title.fontSize,
    fontWeight: '700',
    color: Colors.textPrimary,
    marginBottom: Spacing.sm,
  },
  pnl: {
    fontSize: Typography.mono.fontSize,
    fontWeight: '700',
  },
  content: {
    flex: 1,
    padding: Spacing.md,
  },
  label: {
    fontSize: Typography.label.fontSize,
    fontWeight: '600',
    color: Colors.textSecondary,
    textTransform: 'uppercase',
    letterSpacing: 1,
  },
  value: {
    fontSize: 18,
    fontWeight: '700',
    color: Colors.textPrimary,
    marginTop: Spacing.sm,
  },
  btnGroup: {
    flexDirection: 'row',
    gap: Spacing.md,
    marginTop: Spacing.lg,
  },
  btn: {
    flex: 1,
    padding: Spacing.md,
    borderRadius: 8,
    alignItems: 'center',
  },
  btnDanger: {
    backgroundColor: 'rgba(239, 68, 68, 0.2)',
  },
  btnSecondary: {
    backgroundColor: 'rgba(139, 148, 158, 0.1)',
  },
  btnText: {
    fontWeight: '700',
    fontSize: 14,
    textTransform: 'uppercase',
    letterSpacing: 1,
    color: Colors.textPrimary,
  },
});
