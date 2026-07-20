import { apiFetch, apiFetchForm } from './client';
import { CapturedImage, IntakeData } from '../onboarding/types';

export interface SessionPlanResponse {
  status: 'ready' | 'pending';
  plan: string | null;
}

export function fetchSessionPlan(sessionId: string): Promise<SessionPlanResponse> {
  return apiFetch<SessionPlanResponse>(`/sessions/${sessionId}/plan`);
}

export interface ValidateImageResponse {
  valid: boolean;
  stage: string | null;
  issue: string | null;
}

/** Quality + authenticity check only — the same pre-check the web app's
 * CameraCapture runs before committing to a full (slower) generation
 * call. Doesn't create a session. */
export function validateImage(image: CapturedImage): Promise<ValidateImageResponse> {
  const formData = new FormData();
  formData.append('file', {
    uri: image.uri,
    name: 'scan.jpg',
    type: image.mimeType,
  } as unknown as Blob);
  return apiFetchForm<ValidateImageResponse>('/validate-image', formData);
}

export interface GeneratePlanResponse {
  session_id: string;
  inbody: Record<string, unknown>;
}

/** Kicks off generation — the caller then opens the SSE stream at
 * GET /generate-plan/stream/{session_id} for live progress and the final
 * plan text (see onboarding/steps/ProcessingStep.tsx). */
export function generatePlan(intake: IntakeData, image: CapturedImage): Promise<GeneratePlanResponse> {
  const formData = new FormData();
  formData.append('inbody_file', {
    uri: image.uri,
    name: 'scan.jpg',
    type: image.mimeType,
  } as unknown as Blob);
  formData.append('goal', intake.goal);
  formData.append('days_per_week', String(intake.days_per_week));
  formData.append('experience', intake.experience);
  formData.append('session_duration', intake.session_duration);
  if (intake.injuries) formData.append('injuries', intake.injuries);
  if (intake.priority) formData.append('priority', intake.priority);
  if (intake.age !== undefined) formData.append('age', String(intake.age));
  if (intake.sleep_quality) formData.append('sleep_quality', intake.sleep_quality);
  if (intake.job_type) formData.append('job_type', intake.job_type);
  if (intake.current_program) formData.append('current_program', intake.current_program);

  return apiFetchForm<GeneratePlanResponse>('/generate-plan', formData);
}
