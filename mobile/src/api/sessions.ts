import { apiFetch } from './client';

export interface PlanSession {
  session_id: string;
  goal: string | null;
  created_at: string;
}

export function fetchSessions(): Promise<PlanSession[]> {
  return apiFetch<{ sessions: PlanSession[] }>('/sessions').then((r) => r.sessions);
}
