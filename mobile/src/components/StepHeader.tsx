import React from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { colors } from '../theme';

/** Mirrors the web app's stepHeader() (frontend/src/pages/intake.js). */
export function StepHeader({ step, total, title, subtitle }: { step: number; total: number; title: string; subtitle?: string }) {
  return (
    <View style={styles.container}>
      <Text style={styles.eyebrow}>
        Step {step} of {total}
        {subtitle ? ` · ${subtitle}` : ''}
      </Text>
      <Text style={styles.title}>{title}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { marginBottom: 32 },
  eyebrow: { fontSize: 12, color: colors.accentPrimary, textTransform: 'uppercase', letterSpacing: 1, marginBottom: 4, fontWeight: '600' },
  title: { fontSize: 26, fontWeight: '700', color: colors.textPrimary },
});
