import { GoogleSignin } from '@react-native-google-signin/google-signin';
import * as SecureStore from 'expo-secure-store';
import React, { createContext, useContext, useEffect, useState } from 'react';

import { fetchMe, signInWithGoogleIdToken, User } from '../api/auth';
import { setAuthToken } from '../api/client';
import { GOOGLE_WEB_CLIENT_ID } from '../config';

// GoogleSignin requires custom native code and does NOT run in Expo Go —
// this only works in a dev-client/standalone build. See mobile/README's
// auth setup notes for the EAS build + Google Cloud Console steps needed
// before this can actually be tapped and tested.
//
// Calling .configure() reaches into the native module immediately, which
// doesn't exist in Expo Go — left unguarded, this throws at MODULE LOAD
// TIME (this runs the moment AuthContext is imported, before React ever
// renders), crashing the entire app on startup rather than just failing
// when the sign-in button is tapped. Swallowing it here means the rest of
// the app (including onboarding, which has no native dependency) still
// loads fine in Expo Go — signInWithGoogle()'s own try/catch below is what
// surfaces a real error to the user if they actually tap the button.
try {
  GoogleSignin.configure({ webClientId: GOOGLE_WEB_CLIENT_ID });
} catch {
  // No native module in this environment (Expo Go) — expected, not a bug.
}

const TOKEN_STORAGE_KEY = 'tamreena_access_token';

interface AuthState {
  user: User | null;
  isLoading: boolean;
  isSigningIn: boolean;
  error: string | null;
  signInWithGoogle: () => Promise<void>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthState | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSigningIn, setIsSigningIn] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    restoreSession();
  }, []);

  async function restoreSession() {
    try {
      const storedToken = await SecureStore.getItemAsync(TOKEN_STORAGE_KEY);
      if (!storedToken) return;
      setAuthToken(storedToken);
      const me = await fetchMe();
      setUser(me);
    } catch {
      // Stored token is missing/expired/invalid — fall through to the
      // login screen rather than surfacing an error on launch.
      await SecureStore.deleteItemAsync(TOKEN_STORAGE_KEY);
      setAuthToken(null);
    } finally {
      setIsLoading(false);
    }
  }

  async function signInWithGoogle() {
    setIsSigningIn(true);
    setError(null);
    try {
      await GoogleSignin.hasPlayServices();
      const result = await GoogleSignin.signIn();
      const idToken = result.data?.idToken;
      if (!idToken) {
        throw new Error('Google did not return an ID token.');
      }

      const session = await signInWithGoogleIdToken(idToken);
      await SecureStore.setItemAsync(TOKEN_STORAGE_KEY, session.access_token);
      setAuthToken(session.access_token);
      setUser(session.user);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Sign-in failed.');
    } finally {
      setIsSigningIn(false);
    }
  }

  async function signOut() {
    await SecureStore.deleteItemAsync(TOKEN_STORAGE_KEY);
    setAuthToken(null);
    setUser(null);
    try {
      await GoogleSignin.signOut();
    } catch {
      // Not signed in on the native side (e.g. session was restored from
      // a stored token without a live native session) — nothing to undo.
    }
  }

  return (
    <AuthContext.Provider value={{ user, isLoading, isSigningIn, error, signInWithGoogle, signOut }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return ctx;
}
