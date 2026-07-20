import React from 'react';
import { StyleSheet, Text, TouchableOpacity, View } from 'react-native';

import { colors, radii } from '../theme';

type Variant = 'accent' | 'danger';

/** Mirrors the web app's .pill-group/.pill pattern. Single-select — value
 * is one of `options[].value`, or null if nothing's picked yet.
 * `variant="danger"` renders the active pill in the app's danger color
 * instead of the default accent blue (used for the pain toggle — see
 * WorkoutFeedbackScreen.tsx). Every existing call site omits `variant`
 * and is unaffected. */
export function PillSelect<T extends string>({
  label,
  options,
  value,
  onChange,
  variant = 'accent',
}: {
  label: string;
  options: { label: string; value: T }[];
  value: T | null;
  onChange: (value: T) => void;
  variant?: Variant;
}) {
  const activePillStyle = variant === 'danger' ? styles.pillActiveDanger : styles.pillActive;
  const activeTextStyle = variant === 'danger' ? styles.pillTextActiveDanger : styles.pillTextActive;

  return (
    <View style={styles.container}>
      <Text style={styles.label}>{label}</Text>
      <View style={styles.group}>
        {options.map((opt) => {
          const active = opt.value === value;
          return (
            <TouchableOpacity
              key={opt.value}
              style={[styles.pill, active && activePillStyle]}
              activeOpacity={0.7}
              onPress={() => onChange(opt.value)}
            >
              <Text style={[styles.pillText, active && activeTextStyle]}>{opt.label}</Text>
            </TouchableOpacity>
          );
        })}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { marginBottom: 24 },
  label: { fontSize: 13, color: colors.textMuted, marginBottom: 8, textTransform: 'uppercase', letterSpacing: 0.5, fontWeight: '600' },
  group: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  pill: {
    paddingVertical: 8,
    paddingHorizontal: 16,
    borderRadius: radii.badge,
    borderWidth: 1,
    borderColor: colors.borderDefault,
    backgroundColor: colors.bgInput,
  },
  pillActive: { borderColor: colors.accentPrimary, backgroundColor: colors.accentTint },
  pillActiveDanger: { borderColor: colors.danger, backgroundColor: colors.bgInput },
  pillText: { fontSize: 13, fontWeight: '500', color: colors.textSecondary },
  pillTextActive: { color: colors.accentPrimary, fontWeight: '600' },
  pillTextActiveDanger: { color: colors.danger, fontWeight: '700' },
});
