import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { useAuth } from '../auth/AuthContext';
import { PrimaryButton } from '../components/Buttons';
import { colors, spacing } from '../theme';

export function LoginScreen() {
  const { signInWithGoogle, isSigningIn, error } = useAuth();

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
