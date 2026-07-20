import { useNavigation } from '@react-navigation/native';
import React from 'react';
import { ActivityIndicator, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { useAuth } from '../auth/AuthContext';
import { Badge } from '../components/Badge';
import { Card } from '../components/Card';
import { PrimaryButton } from '../components/Buttons';
import { StatTile } from '../components/StatTile';
import { useLatestPlan } from '../hooks/useLatestPlan';
import { colors, spacing } from '../theme';

function daysSince(iso: string): number {
  const start = new Date(iso.replace(' ', 'T') + 'Z').getTime();
  return Math.max(0, Math.floor((Date.now() - start) / (1000 * 60 * 60 * 24)));
}

function exerciseCount(day: { blocks: { type: string; rows?: unknown[] }[] }): number {
  return day.blocks
    .filter((b): b is { type: 'table'; rows: unknown[] } => b.type === 'table')
    .reduce((sum, b) => sum + b.rows.length, 0);
}

export function HomeScreen() {
  const navigation = useNavigation<any>();
  const { user } = useAuth();
  const { isLoading, error, session, status, days } = useLatestPlan();
  const nextDay = days[0];

  return (
    <SafeAreaView style={styles.safeArea} edges={['top']}>
      <ScrollView contentContainerStyle={styles.content}>
        <View style={styles.header}>
          <Text style={styles.greeting}>
            {user?.name ? `Good morning, ${user.name.split(' ')[0]}` : 'Good morning'}
          </Text>
          {/* Subscription/trial status is still mock — Subscriptions/IAP isn't built yet. */}
          <Badge label="12 days left in your free trial" />
        </View>

        <Text style={styles.sectionTitle}>Next Workout</Text>
        <Card>
          {isLoading ? (
            <ActivityIndicator color={colors.accentPrimary} />
          ) : error ? (
            <Text style={styles.error}>{error}</Text>
          ) : !session ? (
            <Text style={styles.emptyText}>No plan yet — generate one to get started.</Text>
          ) : status === 'pending' ? (
            <Text style={styles.emptyText}>Your plan is still being generated…</Text>
          ) : nextDay ? (
            <>
              <View style={styles.rowBetween}>
                <View style={{ flex: 1 }}>
                  <Text style={styles.cardTitle}>{nextDay.title.replace(/^Day\s+\d+\s*[—-]\s*/i, '')}</Text>
                </View>
                <Badge label={`${exerciseCount(nextDay)} Exercises`} />
              </View>
              <PrimaryButton
                label="Start Workout"
                onPress={() => navigation.navigate('Workout')}
                style={{ marginTop: spacing.gapCards }}
              />
            </>
          ) : (
            <Text style={styles.emptyText}>Plan ready, but no training days were found in it.</Text>
          )}
        </Card>

        <View style={styles.rowBetween}>
          <Text style={styles.sectionTitleInline}>Nutrition Today</Text>
          <Text style={styles.link}>View Plan</Text>
        </View>
        {/* Still mock — Nutrition Agent integration is on hold pending the coworker's contract. */}
        <Card>
          <View style={styles.statRow}>
            <StatTile value="2,450" label="kcal" />
            <StatTile value="180g" label="Pro" />
            <StatTile value="220g" label="Carb" />
            <StatTile value="75g" label="Fat" />
          </View>
        </Card>

        <Text style={styles.sectionTitle}>Your Progress</Text>
        <Card>
          <Text style={styles.cardTitle}>Day {user ? daysSince(user.created_at) : '—'}</Text>
          <Text style={styles.cardSubtitleMuted}>Since starting program</Text>
        </Card>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: colors.bgPrimary },
  content: { padding: spacing.screenPad, paddingBottom: 120 },
  header: { marginBottom: 24 },
  greeting: { fontSize: 24, fontWeight: '700', color: colors.textPrimary, marginBottom: 8 },
  sectionTitle: { fontSize: 20, fontWeight: '600', color: colors.textPrimary, marginBottom: 16, marginTop: 8 },
  sectionTitleInline: { fontSize: 18, fontWeight: '700', color: colors.textPrimary },
  rowBetween: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 },
  statRow: { flexDirection: 'row', gap: 12 },
  cardTitle: { fontSize: 17, fontWeight: '700', color: colors.textPrimary },
  cardSubtitleMuted: { fontSize: 11, color: colors.textMuted, textTransform: 'uppercase', fontWeight: '600', marginTop: 2 },
  link: { color: colors.accentPrimary, fontSize: 13, fontWeight: '600' },
  emptyText: { fontSize: 13, color: colors.textMuted },
  error: { fontSize: 13, color: colors.danger },
});
