import { Text as RNText, TextProps, Dimensions, Platform } from 'react-native';
import { useColors } from '../../hooks/use-colors';

interface TerminalTextProps extends TextProps {
  children: React.ReactNode;
  variant?: 'primary' | 'muted' | 'cyan' | 'success' | 'warning' | 'error' | 'ticker' | 'matrix';
  size?: 'xs' | 'sm' | 'md' | 'lg' | 'xl';
  className?: string;
}

// On force le mode Desktop si on est sur le Web pour éviter l'effet "miniature" dans les iframes
const isDesktop = Platform.OS === 'web';

const sizeMap = {
  xs: isDesktop ? 14 : 10,
  sm: isDesktop ? 16 : 12,
  md: isDesktop ? 18 : 14,
  lg: isDesktop ? 24 : 16,
  xl: isDesktop ? 32 : 18,
};

export function TerminalText({ 
  children, 
  variant = 'primary', 
  size = 'md', 
  className = '',
  style,
  ...props 
}: TerminalTextProps) {
  const colors = useColors();

  const colorMap = {
    primary: colors.foreground,
    muted: colors.muted,
    cyan: colors.primary,
    success: colors.success,
    warning: colors.warning,
    error: colors.error,
    ticker: colors.primary,
    matrix: colors.muted,
  };

  const fontConfig = {
    family: (variant === 'ticker' || variant === 'matrix') ? 'JetBrainsMono_600SemiBold' : 'Inter_400Regular',
    weight: '400',
  };

  return (
    <RNText 
      className={className}
      style={[
        {
          color: colorMap[variant],
          fontFamily: fontConfig.family,
          fontSize: sizeMap[size],
          letterSpacing: (variant === 'ticker' || variant === 'matrix') ? 0.5 : 0,
          textTransform: variant === 'matrix' ? 'uppercase' : 'none',
        },
        style
      ]}
      {...props}
    >
      {children}
    </RNText>
  );
}
