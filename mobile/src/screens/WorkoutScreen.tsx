import React, { useEffect, useState } from 'react';
import { ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { ApiError } from '../api/client';
import { fetchSessions, PlanSession } from '../api/sessions';
import { Card } from '../components/Card';
import { PrimaryButton } from '../components/Buttons';
import { colors, spacing } from '../theme';

const DAYS = [
  { label: 'Mon', focus: 'Push', today: false },
  { label: 'Tue', focus: 'Pull', today: true },
  { label: 'Wed', focus: 'Legs', today: false },
  { label: 'Thu', focus: 'Rest', today: false },
  { label: 'Fri', focus: 'Push', today: false },
];

// Still mock — there's no GET /sessions/{id}/plan endpoint yet to fetch a
// specific day's real prescribed exercises out of plan.md. The day strip
// and this list stay illustrative until that's built.
const EXERCISES = [
  { name: 'Pull-Up', sets: '4×8', rest: '2 min', rpe: 8 },
  { name: 'Barbell Row', sets: '4×10', rest: '90s', rpe: 7 },
  { name: 'Lat Pulldown', sets: '3×12', rest: '90s', rpe: 7 },
  { name: 'Face Pull', sets: '3×15', rest: '60s', rpe: 6 },
];

function formatDate(iso: string): string {
  return new Date(iso.replace(' ', 'T') + 'Z').toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

export function WorkoutScreen() {
  const [sessions, setSessions] = useState<PlanSession[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchSessions()
      .then(setSessions)
      .catch((err) => setError(err instanceof ApiError ? err.message : 'Could not load workout history.'));
  }, []);

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

        <Text style={styles.sectionTitle}>Workout History</Text>
        {error ? (
          <Card>
            <Text style={styles.error}>{error}</Text>
          </Card>
        ) : sessions && sessions.length > 0 ? (
          sessions.map((s) => (
            <Card key={s.session_id}>
              <View style={styles.rowBetween}>
                <Text style={styles.historyGoal}>{s.goal ?? 'Untitled plan'}</Text>
                <Text style={styles.historyDate}>{formatDate(s.created_at)}</Text>
              </View>
            </Card>
          ))
        ) : sessions ? (
          <Card>
            <Text style={styles.emptyText}>No past plans yet.</Text>
          </Card>
        ) : null}
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
  sectionTitle: { fontSize: 18, fontWeight: '700', color: colors.textPrimary, marginBottom: 12, marginTop: 8 },
  exerciseName: { fontSize: 16, fontWeight: '600', color: colors.textPrimary },
  exerciseDetail: { fontSize: 13, color: colors.textSecondary, marginTop: 4 },
  rowBetween: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  historyGoal: { fontSize: 14, fontWeight: '600', color: colors.textPrimary, textTransform: 'capitalize' },
  historyDate: { fontSize: 12, color: colors.textMuted },
  emptyText: { fontSize: 13, color: colors.textMuted },
  error: { fontSize: 13, color: colors.danger },
});
