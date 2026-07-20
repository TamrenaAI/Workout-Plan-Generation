import { apiFetch } from './client';

export interface SessionPlanResponse {
  status: 'ready' | 'pending';
  plan: string | null;
}

export function fetchSessionPlan(sessionId: string): Promise<SessionPlanResponse> {
  return apiFetch<SessionPlanResponse>(`/sessions/${sessionId}/plan`);
}
