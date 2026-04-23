// screens/SettingsScreen.tsx
import React from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Colors, Typography, Spacing } from '../constants/Colors';
import Card from '../components/Card';

export default function SettingsScreen() {
  const insets = useSafeAreaInsets();

  return (
    <View style={[styles.container, { paddingTop: insets.top }]}>
      <View style={styles.header}>
        <Text style={styles.title}>⚙️ Paramètres</Text>
      </View>

      <ScrollView style={styles.content}>
        <Text style={[styles.sectionLabel, { marginTop: Spacing.md }]}>Compte</Text>
        <Card>
          <View style={styles.row}>
            <Text>Utilisateur</Text>
            <Text style={styles.mono}>trader@sentinel.pro</Text>
          </View>
          <View style={styles.row}>
            <Text>Authentification 2FA</Text>
            <Text style={[styles.mono, { color: Colors.bullish }]}>✓ Activé</Text>
          </View>
        </Card>

        <Text style={styles.sectionLabel}>Préférences</Text>
        <Card>
          <View style={styles.row}>
            <Text>Devise</Text>
            <Text style={styles.mono}>USD</Text>
          </View>
          <View style={styles.row}>
            <Text>Risque Maximum</Text>
            <Text style={styles.mono}>2% par trade</Text>
          </View>
          <View style={styles.row}>
            <Text>Levier Maximum</Text>
            <Text style={styles.mono}>30:1</Text>
          </View>
        </Card>

        <Text style={styles.sectionLabel}>À Propos</Text>
        <Card>
          <View style={styles.row}>
            <Text>Version</Text>
            <Text style={styles.mono}>1.0.0</Text>
          </View>
          <View style={styles.row}>
            <Text>Build</Text>
            <Text style={styles.mono}>2024.04.21</Text>
          </View>
        </Card>

        <TouchableOpacity style={[styles.btn, styles.btnDanger]}>
          <Text style={styles.btnText}>Déconnexion</Text>
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
  sectionLabel: {
    fontSize: Typography.label.fontSize,
    fontWeight: '600',
    color: Colors.textSecondary,
    textTransform: 'uppercase',
    letterSpacing: 1,
    marginBottom: Spacing.md,
  },
  row: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: Spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: Colors.borderColor,
  },
  mono: {
    fontFamily: 'JetBrains Mono',
    fontWeight: '600',
    fontSize: 12,
    color: Colors.textPrimary,
  },
  btn: {
    padding: Spacing.md,
    borderRadius: 8,
    alignItems: 'center',
    marginTop: Spacing.lg,
  },
  btnDanger: {
    backgroundColor: 'rgba(239, 68, 68, 0.2)',
  },
  btnText: {
    fontWeight: '700',
    fontSize: 14,
    textTransform: 'uppercase',
    letterSpacing: 1,
    color: Colors.textPrimary,
  },
});
