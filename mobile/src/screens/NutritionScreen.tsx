import React from 'react';
import { ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Card } from '../components/Card';
import { GhostButton } from '../components/Buttons';
import { StatTile } from '../components/StatTile';
import { colors, spacing } from '../theme';

// Mock content — the Nutrition Agent integration (external repo, on hold
// per project decision) will supply real meals/macros once its contract
// is agreed.
const MEALS = [
  { name: 'Breakfast', desc: 'Oats, eggs, banana', kcal: '520 kcal' },
  { name: 'Lunch', desc: 'Chicken, rice, greens', kcal: '680 kcal' },
  { name: 'Dinner', desc: 'Salmon, potatoes, salad', kcal: '710 kcal' },
  { name: 'Snack', desc: 'Greek yogurt, almonds', kcal: '340 kcal' },
];

export function NutritionScreen() {
  return (
    <SafeAreaView style={styles.safeArea} edges={['top']}>
      <ScrollView contentContainerStyle={styles.content}>
        <Text style={styles.title}>Nutrition</Text>

        <Card>
          <View style={styles.statRow}>
            <StatTile value="2,450" label="kcal" />
            <StatTile value="180g" label="Pro" />
            <StatTile value="220g" label="Carb" />
            <StatTile value="75g" label="Fat" />
          </View>
        </Card>

        <Text style={styles.sectionTitle}>Today's Meals</Text>
        {MEALS.map((m) => (
          <Card key={m.name}>
            <Text style={styles.mealName}>{m.name}</Text>
            <Text style={styles.mealDesc}>{m.desc}</Text>
            <Text style={styles.mealKcal}>{m.kcal}</Text>
          </Card>
        ))}

        <GhostButton label="Regenerate Plan" style={{ marginTop: spacing.gapCards }} />
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: colors.bgPrimary },
  content: { padding: spacing.screenPad, paddingBottom: 120 },
  title: { fontSize: 24, fontWeight: '700', color: colors.textPrimary, marginBottom: 16 },
  statRow: { flexDirection: 'row', gap: 12 },
  sectionTitle: { fontSize: 18, fontWeight: '700', color: colors.textPrimary, marginVertical: 12 },
  mealName: { fontSize: 16, fontWeight: '600', color: colors.textPrimary },
  mealDesc: { fontSize: 13, color: colors.textSecondary, marginTop: 4 },
  mealKcal: { fontSize: 12, color: colors.textMuted, marginTop: 6, fontWeight: '600' },
});
