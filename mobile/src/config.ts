/**
 * Runtime config — see .env.example for what needs to be set and why.
 * EXPO_PUBLIC_* vars are read at build time; there is no server-side
 * secret handling on the client (nor should there be — this is a public
 * mobile binary).
 */

export const API_BASE_URL = process.env.EXPO_PUBLIC_API_URL ?? 'http://localhost:8001';
export const GOOGLE_WEB_CLIENT_ID = process.env.EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID ?? '';
