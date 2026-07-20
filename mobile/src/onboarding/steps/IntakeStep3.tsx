import React, { useState } from 'react';
import { ScrollView, StyleSheet } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { GhostButton, PrimaryButton } from '../../components/Buttons';
import { PillSelect } from '../../components/PillSelect';
import { StepHeader } from '../../components/StepHeader';
import { TextField } from '../../components/TextField';
import { colors, spacing } from '../../theme';

const SLEEP_OPTIONS: { label: string; value: 'good' | 'average' | 'poor' }[] = [
  { label: 'Good', value: 'good' },
  { label: 'Average', value: 'average' },
  { label: 'Poor', value: 'poor' },
];
const JOB_OPTIONS: { label: string; value: 'desk' | 'light_physical' | 'heavy_physical' }[] = [
  { label: 'Desk job', value: 'desk' },
  { label: 'Light physical', value: 'light_physical' },
  { label: 'Heavy physical', value: 'heavy_physical' },
];

export interface OptionalIntakeFields {
  injuries?: string;
  priority?: string;
  age?: number;
  sleep_quality?: 'good' | 'average' | 'poor';
  job_type?: 'desk' | 'light_physical' | 'heavy_physical';
  current_program?: string;
}

export function IntakeStep3({ onNext }: { onNext: (patch: OptionalIntakeFields) => void }) {
  const [injuries, setInjuries] = useState('');
  const [priority, setPriority] = useState('');
  const [age, setAge] = useState('');
  const [sleepQuality, setSleepQuality] = useState<'good' | 'average' | 'poor' | null>(null);
  const [jobType, setJobType] = useState<'desk' | 'light_physical' | 'heavy_physical' | null>(null);
  const [currentProgram, setCurrentProgram] = useState('');

  function submit() {
    onNext({
      injuries: injuries.trim() || undefined,
      priority: priority.trim() || undefined,
      age: age.trim() ? Number(age.trim()) : undefined,
      sleep_quality: sleepQuality ?? undefined,
      job_type: jobType ?? undefined,
      current_program: currentProgram.trim() || undefined,
    });
  }

  return (
    <SafeAreaView style={styles.safeArea}>
      <ScrollView contentContainerStyle={styles.content}>
        <StepHeader step={3} total={4} title="A few more details" subtitle="all optional" />

        <TextField
          label="Injuries or limitations"
          placeholder="e.g. Left shoulder — no overhead pressing"
          value={injuries}
          onChangeText={setInjuries}
        />
        <TextField
          label="Priority focus"
          placeholder="e.g. I want bigger arms"
          value={priority}
          onChangeText={setPriority}
        />
        <TextField label="Age" placeholder="e.g. 27" keyboardType="number-pad" value={age} onChangeText={setAge} />
        <PillSelect label="Sleep quality" options={SLEEP_OPTIONS} value={sleepQuality} onChange={setSleepQuality} />
        <PillSelect label="Job type" options={JOB_OPTIONS} value={jobType} onChange={setJobType} />
        <TextField
          label="Current program"
          placeholder="What have you been doing so far?"
          value={currentProgram}
          onChangeText={setCurrentProgram}
        />

        <PrimaryButton label="Continue" onPress={submit} />
        <GhostButton label="Skip this step" onPress={() => onNext({})} style={{ marginTop: spacing.gapInner }} />
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: colors.bgPrimary },
  content: { padding: spacing.screenPad, paddingTop: 40, paddingBottom: 60 },
});
