import React, { useState } from 'react';
import { ScrollView, StyleSheet } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { PillSelect } from '../../components/PillSelect';
import { PrimaryButton } from '../../components/Buttons';
import { StepHeader } from '../../components/StepHeader';
import { TextField } from '../../components/TextField';
import { colors, spacing } from '../../theme';

// The backend classifies free-text goals into a training paradigm itself
// (Supervisor step 0, tamrena_architecture_2.md Section 4e) -- these are
// quick-pick suggestions that fill the text field, not a closed enum like
// experience/duration are on the next step.
const GOAL_SUGGESTIONS = ['Build muscle', 'Get stronger', 'Lose fat', 'General fitness', 'Athletic performance'];
const DAY_OPTIONS = ['2', '3', '4', '5', '6'];

interface Props {
  initialGoal?: string;
  initialDays?: number;
  onNext: (patch: { goal: string; days_per_week: number }) => void;
}

export function IntakeStep1({ initialGoal, initialDays, onNext }: Props) {
  const [goal, setGoal] = useState(initialGoal ?? '');
  const [days, setDays] = useState<string | null>(initialDays ? String(initialDays) : null);

  const canContinue = goal.trim().length > 0 && days !== null;

  return (
    <SafeAreaView style={styles.safeArea}>
      <ScrollView contentContainerStyle={styles.content}>
        <StepHeader step={1} total={4} title="What's your goal?" />

        <TextField
          label="Goal"
          placeholder="e.g. Build muscle, get stronger, lose fat..."
          value={goal}
          onChangeText={setGoal}
        />
        <PillSelect
          label="Or pick one"
          options={GOAL_SUGGESTIONS.map((g) => ({ label: g, value: g }))}
          value={GOAL_SUGGESTIONS.includes(goal) ? goal : null}
          onChange={setGoal}
        />

        <PillSelect
          label="Days per week"
          options={DAY_OPTIONS.map((n) => ({ label: n, value: n }))}
          value={days}
          onChange={setDays}
        />

        <PrimaryButton
          label="Continue"
          disabled={!canContinue}
          onPress={() => canContinue && onNext({ goal: goal.trim(), days_per_week: Number(days) })}
        />
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: colors.bgPrimary },
  content: { padding: spacing.screenPad, paddingTop: 40, paddingBottom: 60 },
});
