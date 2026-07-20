import { API_BASE_URL } from '../config';

/** Thrown on any non-2xx response — `status` lets callers branch on 401 vs
 * everything else (e.g. AuthContext treats 401 as "session expired", not
 * a generic error to surface). */
export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

type FetchOptions = Omit<RequestInit, 'body'> & { body?: unknown };

let authToken: string | null = null;

/** Called by AuthContext after sign-in/sign-out/restore — every request
 * after that automatically carries the current token, so screens never
 * have to thread it through themselves. */
export function setAuthToken(token: string | null) {
  authToken = token;
}

/** react-native-sse's EventSource needs the token passed explicitly in its
 * own headers option (it isn't routed through apiFetch), unlike every
 * other request in this app. */
export function getAuthToken(): string | null {
  return authToken;
}

export async function apiFetch<T>(path: string, options: FetchOptions = {}): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string> | undefined),
  };
  if (authToken) {
    headers.Authorization = `Bearer ${authToken}`;
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
  });

  const text = await response.text();
  const data = text ? JSON.parse(text) : null;

  if (!response.ok) {
    const detail = data && typeof data === 'object' ? data.detail ?? data.error : undefined;
    const message = typeof detail === 'string' ? detail : response.statusText;
    throw new ApiError(response.status, message);
  }

  return data as T;
}

/** Separate from apiFetch because multipart requests must NOT set
 * Content-Type themselves — fetch derives the correct boundary from the
 * FormData body, and setting it manually breaks the upload. Used for
 * /validate-image and /generate-plan, both of which take a file. */
export async function apiFetchForm<T>(path: string, formData: FormData): Promise<T> {
  const headers: Record<string, string> = {};
  if (authToken) {
    headers.Authorization = `Bearer ${authToken}`;
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: 'POST',
    headers,
    body: formData,
  });

  const text = await response.text();
  const data = text ? JSON.parse(text) : null;

  if (!response.ok) {
    const detail = data && typeof data === 'object' ? data.detail ?? data.error : undefined;
    const message = typeof detail === 'string' ? detail : response.statusText;
    throw new ApiError(response.status, message);
  }

  return data as T;
}
