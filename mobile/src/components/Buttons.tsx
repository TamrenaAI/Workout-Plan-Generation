import React from 'react';
import { StyleSheet, Text, TouchableOpacity, TouchableOpacityProps } from 'react-native';

import { colors, radii } from '../theme';

type ButtonProps = TouchableOpacityProps & { label: string };

/** Mirrors the web app's .t-btn-primary class. */
export function PrimaryButton({ label, style, ...rest }: ButtonProps) {
  return (
    <TouchableOpacity style={[styles.primary, style]} activeOpacity={0.8} {...rest}>
      <Text style={styles.primaryText}>{label}</Text>
    </TouchableOpacity>
  );
}

/** Mirrors the web app's .t-btn-ghost class. */
export function GhostButton({ label, style, ...rest }: ButtonProps) {
  return (
    <TouchableOpacity style={[styles.ghost, style]} activeOpacity={0.7} {...rest}>
      <Text style={styles.ghostText}>{label}</Text>
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  primary: {
    height: 52,
    borderRadius: radii.button,
    backgroundColor: colors.accentPrimary,
    alignItems: 'center',
    justifyContent: 'center',
  },
  primaryText: { color: '#fff', fontSize: 15, fontWeight: '600' },
  ghost: {
    height: 48,
    borderRadius: radii.button,
    backgroundColor: colors.bgCardAlt,
    borderWidth: 1,
    borderColor: colors.borderDefault,
    alignItems: 'center',
    justifyContent: 'center',
  },
  ghostText: { color: colors.textPrimary, fontSize: 14, fontWeight: '500' },
});
