import React from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { colors, radii } from '../theme';

type Variant = 'default' | 'success' | 'warning' | 'danger';

const VARIANT_COLOR: Record<Variant, string> = {
  default: colors.textSecondary,
  success: colors.success,
  warning: colors.warning,
  danger: colors.danger,
};

/** Mirrors the web app's .t-badge class. */
export function Badge({ label, variant = 'default' }: { label: string; variant?: Variant }) {
  const tint = VARIANT_COLOR[variant];
  return (
    <View style={[styles.badge, { borderColor: variant === 'default' ? colors.borderDefault : tint }]}>
      <Text style={[styles.text, { color: tint }]}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  badge: {
    flexDirection: 'row',
    alignSelf: 'flex-start',
    alignItems: 'center',
    paddingHorizontal: 12,
    paddingVertical: 4,
    borderRadius: radii.badge,
    borderWidth: 1,
    backgroundColor: colors.bgCardAlt,
  },
  text: {
    fontSize: 11,
    fontWeight: '700',
    letterSpacing: 0.5,
    textTransform: 'uppercase',
  },
});
