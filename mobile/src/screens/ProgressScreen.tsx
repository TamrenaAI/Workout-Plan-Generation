import React, { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, RefreshControl, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { fetchLatestComparison, fetchScanHistory, InBodyScan, ScanComparison } from '../api/progress';
import { ApiError } from '../api/client';
import { Badge } from '../components/Badge';
import { Card } from '../components/Card';
import { colors, spacing } from '../theme';

function formatDate(iso: string): string {
  return new Date(iso.replace(' ', 'T') + 'Z').toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

function deltaBadge(value: number, unit: string, lowerIsBetter: boolean) {
  const improved = lowerIsBetter ? value < 0 : value > 0;
  const sign = value > 0 ? '+' : '';
  return <Badge label={`${sign}${value}${unit}`} variant={improved ? 'success' : value === 0 ? 'default' : 'warning'} />;
}

export function ProgressScreen() {
  const [scans, setScans] = useState<InBodyScan[] | null>(null);
  const [comparison, setComparison] = useState<ScanComparison | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [scanHistory, latestComparison] = await Promise.all([fetchScanHistory(), fetchLatestComparison()]);
      setScans(scanHistory);
      setComparison(latestComparison);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not load progress.');
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function onRefresh() {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  }

  if (scans === null && !error) {
    return (
      <SafeAreaView style={styles.safeArea}>
        <View style={styles.centered}>
          <ActivityIndicator color={colors.accentPrimary} />
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.safeArea} edges={['top']}>
      <ScrollView
        contentContainerStyle={styles.content}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
      >
        <Text style={styles.title}>Progress</Text>

        {error ? (
          <Card>
            <Text style={styles.error}>{error}</Text>
          </Card>
        ) : null}

        <Text style={styles.sectionTitle}>Latest Comparison</Text>
        {comparison ? (
          <Card>
            <View style={styles.rowBetween}>
              <Text style={styles.compareLabel}>Skeletal Muscle Mass</Text>
              {deltaBadge(comparison.delta.skeletal_muscle_mass_kg, ' kg', false)}
            </View>
            <View style={styles.rowBetween}>
              <Text style={styles.compareLabel}>Body Fat %</Text>
              {deltaBadge(comparison.delta.body_fat_percent, '%', true)}
            </View>
            {comparison.delta.arm_asymmetry_resolved ? (
              <View style={styles.rowBetween}>
                <Text style={styles.compareLabel}>Arm Asymmetry</Text>
                <Badge label="Resolved" variant="success" />
              </View>
            ) : null}
            {comparison.delta.leg_asymmetry_resolved ? (
              <View style={styles.rowBetween}>
                <Text style={styles.compareLabel}>Leg Asymmetry</Text>
                <Badge label="Resolved" variant="success" />
              </View>
            ) : null}
          </Card>
        ) : (
          <Card>
            <Text style={styles.emptyText}>
              Record your next InBody scan to see how you've progressed since your last one.
            </Text>
          </Card>
        )}

        <Text style={styles.sectionTitle}>Scan History</Text>
        {scans && scans.length > 0 ? (
          scans.map((scan) => (
            <Card key={scan.id}>
              <View style={styles.rowBetween}>
                <Text style={styles.scanDate}>{formatDate(scan.created_at)}</Text>
                <Text style={styles.scanStat}>
                  {scan.skeletal_muscle_mass_kg.toFixed(1)} kg SMM · {scan.body_fat_percent.toFixed(1)}% BF
                </Text>
              </View>
            </Card>
          ))
        ) : (
          <Card>
            <Text style={styles.emptyText}>No InBody scans yet — generate a plan to record your first one.</Text>
          </Card>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: colors.bgPrimary },
  centered: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  content: { padding: spacing.screenPad, paddingBottom: 120 },
  title: { fontSize: 24, fontWeight: '700', color: colors.textPrimary, marginBottom: 16 },
  sectionTitle: { fontSize: 18, fontWeight: '700', color: colors.textPrimary, marginBottom: 12 },
  rowBetween: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 },
  compareLabel: { fontSize: 14, color: colors.textSecondary },
  scanDate: { fontSize: 13, fontWeight: '600', color: colors.textPrimary },
  scanStat: { fontSize: 12, color: colors.textSecondary },
  emptyText: { fontSize: 13, color: colors.textMuted, lineHeight: 18 },
  error: { fontSize: 13, color: colors.danger },
});
