import { apiFetch } from './client';

export interface User {
  id: number;
  email: string;
  name: string | null;
  picture_url: string | null;
}

export interface SessionResponse {
  access_token: string;
  token_type: string;
  user: User;
}

/** Exchanges a verified Google ID token for this backend's own session
 * JWT — see api/routes/auth.py's POST /auth/google. */
export function signInWithGoogleIdToken(idToken: string): Promise<SessionResponse> {
  return apiFetch<SessionResponse>('/auth/google', { method: 'POST', body: { id_token: idToken } });
}

export function fetchMe(): Promise<User> {
  return apiFetch<User>('/auth/me');
}
