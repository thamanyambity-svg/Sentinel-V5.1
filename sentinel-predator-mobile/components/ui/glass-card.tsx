import React from 'react';
import { View, ViewProps } from 'react-native';
import { useColors } from '../../hooks/use-colors';

 interface GlassCardProps extends ViewProps {
   children: React.ReactNode;
   intensity?: 'light' | 'medium' | 'dark';
   borderOpacity?: number;
   className?: string;
   glowColor?: string;
   glowIntensity?: number;
 }
 
 export function GlassCard({ 
   children, 
   intensity = 'medium', 
   borderOpacity = 0.08,
   className = '',
   glowColor,
   glowIntensity = 0.4,
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
           borderColor: glowColor ? glowColor : `rgba(255, 255, 255, ${borderOpacity})`,
           shadowColor: glowColor || '#000',
           shadowOffset: { width: 0, height: 4 },
           shadowOpacity: glowColor ? glowIntensity : 0.2,
           shadowRadius: glowColor ? 15 : 10,
           borderWidth: glowColor ? 1.5 : 1,
         },
         style
       ]}
       {...props}
     >
       {children}
     </View>
   );
 }
