import React, { useState } from 'react';
import { ScrollView, StyleSheet } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { PillSelect } from '../../components/PillSelect';
import { PrimaryButton } from '../../components/Buttons';
import { StepHeader } from '../../components/StepHeader';
import { colors, spacing } from '../../theme';

// Values match auth.py-adjacent backend validation exactly (VALID_EXPERIENCE
// in api/routes/plan.py, and DURATION_PATTERN = ^\d{2,3}min$) -- picking
// from a closed set here means there's no client-side re-validation to
// keep in sync with the server's.
const EXPERIENCE_OPTIONS: { label: string; value: 'beginner' | 'intermediate' | 'advanced' }[] = [
  { label: 'Beginner (<1yr)', value: 'beginner' },
  { label: 'Intermediate (1-3yr)', value: 'intermediate' },
  { label: 'Advanced (3yr+)', value: 'advanced' },
];
const DURATION_OPTIONS = ['45min', '60min', '75min', '90min'];

interface Props {
  initialExperience?: 'beginner' | 'intermediate' | 'advanced';
  initialDuration?: string;
  onNext: (patch: { experience: 'beginner' | 'intermediate' | 'advanced'; session_duration: string }) => void;
}

export function IntakeStep2({ initialExperience, initialDuration, onNext }: Props) {
  const [experience, setExperience] = useState<'beginner' | 'intermediate' | 'advanced' | null>(initialExperience ?? null);
  const [duration, setDuration] = useState<string | null>(initialDuration ?? null);

  const canContinue = experience !== null && duration !== null;

  return (
    <SafeAreaView style={styles.safeArea}>
      <ScrollView contentContainerStyle={styles.content}>
        <StepHeader step={2} total={4} title="Training experience" />

        <PillSelect label="Experience level" options={EXPERIENCE_OPTIONS} value={experience} onChange={setExperience} />
        <PillSelect
          label="Session duration"
          options={DURATION_OPTIONS.map((d) => ({ label: d, value: d }))}
          value={duration}
          onChange={setDuration}
        />

        <PrimaryButton
          label="Continue"
          disabled={!canContinue}
          onPress={() => canContinue && onNext({ experience: experience!, session_duration: duration! })}
        />
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: colors.bgPrimary },
  content: { padding: spacing.screenPad, paddingTop: 40, paddingBottom: 60 },
});
