import { Text as RNText, TextProps } from 'react-native';
import { useColors } from '../../hooks/use-colors';

interface TerminalTextProps extends TextProps {
  children: React.ReactNode;
  variant?: 'primary' | 'muted' | 'cyan' | 'success' | 'warning' | 'error' | 'ticker' | 'matrix';
  size?: 'xs' | 'sm' | 'md' | 'lg' | 'xl';
  className?: string;
}

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

  const sizeMap = {
    xs: 10,
    sm: 12,
    md: 14,
    lg: 16,
    xl: 18,
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
