import React, { useEffect, useRef, useState } from 'react';
import { ActivityIndicator, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import EventSource from 'react-native-sse';

import { ApiError, getAuthToken } from '../../api/client';
import { generatePlan } from '../../api/plan';
import { GhostButton } from '../../components/Buttons';
import { API_BASE_URL } from '../../config';
import { colors, spacing } from '../../theme';
import { CapturedImage, IntakeData } from '../types';

interface ProgressEvent {
  type: 'progress' | 'done';
  agent?: string;
  label?: string;
  plan?: string;
  error?: string;
}

interface Props {
  intake: IntakeData;
  image: CapturedImage;
  onComplete: () => void;
  onRetry: () => void;
}

/**
 * Mirrors frontend/src/pages/processing.js's runGeneration() + streamProgress()
 * flow: POST /generate-plan kicks off the background pipeline, then GET
 * /generate-plan/stream/{session_id} (SSE) narrates progress until a
 * "done" event carries the final result or an error.
 *
 * React Native has no built-in EventSource — react-native-sse is a pure-JS
 * polyfill (uses XMLHttpRequest under the hood), so this works in Expo Go
 * with no native linking, unlike Google Sign-In.
 */
export function ProcessingStep({ intake, image, onComplete, onRetry }: Props) {
  const [label, setLabel] = useState('Uploading InBody scan…');
  const [error, setError] = useState<string | null>(null);
  const esRef = useRef<EventSource<'message'> | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function run() {
      try {
        const { session_id } = await generatePlan(intake, image);
        if (cancelled) return;

        setLabel('Generating your plan…');
        const token = getAuthToken();
        const es = new EventSource<'message'>(`${API_BASE_URL}/generate-plan/stream/${session_id}`, {
          headers: {
            Authorization: {
              toString: () => `Bearer ${token ?? ''}`,
            },
          } as unknown as Record<string, string>,
        });
        esRef.current = es;

        es.addEventListener('message', (event) => {
          if (!event.data) return;
          let data: ProgressEvent;
          try {
            data = JSON.parse(event.data);
          } catch {
            return;
          }

          if (data.type === 'progress') {
            setLabel([data.agent, data.label].filter(Boolean).join(' — '));
          } else if (data.type === 'done') {
            es.close();
            if (data.error) {
              setError(data.error);
            } else {
              onComplete();
            }
          }
        });

        es.addEventListener('error', () => {
          if (!cancelled) setError('Lost connection to the server while generating your plan.');
        });
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : 'Could not start plan generation.');
        }
      }
    }

    run();
    return () => {
      cancelled = true;
      esRef.current?.close();
    };
    // Intentionally runs once per mount — retrying re-mounts this step
    // (see OnboardingFlow) rather than re-running this effect in place.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (error) {
    return (
      <SafeAreaView style={styles.safeArea}>
        <View style={styles.centered}>
          <Text style={styles.errorTitle}>Generation Failed</Text>
          <Text style={styles.errorText}>{error}</Text>
          <GhostButton label="Try Again" onPress={onRetry} style={{ marginTop: spacing.gapCards, width: 200 }} />
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.safeArea}>
      <View style={styles.centered}>
        <ActivityIndicator size="large" color={colors.accentPrimary} />
        <Text style={styles.label}>{label}</Text>
        <Text style={styles.hint}>This can take a few minutes — several agents work through your plan in sequence.</Text>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: colors.bgPrimary },
  centered: { flex: 1, alignItems: 'center', justifyContent: 'center', paddingHorizontal: spacing.screenPad },
  label: { fontSize: 15, fontWeight: '600', color: colors.textPrimary, marginTop: 20, textAlign: 'center' },
  hint: { fontSize: 12, color: colors.textMuted, marginTop: 8, textAlign: 'center' },
  errorTitle: { fontSize: 20, fontWeight: '700', color: colors.danger, marginBottom: 8 },
  errorText: { fontSize: 13, color: colors.textMuted, textAlign: 'center' },
});
