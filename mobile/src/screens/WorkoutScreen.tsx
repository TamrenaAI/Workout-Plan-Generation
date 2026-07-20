import React, { useEffect, useMemo, useState } from 'react';
import { ActivityIndicator, Alert, ScrollView, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { ApiError } from '../api/client';
import { fetchSessions, PlanSession } from '../api/sessions';
import { Badge } from '../components/Badge';
import { Card } from '../components/Card';
import { GhostButton, PrimaryButton } from '../components/Buttons';
import { useLatestPlan } from '../hooks/useLatestPlan';
import { findColumn, PlanSection } from '../lib/parsePlan';
import { colors, spacing } from '../theme';
import { FeedbackExercise, WorkoutFeedbackScreen } from './WorkoutFeedbackScreen';

function formatDate(iso: string): string {
  return new Date(iso.replace(' ', 'T') + 'Z').toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

function dayShortLabel(section: PlanSection): string {
  // "Day 1 — Push: Chest Focus" -> "Push" (falls back to "Day N" if the
  // heading doesn't follow the usual "Day N — Focus: ..." shape).
  const match = section.title.match(/^Day\s+\d+\s*[—-]\s*([^:]+)/i);
  return match ? match[1].trim() : `Day ${section.dayNumber}`;
}

function exercisesFromDay(section: PlanSection) {
  const table = section.blocks.find((b) => b.type === 'table');
  if (!table || table.type !== 'table') return [];

  const nameIdx = findColumn(table.header, /exercise/i);
  const setsIdx = findColumn(table.header, /sets/i);
  const restIdx = findColumn(table.header, /rest/i);
  const rpeIdx = findColumn(table.header, /rpe/i);

  return table.rows.map((row, i) => ({
    key: `${section.dayNumber}-${i}`,
    name: nameIdx >= 0 ? row[nameIdx] : row[1] ?? 'Exercise',
    sets: setsIdx >= 0 ? row[setsIdx] : '—',
    rest: restIdx >= 0 ? row[restIdx] : '—',
    rpe: rpeIdx >= 0 ? row[rpeIdx] : '—',
  }));
}

export function WorkoutScreen() {
  const { isLoading, error, session, status, days, reload } = useLatestPlan();
  const [selectedDay, setSelectedDay] = useState<number | null>(null);
  const [view, setView] = useState<'list' | 'feedback'>('list');
  const [confirmation, setConfirmation] = useState<{ summary: string } | null>(null);

  useEffect(() => {
    if (days.length > 0 && selectedDay === null) {
      setSelectedDay(days[0].dayNumber);
    }
  }, [days, selectedDay]);

  const activeSection = days.find((d) => d.dayNumber === selectedDay) ?? days[0];
  const exercises = useMemo(() => (activeSection ? exercisesFromDay(activeSection) : []), [activeSection]);

  const [sessions, setSessions] = useState<PlanSession[] | null>(null);
  const [historyError, setHistoryError] = useState<string | null>(null);

  useEffect(() => {
    fetchSessions()
      .then(setSessions)
      .catch((err) => setHistoryError(err instanceof ApiError ? err.message : 'Could not load workout history.'));
  }, []);

  function handleFeedbackDone(result: { adjustmentTriggered: boolean; summary: string | null }) {
    setView('list');
    reload();
    if (result.adjustmentTriggered && result.summary) {
      setConfirmation({ summary: result.summary });
    } else {
      Alert.alert('Feedback saved');
    }
  }

  if (view === 'feedback' && activeSection) {
    const feedbackExercises: FeedbackExercise[] = exercises.map((ex) => ({ name: ex.name, sets: ex.sets }));
    return (
      <WorkoutFeedbackScreen
        sessionId={session?.session_id ?? ''}
        dayLabel={activeSection.title}
        exercises={feedbackExercises}
        onBack={() => setView('list')}
        onDone={handleFeedbackDone}
      />
    );
  }

  return (
    <SafeAreaView style={styles.safeArea} edges={['top']}>
      <ScrollView contentContainerStyle={styles.content}>
        <Text style={styles.title}>Workout</Text>

        {confirmation ? (
          <Card>
            <Badge label="Plan updated" variant="success" />
            <Text style={styles.confirmationBody}>{confirmation.summary}</Text>
            <GhostButton label="Got it" onPress={() => setConfirmation(null)} style={{ marginTop: spacing.gapInner }} />
          </Card>
        ) : null}

        {isLoading ? (
          <ActivityIndicator color={colors.accentPrimary} />
        ) : error ? (
          <Card>
            <Text style={styles.error}>{error}</Text>
          </Card>
        ) : status === 'pending' ? (
          <Card>
            <Text style={styles.emptyText}>Your plan is still being generated…</Text>
          </Card>
        ) : days.length === 0 ? (
          <Card>
            <Text style={styles.emptyText}>No plan yet — generate one to see your training days here.</Text>
          </Card>
        ) : (
          <>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.dayStrip}>
              {days.map((d) => {
                const active = d.dayNumber === activeSection?.dayNumber;
                return (
                  <TouchableOpacity
                    key={d.dayNumber}
                    style={[styles.dayPill, active && styles.dayPillActive]}
                    activeOpacity={0.7}
                    onPress={() => setSelectedDay(d.dayNumber)}
                  >
                    <Text style={[styles.dayLabel, active && styles.dayLabelActive]}>Day {d.dayNumber}</Text>
                    <Text style={[styles.dayFocus, active && styles.dayLabelActive]}>{dayShortLabel(d)}</Text>
                  </TouchableOpacity>
                );
              })}
            </ScrollView>

            <Text style={styles.sectionTitle}>{activeSection?.title ?? 'Session'}</Text>
            {exercises.length > 0 ? (
              exercises.map((ex) => (
                <Card key={ex.key}>
                  <Text style={styles.exerciseName}>{ex.name}</Text>
                  <Text style={styles.exerciseDetail}>
                    {ex.sets} · Rest {ex.rest} · RPE {ex.rpe}
                  </Text>
                  <PrimaryButton label="Start Set" style={{ marginTop: spacing.gapInner }} />
                </Card>
              ))
            ) : (
              <Card>
                <Text style={styles.emptyText}>No exercises found for this day.</Text>
              </Card>
            )}
            {exercises.length > 0 ? (
              <PrimaryButton label="Finish Workout" onPress={() => setView('feedback')} style={{ marginTop: spacing.gapCards, marginBottom: spacing.gapCards }} />
            ) : null}
          </>
        )}

        <Text style={styles.sectionTitle}>Workout History</Text>
        {historyError ? (
          <Card>
            <Text style={styles.error}>{historyError}</Text>
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
  confirmationBody: { fontSize: 13, lineHeight: 1.55 * 13, color: colors.textPrimary, marginTop: 10 },
});
