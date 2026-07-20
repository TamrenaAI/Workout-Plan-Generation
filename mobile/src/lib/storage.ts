import { Platform } from 'react-native';
import * as SecureStore from 'expo-secure-store';

/**
 * expo-secure-store has no web implementation (confirmed against Expo SDK
 * 57 docs — supported platforms are android/ios/tvos/expo-go; web isn't
 * listed, and there's no documented fallback). Falling back to
 * localStorage on web keeps `expo start --web` usable for previewing the
 * app on the PC without a phone. Tokens stored this way are less
 * protected than the OS keychain SecureStore uses natively, but that's
 * inherent to any web app's storage, not a regression introduced here.
 */
export async function getSecureItem(key: string): Promise<string | null> {
  if (Platform.OS === 'web') {
    return typeof localStorage === 'undefined' ? null : localStorage.getItem(key);
  }
  return SecureStore.getItemAsync(key);
}

export async function setSecureItem(key: string, value: string): Promise<void> {
  if (Platform.OS === 'web') {
    if (typeof localStorage !== 'undefined') localStorage.setItem(key, value);
    return;
  }
  await SecureStore.setItemAsync(key, value);
}

export async function deleteSecureItem(key: string): Promise<void> {
  if (Platform.OS === 'web') {
    if (typeof localStorage !== 'undefined') localStorage.removeItem(key);
    return;
  }
  await SecureStore.deleteItemAsync(key);
}
