import { Ionicons } from '@expo/vector-icons';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import React from 'react';
import { Alert, View } from 'react-native';

import { ChatButton } from '../components/ChatButton';
import { HomeScreen } from '../screens/HomeScreen';
import { NutritionScreen } from '../screens/NutritionScreen';
import { ProfileScreen } from '../screens/ProfileScreen';
import { ProgressScreen } from '../screens/ProgressScreen';
import { WorkoutScreen } from '../screens/WorkoutScreen';
import { colors } from '../theme';

const Tab = createBottomTabNavigator();

const ICONS: Record<string, keyof typeof Ionicons.glyphMap> = {
  Home: 'home',
  Workout: 'barbell',
  Nutrition: 'nutrition',
  Progress: 'trending-up',
  Profile: 'person',
};

export function TabNavigator() {
  return (
    <View style={{ flex: 1 }}>
      <Tab.Navigator
        screenOptions={({ route }) => ({
          headerShown: false,
          tabBarActiveTintColor: colors.accentPrimary,
          tabBarInactiveTintColor: colors.textMuted,
          tabBarStyle: { borderTopColor: colors.borderDefault, height: 76, paddingTop: 8, paddingBottom: 20 },
          tabBarLabelStyle: { fontSize: 10, fontWeight: '600' },
          tabBarIcon: ({ color, size }) => <Ionicons name={ICONS[route.name]} size={size} color={color} />,
        })}
      >
        <Tab.Screen name="Home" component={HomeScreen} />
        <Tab.Screen name="Workout" component={WorkoutScreen} />
        <Tab.Screen name="Nutrition" component={NutritionScreen} />
        <Tab.Screen name="Progress" component={ProgressScreen} />
        <Tab.Screen name="Profile" component={ProfileScreen} />
      </Tab.Navigator>

      {/* Overlays the tab bar, floating clear above it — see ChatButton.tsx */}
      <ChatButton onPress={() => Alert.alert('Chat', 'App-guidance assistant — not wired up yet.')} />
    </View>
  );
}
