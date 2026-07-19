import React from 'react';
import { StyleSheet, View, ViewProps } from 'react-native';

import { colors, radii, spacing } from '../theme';

/** Mirrors the web app's .t-card class (frontend/src/base.css). */
export function Card({ style, children, ...rest }: ViewProps) {
  return (
    <View style={[styles.card, style]} {...rest}>
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.bgCard,
    borderWidth: 1,
    borderColor: colors.borderDefault,
    borderRadius: radii.card,
    padding: spacing.cardPad,
    marginBottom: spacing.gapCards,
  },
});
