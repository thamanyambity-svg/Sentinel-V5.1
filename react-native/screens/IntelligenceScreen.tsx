// screens/IntelligenceScreen.tsx
import React from 'react';
import { View, Text, StyleSheet, ScrollView } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Colors, Typography, Spacing } from '../constants/Colors';
import Card from '../components/Card';

export default function IntelligenceScreen() {
  const insets = useSafeAreaInsets();

  return (
    <View style={[styles.container, { paddingTop: insets.top }]}>
      <View style={styles.header}>
        <Text style={styles.title}>🧠 Intelligence</Text>
      </View>

      <ScrollView style={styles.content}>
        <Card>
          <Text style={styles.label}>Résumé Exécutif</Text>
          <Text style={styles.text}>
            L'or (XAUUSD) montre une force technique claire avec un break au-dessus de la moyenne mobile 50j.
            Les indicateurs macroéconomiques soutiennent un biais haussier court terme.
          </Text>
        </Card>

        <Card>
          <Text style={styles.label}>📊 Analyse Technique</Text>
          <View style={styles.row}>
            <Text>Support</Text>
            <Text style={styles.mono}>2,360</Text>
          </View>
          <View style={styles.row}>
            <Text>Résistance</Text>
            <Text style={styles.mono}>2,400</Text>
          </View>
          <View style={styles.row}>
            <Text>RSI 14</Text>
            <Text style={styles.mono}>65 (Suracheté)</Text>
          </View>
        </Card>
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
  label: {
    fontSize: Typography.label.fontSize,
    fontWeight: '600',
    color: Colors.textSecondary,
    textTransform: 'uppercase',
    letterSpacing: 1,
    marginBottom: Spacing.md,
  },
  text: {
    color: Colors.textPrimary,
    fontSize: 13,
    lineHeight: 20,
  },
  row: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: Spacing.sm,
  },
  mono: {
    fontFamily: 'JetBrains Mono',
    fontWeight: '600',
    color: Colors.textPrimary,
  },
});
