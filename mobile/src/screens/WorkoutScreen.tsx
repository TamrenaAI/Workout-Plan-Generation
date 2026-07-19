import React from 'react';
import { ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Card } from '../components/Card';
import { GhostButton, PrimaryButton } from '../components/Buttons';
import { colors, spacing } from '../theme';

const DAYS = [
  { label: 'Mon', focus: 'Push', today: false },
  { label: 'Tue', focus: 'Pull', today: true },
  { label: 'Wed', focus: 'Legs', today: false },
  { label: 'Thu', focus: 'Rest', today: false },
  { label: 'Fri', focus: 'Push', today: false },
];

// Mock exercise list matching the approved mockup — real data comes from
// the session's plan.md via a future GET /sessions/{id}/plan endpoint.
const EXERCISES = [
  { name: 'Pull-Up', sets: '4×8', rest: '2 min', rpe: 8 },
  { name: 'Barbell Row', sets: '4×10', rest: '90s', rpe: 7 },
  { name: 'Lat Pulldown', sets: '3×12', rest: '90s', rpe: 7 },
  { name: 'Face Pull', sets: '3×15', rest: '60s', rpe: 6 },
];

export function WorkoutScreen() {
  return (
    <SafeAreaView style={styles.safeArea} edges={['top']}>
      <ScrollView contentContainerStyle={styles.content}>
        <Text style={styles.title}>Workout</Text>

        <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.dayStrip}>
          {DAYS.map((d) => (
            <View key={d.label} style={[styles.dayPill, d.today && styles.dayPillActive]}>
              <Text style={[styles.dayLabel, d.today && styles.dayLabelActive]}>{d.label}</Text>
              <Text style={[styles.dayFocus, d.today && styles.dayLabelActive]}>{d.focus}</Text>
            </View>
          ))}
        </ScrollView>

        <Text style={styles.sectionTitle}>Today's Session — Pull</Text>
        {EXERCISES.map((ex) => (
          <Card key={ex.name}>
            <Text style={styles.exerciseName}>{ex.name}</Text>
            <Text style={styles.exerciseDetail}>
              {ex.sets} · Rest {ex.rest} · RPE {ex.rpe}
            </Text>
            <PrimaryButton label="Start Set" style={{ marginTop: spacing.gapInner }} />
          </Card>
        ))}

        <GhostButton label="Workout History" style={{ marginTop: spacing.gapCards }} />
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: colors.bgPrimary },
  content: { padding: spacing.screenPad, paddingBottom: 120 },
  title: { fontSize: 24, fontWeight: '700', color: colors.textPrimary, marginBottom: 16 },
  dayStrip: { marginBottom: 20 },
  dayPill: {
    paddingVertical: 10,
    paddingHorizontal: 16,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: colors.borderDefault,
    backgroundColor: colors.bgInput,
    marginRight: 8,
    alignItems: 'center',
  },
  dayPillActive: { backgroundColor: colors.accentPrimary, borderColor: colors.accentPrimary },
  dayLabel: { fontSize: 12, fontWeight: '600', color: colors.textSecondary },
  dayFocus: { fontSize: 11, color: colors.textMuted, marginTop: 2 },
  dayLabelActive: { color: '#fff' },
  sectionTitle: { fontSize: 18, fontWeight: '700', color: colors.textPrimary, marginBottom: 12 },
  exerciseName: { fontSize: 16, fontWeight: '600', color: colors.textPrimary },
  exerciseDetail: { fontSize: 13, color: colors.textSecondary, marginTop: 4 },
});
