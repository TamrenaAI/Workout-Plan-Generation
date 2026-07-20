import React from 'react';
import { StyleSheet, Text, TextInput, TextInputProps, View } from 'react-native';

import { colors, radii } from '../theme';

/** Mirrors the web app's .t-input/.t-label pattern. */
export function TextField({ label, style, ...rest }: { label: string } & TextInputProps) {
  return (
    <View style={styles.container}>
      <Text style={styles.label}>{label}</Text>
      <TextInput style={[styles.input, style]} placeholderTextColor={colors.textMuted} {...rest} />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { marginBottom: 24 },
  label: { fontSize: 13, color: colors.textMuted, marginBottom: 8, textTransform: 'uppercase', letterSpacing: 0.5, fontWeight: '600' },
  input: {
    height: 44,
    backgroundColor: colors.bgInput,
    borderWidth: 1,
    borderColor: colors.borderDefault,
    borderRadius: radii.button,
    paddingHorizontal: 14,
    color: colors.textPrimary,
    fontSize: 14,
  },
});
