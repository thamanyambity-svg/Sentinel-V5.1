// screens/CreateOrderScreen.tsx
import React from 'react';
import { View, Text, StyleSheet, TextInput, TouchableOpacity, ScrollView } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Colors, Typography, Spacing } from '../constants/Colors';

export default function CreateOrderScreen() {
  const insets = useSafeAreaInsets();
  const [symbol, setSymbol] = React.useState('XAUUSD');
  const [type, setType] = React.useState<'BUY' | 'SELL'>('BUY');
  const [quantity, setQuantity] = React.useState('1.00');

  return (
    <View style={[styles.container, { paddingTop: insets.top }]}>
      <View style={styles.header}>
        <Text style={styles.title}>➕ Créer Ordre</Text>
      </View>

      <ScrollView style={styles.content}>
        <View style={styles.card}>
          <Text style={styles.label}>Symbole</Text>
          <TextInput
            style={styles.input}
            value={symbol}
            onChangeText={setSymbol}
            placeholder="Ex: XAUUSD"
            placeholderTextColor={Colors.textSecondary}
          />

          <Text style={[styles.label, { marginTop: Spacing.md }]}>Type</Text>
          <View style={styles.toggle}>
            <TouchableOpacity
              style={[styles.toggleBtn, type === 'BUY' && styles.toggleActive]}
              onPress={() => setType('BUY')}
            >
              <Text style={[styles.toggleText, type === 'BUY' && styles.toggleTextActive]}>
                ACHAT
              </Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[styles.toggleBtn, type === 'SELL' && styles.toggleActive]}
              onPress={() => setType('SELL')}
            >
              <Text style={[styles.toggleText, type === 'SELL' && styles.toggleTextActive]}>
                VENTE
              </Text>
            </TouchableOpacity>
          </View>

          <Text style={[styles.label, { marginTop: Spacing.md }]}>Quantité (lots)</Text>
          <TextInput
            style={styles.input}
            value={quantity}
            onChangeText={setQuantity}
            placeholder="0.50"
            placeholderTextColor={Colors.textSecondary}
            keyboardType="decimal-pad"
          />
        </View>

        <TouchableOpacity style={[styles.btn, styles.btnPrimary]}>
          <Text style={styles.btnText}>Confirmer Ordre</Text>
        </TouchableOpacity>
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
  content: {
    flex: 1,
    padding: Spacing.md,
  },
  card: {
    backgroundColor: Colors.cardBackground,
    borderRadius: 12,
    padding: Spacing.md,
    borderWidth: 1,
    borderColor: Colors.borderColor,
  },
  label: {
    fontSize: Typography.label.fontSize,
    fontWeight: '600',
    color: Colors.textSecondary,
    textTransform: 'uppercase',
    letterSpacing: 1,
  },
  input: {
    backgroundColor: 'rgba(139, 148, 158, 0.1)',
    borderRadius: 8,
    padding: Spacing.md,
    marginTop: Spacing.sm,
    color: Colors.textPrimary,
    fontFamily: 'JetBrains Mono',
    fontSize: 14,
    borderWidth: 1,
    borderColor: Colors.borderColor,
  },
  toggle: {
    flexDirection: 'row',
    marginTop: Spacing.sm,
    borderRadius: 8,
    overflow: 'hidden',
    backgroundColor: 'rgba(139, 148, 158, 0.1)',
  },
  toggleBtn: {
    flex: 1,
    padding: Spacing.md,
    alignItems: 'center',
  },
  toggleActive: {
    backgroundColor: 'rgba(8, 145, 178, 0.2)',
  },
  toggleText: {
    color: Colors.textSecondary,
    fontWeight: '600',
    fontSize: 12,
  },
  toggleTextActive: {
    color: Colors.primary,
  },
  btn: {
    padding: Spacing.md,
    borderRadius: 8,
    alignItems: 'center',
    marginTop: Spacing.lg,
  },
  btnPrimary: {
    backgroundColor: Colors.primary,
  },
  btnText: {
    color: 'white',
    fontWeight: '700',
    fontSize: 14,
    textTransform: 'uppercase',
    letterSpacing: 1,
  },
});
