import React from 'react';
import { ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Badge } from '../components/Badge';
import { Card } from '../components/Card';
import { PrimaryButton } from '../components/Buttons';
import { StatTile } from '../components/StatTile';
import { colors, spacing } from '../theme';

// Mock content matching the approved Superdesign mockup — real data comes
// from GET /sessions, GET /progress/scans, and the Nutrition Agent once
// those are wired up (follow-up task, not part of this scaffold).
export function HomeScreen() {
  return (
    <SafeAreaView style={styles.safeArea} edges={['top']}>
      <ScrollView contentContainerStyle={styles.content}>
        <View style={styles.header}>
          <Text style={styles.greeting}>Good morning, Abdullah</Text>
          <Badge label="12 days left in your free trial" />
        </View>

        <Text style={styles.sectionTitle}>Today's Workout</Text>
        <Card>
          <View style={styles.rowBetween}>
            <View>
              <Text style={styles.cardTitle}>Push Day</Text>
              <Text style={styles.cardSubtitle}>Chest, Shoulders, Triceps</Text>
            </View>
            <Badge label="7 Exercises" />
          </View>
          <PrimaryButton label="Start Workout" style={{ marginTop: spacing.gapCards }} />
        </Card>

        <View style={styles.rowBetween}>
          <Text style={styles.sectionTitleInline}>Nutrition Today</Text>
          <Text style={styles.link}>View Plan</Text>
        </View>
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
          <Text style={styles.cardTitle}>Day 14</Text>
          <Text style={styles.cardSubtitleMuted}>Since starting program</Text>
          <View style={styles.divider} />
          <Text style={styles.cardSubtitle}>
            Next InBody scan due in <Text style={styles.bold}>4 days</Text>
          </Text>
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
  cardSubtitle: { fontSize: 13, color: colors.textSecondary, marginTop: 2 },
  cardSubtitleMuted: { fontSize: 11, color: colors.textMuted, textTransform: 'uppercase', fontWeight: '600', marginTop: 2 },
  link: { color: colors.accentPrimary, fontSize: 13, fontWeight: '600' },
  divider: { height: 0.5, backgroundColor: colors.borderDefault, marginVertical: 12 },
  bold: { fontWeight: '700', color: colors.textPrimary },
});
