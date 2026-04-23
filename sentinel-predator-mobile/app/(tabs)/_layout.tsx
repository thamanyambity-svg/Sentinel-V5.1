import { Tabs } from 'expo-router';
import { useColors } from '../../hooks/use-colors';
import { IconSymbol } from '../../components/ui/icon-symbol';

export default function TabLayout() {
  const colors = useColors();

  return (
    <Tabs
      screenOptions={{
        tabBarActiveTintColor: colors.primary,
        tabBarInactiveTintColor: colors.muted,
        tabBarLabelStyle: {
          fontFamily: 'Inter_600SemiBold',
          fontSize: 8,
          textTransform: 'uppercase',
          letterSpacing: 1,
        },
        tabBarStyle: {
          backgroundColor: colors.background,
          borderTopColor: colors.border,
          borderTopWidth: 1,
          height: 60,
          paddingBottom: 8,
        },
        headerShown: false,
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: 'Dashboard',
          tabBarIcon: ({ color }) => <IconSymbol name="house.fill" color={color} />,
        }}
      />
      <Tabs.Screen
        name="terminal"
        options={{
          title: 'Scanner',
          tabBarIcon: ({ color }) => <IconSymbol name="terminal.fill" color={color} />,
        }}
      />
      <Tabs.Screen
        name="trade"
        options={{
          title: 'Trade',
          tabBarIcon: ({ color }) => <IconSymbol name="chart.bar.fill" color={color} />,
        }}
      />
      <Tabs.Screen
        name="intelligence"
        options={{
          title: 'Intel',
          tabBarIcon: ({ color }) => <IconSymbol name="brain.fill" color={color} />,
        }}
      />
      <Tabs.Screen
        name="news"
        options={{
          title: 'Radar',
          tabBarIcon: ({ color }) => <IconSymbol name="globe.americas.fill" color={color} />,
        }}
      />
      <Tabs.Screen
        name="settings"
        options={{
          href: null, // Hide from tab bar, will use header icon
        }}
      />
    </Tabs>
  );
}
