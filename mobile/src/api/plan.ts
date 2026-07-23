import { Platform } from 'react-native';

import { apiFetch, apiFetchForm } from './client';
import { CapturedImage, IntakeData } from '../onboarding/types';

export interface SessionPlanResponse {
  status: 'ready' | 'pending';
  plan: string | null;
}

export function fetchSessionPlan(sessionId: string): Promise<SessionPlanResponse> {
  return apiFetch<SessionPlanResponse>(`/sessions/${sessionId}/plan`);
}

/**
 * React Native's FormData.append(name, {uri, name, type}) shorthand only
 * works on native platforms — RN's own FormData polyfill knows to read the
 * file at that URI. On web, `FormData` is the browser's real, unrelated
 * implementation: it doesn't understand that object shape at all and would
 * effectively send garbage for the file field (this was the actual cause
 * of "Unprocessable Entity" when testing via `expo start --web` — not
 * anything wrong with the image itself). Web needs an actual Blob, fetched
 * from the picker's blob:/data: URI first.
 */
async function appendImageFile(formData: FormData, fieldName: string, image: CapturedImage): Promise<void> {
  if (Platform.OS === 'web') {
    const response = await fetch(image.uri);
    const blob = await response.blob();
    formData.append(fieldName, blob, 'scan.jpg');
  } else {
    formData.append(fieldName, {
      uri: image.uri,
      name: 'scan.jpg',
      type: image.mimeType,
    } as unknown as Blob);
  }
}

export interface ValidateImageResponse {
  valid: boolean;
  stage: string | null;
  issue: string | null;
}

/** Quality + authenticity check only — the same pre-check the web app's
 * CameraCapture runs before committing to a full (slower) generation
 * call. Doesn't create a session. */
export async function validateImage(image: CapturedImage): Promise<ValidateImageResponse> {
  const formData = new FormData();
  await appendImageFile(formData, 'file', image);
  return apiFetchForm<ValidateImageResponse>('/validate-image', formData);
}

export interface GeneratePlanResponse {
  session_id: string;
  inbody: Record<string, unknown>;
}

/** Kicks off generation — the caller then opens the SSE stream at
 * GET /generate-plan/stream/{session_id} for live progress and the final
 * plan text (see onboarding/steps/ProcessingStep.tsx). */
export async function generatePlan(intake: IntakeData, image: CapturedImage): Promise<GeneratePlanResponse> {
  const formData = new FormData();
  await appendImageFile(formData, 'inbody_file', image);
  formData.append('goal', intake.goal);
  formData.append('days_per_week', String(intake.days_per_week));
  formData.append('experience', intake.experience);
  formData.append('session_duration', intake.session_duration);
  if (intake.injuries) formData.append('injuries', intake.injuries);
  if (intake.priority) formData.append('priority', intake.priority);
  if (intake.sleep_quality) formData.append('sleep_quality', intake.sleep_quality);
  if (intake.job_type) formData.append('job_type', intake.job_type);
  if (intake.current_program) formData.append('current_program', intake.current_program);

  return apiFetchForm<GeneratePlanResponse>('/generate-plan', formData);
}
