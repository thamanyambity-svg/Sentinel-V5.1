// components/Card.tsx
import React from 'react';
import { View, StyleSheet, ViewStyle } from 'react-native';
import { Colors, Spacing } from '../constants/Colors';

interface CardProps {
  children: React.ReactNode;
  style?: ViewStyle;
  onPress?: () => void;
}

export default function Card({ children, style, onPress }: CardProps) {
  return (
    <View
      style={[
        styles.card,
        style,
        onPress && styles.cardTouchable,
      ]}
    >
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: Colors.cardBackground,
    borderWidth: 1,
    borderColor: Colors.borderColor,
    borderRadius: 12,
    padding: Spacing.md,
    marginHorizontal: Spacing.md,
    marginVertical: Spacing.sm,
  },
  cardTouchable: {
    opacity: 0.9,
  },
});
