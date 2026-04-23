// App.tsx - SENTINEL PREDATOR Main Application
import React from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import DashboardScreen from './screens/DashboardScreen';
import TerminalScreen from './screens/TerminalScreen';
import CreateOrderScreen from './screens/CreateOrderScreen';
import IntelligenceScreen from './screens/IntelligenceScreen';
import SettingsScreen from './screens/SettingsScreen';
import PositionDetailScreen from './screens/PositionDetailScreen';

import { Colors } from './constants/Colors';
import WSProvider from './context/WSContext';

const Stack = createNativeStackNavigator();
const Tab = createBottomTabNavigator();

const screenOptions = {
  headerShown: false,
  animationEnabled: true,
};

function MainTabs() {
  return (
    <Tab.Navigator
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: Colors.primary,
        tabBarInactiveTintColor: Colors.textSecondary,
        tabBarStyle: {
          backgroundColor: Colors.appBackground,
          borderTopColor: 'rgba(255, 255, 255, 0.05)',
          borderTopWidth: 1,
          paddingBottom: 8,
          paddingTop: 8,
        },
        tabBarLabelStyle: {
          fontSize: 10,
          fontFamily: 'Inter',
          fontWeight: '600',
          marginTop: 4,
        },
      }}
    >
      <Tab.Screen
        name="Dashboard"
        component={DashboardScreen}
        options={{
          tabBarLabel: 'Dashboard',
          tabBarIcon: ({ color }) => <Text style={{ fontSize: 20, color }}>📊</Text>,
        }}
      />
      <Tab.Screen
        name="Terminal"
        component={TerminalScreen}
        options={{
          tabBarLabel: 'Terminal',
          tabBarIcon: ({ color }) => <Text style={{ fontSize: 20, color }}>📡</Text>,
        }}
      />
      <Tab.Screen
        name="CreateOrder"
        component={CreateOrderScreen}
        options={{
          tabBarLabel: 'Ordre',
          tabBarIcon: ({ color }) => <Text style={{ fontSize: 20, color }}>➕</Text>,
        }}
      />
      <Tab.Screen
        name="Intelligence"
        component={IntelligenceScreen}
        options={{
          tabBarLabel: 'Intelligence',
          tabBarIcon: ({ color }) => <Text style={{ fontSize: 20, color }}>🧠</Text>,
        }}
      />
      <Tab.Screen
        name="Settings"
        component={SettingsScreen}
        options={{
          tabBarLabel: 'Paramètres',
          tabBarIcon: ({ color }) => <Text style={{ fontSize: 20, color }}>⚙️</Text>,
        }}
      />
    </Tab.Navigator>
  );
}

export default function App() {
  return (
    <SafeAreaProvider>
      <WSProvider>
        <NavigationContainer>
          <Stack.Navigator screenOptions={screenOptions}>
            <Stack.Screen
              name="MainTabs"
              component={MainTabs}
              options={screenOptions}
            />
            <Stack.Screen
              name="PositionDetail"
              component={PositionDetailScreen}
              options={{
                ...screenOptions,
                animationEnabled: true,
              }}
            />
          </Stack.Navigator>
        </NavigationContainer>
      </WSProvider>
    </SafeAreaProvider>
  );
}

import { Text } from 'react-native';
