// tailwind.config.js
/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./app/**/*.{js,jsx,ts,tsx}", "./components/**/*.{js,jsx,ts,tsx}"],
  presets: [require("nativewind/preset")],
  theme: {
    extend: {
      colors: {
        primary: "hsl(var(--primary))",
        background: "hsl(var(--background))",
        surface: "hsl(var(--card))",
        foreground: "hsl(var(--foreground))",
        muted: "hsl(var(--muted-foreground))",
        border: "hsl(var(--border))",
        success: "hsl(var(--success))",
        warning: "hsl(var(--warning))",
        error: "hsl(var(--error))",
      },
      fontFamily: {
        // Map to both Expo font names and System/Web CSS names
        mono: ["JetBrainsMono_600SemiBold", "JetBrains Mono", "monospace"],
        sans: ["Inter_400Regular", "Inter", "sans-serif"],
        "sans-bold": ["Inter_700Bold", "Inter", "sans-serif"],
        "sans-black": ["Inter_900Black", "Inter", "sans-serif"],
      },
      animation: {
        'pulse-glow': 'pulse-glow 2s cubic-bezier(0.4, 0, 0.6, 1) infinite',
      },
      keyframes: {
        'pulse-glow': {
          '0%, 100%': { opacity: 1, transform: 'scale(1)' },
          '50%': { opacity: 0.7, transform: 'scale(1.02)' },
        },
      },
    },
  },
  plugins: [],
};
