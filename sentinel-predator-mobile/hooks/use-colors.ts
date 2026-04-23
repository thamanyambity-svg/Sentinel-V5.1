import { useColorScheme } from 'react-native';

export const colors = {
  primary: "#0891b2",    // Cyan
  background: "#0d1117", // Deep Black
  surface: "#161b22",    // Dark Gray
  foreground: "#e2e8f0", // Off White
  muted: "#8b949e",      // Gray
  border: "#30363d",     // Border Gray
  success: "#10b981",    // Green
  warning: "#f59e0b",    // Amber
  error: "#ef4444",      // Red
};

export function useColors() {
  // For now, we use a single dark theme as per the institucional design
  return colors;
}
