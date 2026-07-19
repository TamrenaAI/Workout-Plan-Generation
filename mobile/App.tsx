import { NavigationContainer } from '@react-navigation/native';
import { StatusBar } from 'expo-status-bar';
import React from 'react';
import { ActivityIndicator, View } from 'react-native';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import { AuthProvider, useAuth } from './src/auth/AuthContext';
import { TabNavigator } from './src/navigation/TabNavigator';
import { LoginScreen } from './src/screens/LoginScreen';
import { colors } from './src/theme';

function Root() {
  const { user, isLoading } = useAuth();

  if (isLoading) {
    return (
      <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.bgPrimary }}>
        <ActivityIndicator color={colors.accentPrimary} />
      </View>
    );
  }

  return user ? <TabNavigator /> : <LoginScreen />;
}

export default function App() {
  return (
    <SafeAreaProvider>
      <AuthProvider>
        <NavigationContainer>
          <Root />
          <StatusBar style="dark" />
        </NavigationContainer>
      </AuthProvider>
    </SafeAreaProvider>
  );
}
