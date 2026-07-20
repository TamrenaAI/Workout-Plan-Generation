import { apiFetch } from './client';

export interface User {
  id: number;
  email: string;
  name: string | null;
  picture_url: string | null;
  created_at: string;
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

/** Only ever reachable from a __DEV__-gated button (see LoginScreen) —
 * the backend route itself is also disabled unless the server operator
 * explicitly set ALLOW_DEV_LOGIN=true, so this 404s against any real
 * deployment regardless of the client-side guard. See api/routes/auth.py. */
export function devLogin(): Promise<SessionResponse> {
  return apiFetch<SessionResponse>('/auth/dev-login', { method: 'POST' });
}
