import { Ionicons } from '@expo/vector-icons';
import React from 'react';
import { StyleSheet, TouchableOpacity } from 'react-native';

import { colors } from '../theme';

/**
 * Floating app-guidance chatbot button — bottom-right, floating clear
 * above the tab bar (see docs/superpowers/specs/2026-07-20-mobile-app-
 * navigation-design.md and the Superdesign TabBar component iteration:
 * this exact position/clearance came from user feedback on the mockup —
 * bottom-left overlapped the Home tab icon, so it moved to bottom-right
 * with enough clearance to sit fully above the bar).
 */
export function ChatButton({ onPress }: { onPress?: () => void }) {
  return (
    <TouchableOpacity style={styles.button} activeOpacity={0.85} onPress={onPress}>
      <Ionicons name="chatbubble-ellipses" size={22} color="#fff" />
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  button: {
    position: 'absolute',
    right: 16,
    bottom: 88,
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: colors.accentPrimary,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 4,
    borderColor: '#fff',
    shadowColor: '#000',
    shadowOpacity: 0.15,
    shadowRadius: 6,
    shadowOffset: { width: 0, height: 2 },
    elevation: 4,
    zIndex: 10,
  },
});
