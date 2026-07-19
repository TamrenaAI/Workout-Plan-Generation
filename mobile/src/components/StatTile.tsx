import React from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { colors, radii } from '../theme';

/** Mirrors the web app's .t-stat-tile — used 4-up for macro/body-composition grids. */
export function StatTile({ value, label }: { value: string; label: string }) {
  return (
    <View style={styles.tile}>
      <Text style={styles.value}>{value}</Text>
      <Text style={styles.label}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  tile: {
    flex: 1,
    backgroundColor: colors.bgCardAlt,
    borderWidth: 0.5,
    borderColor: colors.borderSubtle,
    borderRadius: radii.tile,
    paddingVertical: 12,
    paddingHorizontal: 8,
    alignItems: 'center',
  },
  value: { fontSize: 18, fontWeight: '700', color: colors.textPrimary },
  label: { fontSize: 10, color: colors.textMuted, marginTop: 2, textTransform: 'uppercase' },
});
