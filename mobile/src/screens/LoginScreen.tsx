import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { useAuth } from '../auth/AuthContext';
import { GhostButton, PrimaryButton } from '../components/Buttons';
import { colors, spacing } from '../theme';

export function LoginScreen() {
  const { signInWithGoogle, signInAsDevUser, isSigningIn, error } = useAuth();

  return (
    <SafeAreaView style={styles.safeArea}>
      <View style={styles.content}>
        <Text style={styles.title}>Tamreena</Text>
        <Text style={styles.subtitle}>
          Your personalised training, nutrition, and progress — built around your body.
        </Text>

        {error ? <Text style={styles.error}>{error}</Text> : null}

        <PrimaryButton
          label={isSigningIn ? 'Signing in…' : 'Sign in with Google'}
          onPress={signInWithGoogle}
          disabled={isSigningIn}
        />

        {/* __DEV__ is a React Native global, false in any release build —
            this button can never render outside a development bundle. The
            backend endpoint it calls is ALSO disabled unless the server
            operator explicitly opted in (config.ALLOW_DEV_LOGIN), so it's
            safe even if someone ran a dev build against a real server. */}
        {__DEV__ ? (
          <GhostButton
            label="Continue as Test User (dev only)"
            onPress={signInAsDevUser}
            disabled={isSigningIn}
            style={{ marginTop: spacing.gapInner }}
          />
        ) : null}
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: colors.bgPrimary },
  content: { flex: 1, justifyContent: 'center', paddingHorizontal: spacing.screenPad },
  title: { fontSize: 32, fontWeight: '700', color: colors.textPrimary, textAlign: 'center', marginBottom: 12 },
  subtitle: { fontSize: 14, color: colors.textSecondary, textAlign: 'center', marginBottom: 32 },
  error: { color: colors.danger, fontSize: 13, textAlign: 'center', marginBottom: 16 },
});
