import { manipulateAsync, SaveFormat } from 'expo-image-manipulator';
import * as ImagePicker from 'expo-image-picker';
import React, { useState } from 'react';
import { ActivityIndicator, Image, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { ApiError } from '../../api/client';
import { validateImage } from '../../api/plan';
import { Badge } from '../../components/Badge';
import { GhostButton, PrimaryButton } from '../../components/Buttons';
import { StepHeader } from '../../components/StepHeader';
import { colors, spacing } from '../../theme';
import { CapturedImage } from '../types';

type Status = 'idle' | 'checking' | 'valid' | 'invalid';

// A phone camera photo (commonly 12-48MP) only needs to be legible enough
// for the server-side VLM to read InBody's printed numbers — a modern
// phone's raw capture (several MB) uploads slowly on real mobile networks
// for no accuracy benefit. Downscaling the long edge to this, plus
// re-compressing, cuts a typical capture from several MB to a few hundred
// KB. Only resize when the source actually exceeds it — never upscale a
// smaller source image (e.g. one already picked from a compressed library
// photo or screenshot).
const MAX_DIMENSION = 2000;

/**
 * Uses the native camera/photo-library picker UI (expo-image-picker)
 * rather than a custom live-camera overlay with client-side pixel
 * analysis, like the web app's CameraCapture class has. The server-side
 * check (POST /validate-image -> check_image_quality + validate_inbody_scan)
 * is the authoritative one either way; this skips only the redundant
 * client-side pre-check, not real validation.
 */
export function CaptureStep({ onNext }: { onNext: (image: CapturedImage) => void }) {
  const [image, setImage] = useState<CapturedImage | null>(null);
  const [status, setStatus] = useState<Status>('idle');
  const [message, setMessage] = useState<string | null>(null);

  async function pick(source: 'camera' | 'library') {
    const permission =
      source === 'camera'
        ? await ImagePicker.requestCameraPermissionsAsync()
        : await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!permission.granted) {
      setStatus('invalid');
      setMessage('Permission was denied — allow camera/photo access in Settings to continue.');
      return;
    }

    const result = source === 'camera'
      ? await ImagePicker.launchCameraAsync({ quality: 0.9 })
      : await ImagePicker.launchImageLibraryAsync({ quality: 0.9 });

    if (result.canceled || !result.assets?.[0]) return;

    const asset = result.assets[0];
    const captured = await resizeIfNeeded(asset);
    setImage(captured);
    await runValidation(captured);
  }

  async function resizeIfNeeded(asset: ImagePicker.ImagePickerAsset): Promise<CapturedImage> {
    const longEdge = Math.max(asset.width, asset.height);
    if (longEdge <= MAX_DIMENSION) {
      return { uri: asset.uri, mimeType: asset.mimeType ?? 'image/jpeg' };
    }

    const isPortrait = asset.height >= asset.width;
    const resized = await manipulateAsync(
      asset.uri,
      [{ resize: isPortrait ? { height: MAX_DIMENSION } : { width: MAX_DIMENSION } }],
      { compress: 0.85, format: SaveFormat.JPEG },
    );
    return { uri: resized.uri, mimeType: 'image/jpeg' };
  }

  async function runValidation(captured: CapturedImage) {
    setStatus('checking');
    setMessage('Checking image quality...');
    try {
      const result = await validateImage(captured);
      if (result.valid) {
        setStatus('valid');
        setMessage('InBody scan detected');
      } else {
        setStatus('invalid');
        setMessage(result.issue ?? 'This does not look like a valid InBody scan.');
      }
    } catch (err) {
      setStatus('invalid');
      setMessage(err instanceof ApiError ? err.message : 'Could not check the image — try again.');
    }
  }

  return (
    <SafeAreaView style={styles.safeArea}>
      <ScrollView contentContainerStyle={styles.content}>
        <StepHeader step={4} total={4} title="Scan your InBody result" subtitle="photo or gallery" />

        {image ? (
          <Image source={{ uri: image.uri }} style={styles.preview} resizeMode="contain" />
        ) : (
          <View style={styles.placeholder}>
            <Text style={styles.placeholderText}>Position the InBody scan inside the frame</Text>
          </View>
        )}

        {status === 'checking' ? (
          <View style={styles.statusRow}>
            <ActivityIndicator color={colors.warning} />
            <Text style={styles.statusText}>{message}</Text>
          </View>
        ) : message ? (
          <View style={styles.statusRow}>
            <Badge label={message} variant={status === 'valid' ? 'success' : 'danger'} />
          </View>
        ) : null}

        <PrimaryButton
          label={image ? 'Retake Photo' : 'Take Photo'}
          onPress={() => pick('camera')}
          style={{ marginTop: spacing.gapCards }}
        />
        <GhostButton label="Choose from Library" onPress={() => pick('library')} style={{ marginTop: spacing.gapInner }} />

        {status === 'valid' && image ? (
          <PrimaryButton label="Continue" onPress={() => onNext(image)} style={{ marginTop: spacing.gapCards }} />
        ) : null}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: colors.bgPrimary },
  content: { padding: spacing.screenPad, paddingTop: 40, paddingBottom: 60 },
  placeholder: {
    height: 280,
    borderRadius: 16,
    borderWidth: 2,
    borderColor: colors.borderDefault,
    borderStyle: 'dashed',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.bgCardAlt,
    marginBottom: spacing.gapCards,
  },
  placeholderText: { fontSize: 13, color: colors.textMuted, textAlign: 'center', paddingHorizontal: 24 },
  preview: { height: 280, borderRadius: 16, marginBottom: spacing.gapCards, backgroundColor: colors.bgCardAlt },
  statusRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: spacing.gapCards },
  statusText: { fontSize: 13, color: colors.textSecondary },
});
