import { NavigationContainer } from '@react-navigation/native';
import { StatusBar } from 'expo-status-bar';
import React, { useEffect, useState } from 'react';
import { ActivityIndicator, View } from 'react-native';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import { fetchSessions } from './src/api/sessions';
import { AuthProvider, useAuth } from './src/auth/AuthContext';
import { TabNavigator } from './src/navigation/TabNavigator';
import { OnboardingFlow } from './src/onboarding/OnboardingFlow';
import { LoginScreen } from './src/screens/LoginScreen';
import { colors } from './src/theme';

function LoadingScreen() {
  return (
    <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.bgPrimary }}>
      <ActivityIndicator color={colors.accentPrimary} />
    </View>
  );
}

function Root() {
  const { user, isLoading } = useAuth();
  const [checkingSessions, setCheckingSessions] = useState(true);
  const [needsOnboarding, setNeedsOnboarding] = useState(false);

  useEffect(() => {
    if (!user) return;
    let cancelled = false;

    fetchSessions()
      .then((sessions) => {
        if (!cancelled) setNeedsOnboarding(sessions.length === 0);
      })
      .catch(() => {
        // Fail open to the tab bar rather than trap a signed-in user in
        // onboarding because of a transient network error.
        if (!cancelled) setNeedsOnboarding(false);
      })
      .finally(() => {
        if (!cancelled) setCheckingSessions(false);
      });

    return () => {
      cancelled = true;
    };
  }, [user]);

  if (isLoading) return <LoadingScreen />;
  if (!user) return <LoginScreen />;
  if (checkingSessions) return <LoadingScreen />;
  if (needsOnboarding) return <OnboardingFlow onComplete={() => setNeedsOnboarding(false)} />;
  return <TabNavigator />;
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
