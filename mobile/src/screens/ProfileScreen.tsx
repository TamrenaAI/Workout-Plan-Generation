import React from 'react';
import { ScrollView, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Card } from '../components/Card';
import { GhostButton, PrimaryButton } from '../components/Buttons';
import { colors, spacing } from '../theme';

// Mock content — real user/subscription data comes from GET /auth/me and
// the (not-yet-built) Subscriptions/IAP integration.
const SETTINGS_ROWS = ['Language — English', 'Units — kg', 'Notifications'];

export function ProfileScreen() {
  return (
    <SafeAreaView style={styles.safeArea} edges={['top']}>
      <ScrollView contentContainerStyle={styles.content}>
        <View style={styles.header}>
          <View style={styles.avatar} />
          <View>
            <Text style={styles.name}>Abdullah</Text>
            <Text style={styles.email}>abdullah@example.com</Text>
          </View>
        </View>

        <Text style={styles.sectionTitle}>Subscription</Text>
        <Card>
          <Text style={styles.planName}>Free Trial — 12 days left</Text>
          <PrimaryButton label="Manage Subscription" style={{ marginTop: spacing.gapInner }} />
        </Card>

        <Text style={styles.sectionTitle}>Settings</Text>
        <Card style={{ paddingVertical: 4 }}>
          {SETTINGS_ROWS.map((row, i) => (
            <TouchableOpacity key={row} style={[styles.row, i > 0 && styles.rowDivider]}>
              <Text style={styles.rowText}>{row}</Text>
              <Text style={styles.chevron}>›</Text>
            </TouchableOpacity>
          ))}
        </Card>

        <Card>
          <TouchableOpacity style={styles.row}>
            <Text style={styles.rowText}>Support</Text>
            <Text style={styles.chevron}>›</Text>
          </TouchableOpacity>
        </Card>

        <GhostButton label="Log Out" style={{ marginTop: spacing.gapCards }} />
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: colors.bgPrimary },
  content: { padding: spacing.screenPad, paddingBottom: 120 },
  header: { flexDirection: 'row', alignItems: 'center', gap: 14, marginBottom: 20 },
  avatar: { width: 56, height: 56, borderRadius: 28, backgroundColor: colors.bgCardAlt, borderWidth: 1, borderColor: colors.borderDefault },
  name: { fontSize: 18, fontWeight: '700', color: colors.textPrimary },
  email: { fontSize: 13, color: colors.textMuted, marginTop: 2 },
  sectionTitle: { fontSize: 18, fontWeight: '700', color: colors.textPrimary, marginBottom: 12, marginTop: 8 },
  planName: { fontSize: 15, fontWeight: '600', color: colors.textPrimary },
  row: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingVertical: 14 },
  rowDivider: { borderTopWidth: 0.5, borderTopColor: colors.borderSubtle },
  rowText: { fontSize: 14, color: colors.textPrimary },
  chevron: { fontSize: 18, color: colors.textMuted },
});
