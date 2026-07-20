import React, { useState } from 'react';
import { ActivityIndicator, ScrollView, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { ApiError } from '../api/client';
import { Difficulty, ExerciseFeedbackInput, submitWorkoutFeedback } from '../api/workouts';
import { Card } from '../components/Card';
import { PillSelect } from '../components/PillSelect';
import { GhostButton, PrimaryButton } from '../components/Buttons';
import { TextField } from '../components/TextField';
import { colors, spacing } from '../theme';

export interface FeedbackExercise {
  name: string;
  sets: string;
}

export interface WorkoutFeedbackScreenProps {
  sessionId: string;
  dayLabel: string;
  exercises: FeedbackExercise[];
  onBack: () => void;
  onDone: (result: { adjustmentTriggered: boolean; summary: string | null }) => void;
}

interface RowState {
  difficulty: Difficulty;
  pain: boolean;
  note: string;
  completed: boolean;
}

const DIFFICULTY_OPTIONS: { label: string; value: Difficulty }[] = [
  { label: 'Too Easy', value: 'too_easy' },
  { label: 'Just Right', value: 'just_right' },
  { label: 'Too Hard', value: 'too_hard' },
];

const PAIN_OPTIONS: { label: string; value: 'no' | 'yes' }[] = [
  { label: 'No pain', value: 'no' },
  { label: 'Painful', value: 'yes' },
];

const DEFAULT_ROW: RowState = { difficulty: 'just_right', pain: false, note: '', completed: true };

/**
 * Dedicated screen for post-workout feedback — deliberately NOT inline on
 * WorkoutScreen (see docs/superpowers/specs/2026-07-20-post-workout-feedback-mobile-design.md's
 * "Flow" section for why an earlier per-exercise-inline version was rejected).
 * Pure props in, callback out — this component never fetches session/plan
 * data itself.
 */
export function WorkoutFeedbackScreen({ sessionId, dayLabel, exercises, onBack, onDone }: WorkoutFeedbackScreenProps) {
  const [rows, setRows] = useState<RowState[]>(() => exercises.map(() => ({ ...DEFAULT_ROW })));
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function updateRow(index: number, patch: Partial<RowState>) {
    setRows((prev) => prev.map((row, i) => (i === index ? { ...row, ...patch } : row)));
  }

  async function handleSubmit() {
    setSubmitting(true);
    setError(null);
    try {
      const payload: ExerciseFeedbackInput[] = exercises.map((ex, i) => {
        const row = rows[i];
        const entry: ExerciseFeedbackInput = {
          name: ex.name,
          completed: row.completed,
          difficulty: row.difficulty,
          pain: row.pain,
        };
        if (row.pain && row.note.trim()) entry.note = row.note.trim();
        return entry;
      });

      const result = await submitWorkoutFeedback(sessionId, dayLabel, payload);
      onDone({ adjustmentTriggered: result.adjustment_triggered, summary: result.summary });
    } catch (err) {
      setSubmitting(false);
      setError(err instanceof ApiError ? err.message : 'Could not submit feedback — try again.');
    }
  }

  if (submitting) {
    return (
      <SafeAreaView style={styles.safeArea}>
        <View style={styles.centered}>
          <ActivityIndicator size="large" color={colors.accentPrimary} />
          <Text style={styles.loadingLabel}>Adjusting your plan…</Text>
          <Text style={styles.loadingHint}>This can take a moment if anything needs adjusting.</Text>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.safeArea} edges={['top']}>
      <ScrollView contentContainerStyle={styles.content}>
        <View style={styles.header}>
          <TouchableOpacity style={styles.backBtn} onPress={onBack} activeOpacity={0.7}>
            <Text style={styles.backBtnText}>‹</Text>
          </TouchableOpacity>
          <Text style={styles.title}>How did today go?</Text>
        </View>
        <Text style={styles.subtitle}>{dayLabel} · leave anything untouched to mark it fine</Text>

        {error ? (
          <Card style={styles.errorCard}>
            <Text style={styles.errorText}>{error}</Text>
          </Card>
        ) : null}

        {exercises.map((ex, i) => {
          const row = rows[i];
          return (
            <Card key={`${ex.name}-${i}`}>
              <Text style={styles.exerciseName}>
                {ex.name} <Text style={styles.exerciseSets}>· {ex.sets}</Text>
              </Text>
              <PillSelect
                label="How did it feel?"
                options={DIFFICULTY_OPTIONS}
                value={row.difficulty}
                onChange={(difficulty) => updateRow(i, { difficulty })}
              />
              <PillSelect
                label="Anything hurt?"
                variant={row.pain ? 'danger' : 'accent'}
                options={PAIN_OPTIONS}
                value={row.pain ? 'yes' : 'no'}
                onChange={(v) => updateRow(i, { pain: v === 'yes' })}
              />
              {row.pain ? (
                <TextField
                  label="Note (optional)"
                  placeholder="What hurt, and where?"
                  value={row.note}
                  onChangeText={(note) => updateRow(i, { note })}
                  multiline
                  numberOfLines={2}
                />
              ) : null}
              <TouchableOpacity
                style={styles.skipRow}
                onPress={() => updateRow(i, { completed: !row.completed })}
                activeOpacity={0.7}
              >
                <View style={[styles.checkbox, !row.completed && styles.checkboxChecked]} />
                <Text style={styles.skipLabel}>I skipped this exercise</Text>
              </TouchableOpacity>
            </Card>
          );
        })}

        <PrimaryButton label="Submit Feedback" onPress={handleSubmit} style={{ marginTop: spacing.gapCards }} />
        <GhostButton label="Back" onPress={onBack} style={{ marginTop: spacing.gapInner, marginBottom: 20 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: colors.bgPrimary },
  centered: { flex: 1, alignItems: 'center', justifyContent: 'center', paddingHorizontal: spacing.screenPad },
  loadingLabel: { fontSize: 15, fontWeight: '600', color: colors.textPrimary, marginTop: 20, textAlign: 'center' },
  loadingHint: { fontSize: 12, color: colors.textMuted, marginTop: 8, textAlign: 'center' },
  content: { padding: spacing.screenPad, paddingBottom: 60 },
  header: { flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 4 },
  backBtn: {
    width: 30, height: 30, borderRadius: 10, borderWidth: 1, borderColor: colors.borderDefault,
    backgroundColor: colors.bgCardAlt, alignItems: 'center', justifyContent: 'center',
  },
  backBtnText: { fontSize: 18, color: colors.textPrimary, marginTop: -2 },
  title: { fontSize: 20, fontWeight: '700', color: colors.textPrimary },
  subtitle: { fontSize: 12.5, color: colors.textMuted, marginBottom: 16 },
  errorCard: { borderColor: colors.danger },
  errorText: { fontSize: 13, color: colors.danger },
  exerciseName: { fontSize: 15, fontWeight: '600', color: colors.textPrimary, marginBottom: 14 },
  exerciseSets: { fontSize: 13, fontWeight: '400', color: colors.textMuted },
  skipRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 4 },
  checkbox: { width: 16, height: 16, borderRadius: 4, borderWidth: 1.5, borderColor: colors.borderDefault },
  checkboxChecked: { backgroundColor: colors.accentPrimary, borderColor: colors.accentPrimary },
  skipLabel: { fontSize: 12, color: colors.textSecondary },
});
