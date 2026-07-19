import React from 'react';
import { ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Badge } from '../components/Badge';
import { Card } from '../components/Card';
import { colors, spacing } from '../theme';

// Mock content matching the approved mockup — real data comes from
// GET /progress/scans and GET /progress/comparison (pipeline/inbody_history.py).
export function ProgressScreen() {
  return (
    <SafeAreaView style={styles.safeArea} edges={['top']}>
      <ScrollView contentContainerStyle={styles.content}>
        <Text style={styles.title}>Progress</Text>

        <Text style={styles.sectionTitle}>Your Journey</Text>
        <Card>
          <View style={styles.journeyRow}>
            <View style={styles.journeyStep}>
              <View style={[styles.journeyDot, styles.journeyDotDone]} />
              <Text style={styles.journeyLabel}>Start</Text>
            </View>
            <View style={styles.journeyLine} />
            <View style={styles.journeyStep}>
              <View style={[styles.journeyDot, styles.journeyDotCurrent]} />
              <Text style={styles.journeyLabel}>Current</Text>
            </View>
            <View style={[styles.journeyLine, styles.journeyLineMuted]} />
            <View style={styles.journeyStep}>
              <View style={styles.journeyDot} />
              <Text style={styles.journeyLabel}>Goal</Text>
            </View>
          </View>
        </Card>

        <Text style={styles.sectionTitle}>Latest Comparison</Text>
        <Card>
          <View style={styles.rowBetween}>
            <Text style={styles.compareLabel}>Skeletal Muscle Mass</Text>
            <Badge label="+1.5 kg" variant="success" />
          </View>
          <View style={styles.rowBetween}>
            <Text style={styles.compareLabel}>Body Fat %</Text>
            <Badge label="-1.5%" variant="success" />
          </View>
          <View style={styles.rowBetween}>
            <Text style={styles.compareLabel}>Arm Asymmetry</Text>
            <Badge label="Resolved" variant="success" />
          </View>
        </Card>

        <Card style={styles.reminder}>
          <Text style={styles.reminderText}>Next InBody scan due in 4 days</Text>
        </Card>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: colors.bgPrimary },
  content: { padding: spacing.screenPad, paddingBottom: 120 },
  title: { fontSize: 24, fontWeight: '700', color: colors.textPrimary, marginBottom: 16 },
  sectionTitle: { fontSize: 18, fontWeight: '700', color: colors.textPrimary, marginBottom: 12 },
  journeyRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  journeyStep: { alignItems: 'center' },
  journeyDot: { width: 14, height: 14, borderRadius: 7, backgroundColor: colors.borderDefault },
  journeyDotDone: { backgroundColor: colors.success },
  journeyDotCurrent: { backgroundColor: colors.accentPrimary },
  journeyLine: { flex: 1, height: 2, backgroundColor: colors.success, marginHorizontal: 4 },
  journeyLineMuted: { backgroundColor: colors.borderDefault },
  journeyLabel: { fontSize: 11, color: colors.textMuted, marginTop: 6 },
  rowBetween: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 },
  compareLabel: { fontSize: 14, color: colors.textSecondary },
  reminder: { backgroundColor: colors.accentTint, borderColor: colors.accentPrimary },
  reminderText: { fontSize: 13, color: colors.textPrimary, fontWeight: '600' },
});
