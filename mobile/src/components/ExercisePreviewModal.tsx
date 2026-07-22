import React, { useEffect, useState } from 'react';
import { ActivityIndicator, Image, Modal, ScrollView, StyleSheet, Text, View } from 'react-native';

import { ExerciseMedia, fetchExerciseMedia, resolveExerciseMediaUrl } from '../api/exercises';
import { ApiError } from '../api/client';
import { colors, radii, spacing } from '../theme';
import { GhostButton, PrimaryButton } from './Buttons';

interface ExercisePreviewModalProps {
  visible: boolean;
  exerciseName: string;
  onClose: () => void;
  onStart: () => void;
}

/** Shown when the user taps "Start Set" — lets them see the exercise's GIF
 * and instructions before starting, per the product ask. Exercise names
 * here come from an LLM-generated plan with no catalog ID, so a lookup
 * miss (fuzzy match found nothing good enough) is a normal, expected
 * outcome — shown as "no preview available", not an error banner. */
export function ExercisePreviewModal({ visible, exerciseName, onClose, onStart }: ExercisePreviewModalProps) {
  const [media, setMedia] = useState<ExerciseMedia | null>(null);
  const [loading, setLoading] = useState(false);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    if (!visible) return;
    setMedia(null);
    setNotFound(false);
    setLoading(true);
    fetchExerciseMedia(exerciseName)
      .then(setMedia)
      .catch((err) => {
        if (err instanceof ApiError && err.status === 404) {
          setNotFound(true);
        }
      })
      .finally(() => setLoading(false));
  }, [visible, exerciseName]);

  return (
    <Modal visible={visible} animationType="slide" transparent onRequestClose={onClose}>
      <View style={styles.backdrop}>
        <View style={styles.sheet}>
          <ScrollView contentContainerStyle={styles.content}>
            <Text style={styles.title}>{exerciseName}</Text>

            {loading ? (
              <ActivityIndicator color={colors.accentPrimary} style={styles.gifBox} />
            ) : media?.gif_url ? (
              <Image
                source={{ uri: resolveExerciseMediaUrl(media.gif_url) }}
                style={styles.gifBox}
                resizeMode="contain"
              />
            ) : notFound ? (
              <View style={[styles.gifBox, styles.gifPlaceholder]}>
                <Text style={styles.emptyText}>No preview available for this exercise.</Text>
              </View>
            ) : null}

            {media?.instructions ? <Text style={styles.instructions}>{media.instructions}</Text> : null}
            {media?.attribution ? <Text style={styles.attribution}>{media.attribution}</Text> : null}
          </ScrollView>

          <View style={styles.actions}>
            <GhostButton label="Close" onPress={onClose} style={styles.actionButton} />
            <PrimaryButton label="Start Set" onPress={onStart} style={styles.actionButton} />
          </View>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: { flex: 1, backgroundColor: 'rgba(0,0,0,0.5)', justifyContent: 'flex-end' },
  sheet: {
    backgroundColor: colors.bgPrimary,
    borderTopLeftRadius: radii.card,
    borderTopRightRadius: radii.card,
    maxHeight: '85%',
    paddingTop: spacing.screenPad,
  },
  content: { paddingHorizontal: spacing.screenPad, paddingBottom: spacing.gapCards },
  title: { fontSize: 20, fontWeight: '700', color: colors.textPrimary, marginBottom: spacing.gapCards, textTransform: 'capitalize' },
  gifBox: {
    width: '100%',
    aspectRatio: 1,
    backgroundColor: colors.bgCardAlt,
    borderRadius: radii.tile,
    marginBottom: spacing.gapCards,
  },
  gifPlaceholder: { alignItems: 'center', justifyContent: 'center' },
  emptyText: { fontSize: 13, color: colors.textMuted, textAlign: 'center', paddingHorizontal: spacing.gapCards },
  instructions: { fontSize: 14, lineHeight: 1.5 * 14, color: colors.textSecondary, marginBottom: spacing.gapInner },
  attribution: { fontSize: 11, color: colors.textDisabled, marginBottom: spacing.gapCards },
  actions: {
    flexDirection: 'row',
    gap: spacing.gapInner,
    paddingHorizontal: spacing.screenPad,
    paddingBottom: spacing.gapCards,
    paddingTop: spacing.gapInner,
    borderTopWidth: 1,
    borderTopColor: colors.borderDefault,
  },
  actionButton: { flex: 1 },
});
