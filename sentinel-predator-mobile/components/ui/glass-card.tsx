import React from 'react';
import { View, ViewProps } from 'react-native';
import { useColors } from '../../hooks/use-colors';

interface GlassCardProps extends ViewProps {
  children: React.ReactNode;
  intensity?: 'light' | 'medium' | 'dark';
  borderOpacity?: number;
  className?: string;
}

export function GlassCard({ 
  children, 
  intensity = 'medium', 
  borderOpacity = 0.08,
  className = '',
  style,
  ...props 
}: GlassCardProps) {
  const colors = useColors();
  
  const bgOpacity = {
    light: 0.02,
    medium: 0.05,
    dark: 0.1,
  }[intensity];

  return (
    <View 
      className={`rounded-sm border glass-blur ${className}`}
      style={[
        {
          backgroundColor: `rgba(255, 255, 255, ${bgOpacity})`,
          borderColor: `rgba(255, 255, 255, ${borderOpacity})`,
          shadowColor: '#000',
          shadowOffset: { width: 0, height: 4 },
          shadowOpacity: 0.2,
          shadowRadius: 10,
        },
        style
      ]}
      {...props}
    >
      {children}
    </View>
  );
}
