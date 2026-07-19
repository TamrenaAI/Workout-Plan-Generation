/**
 * Design tokens ported from the web app's Hevy-inspired theme
 * (frontend/src/theme.css, .superdesign/design-system.md) so the mobile
 * app stays visually consistent with the same brand — see
 * docs/superpowers/specs/2026-07-20-mobile-app-navigation-design.md.
 */

export const colors = {
  bgPrimary: '#FFFFFF',
  bgCard: '#FFFFFF',
  bgCardAlt: '#F4F5F6',
  bgInput: '#F4F5F6',

  accentPrimary: '#008CFF',
  accentTint: '#E6F3FF',

  textPrimary: '#191A1B',
  textSecondary: '#4A4E52',
  textMuted: '#83898F',
  textDisabled: '#C7CBCE',

  borderSubtle: '#EFF0F1',
  borderDefault: '#E4E6E9',

  success: '#16A34A',
  warning: '#EF9F27',
  danger: '#E24B4A',
} as const;

export const radii = {
  card: 16,
  badge: 20,
  button: 12,
  tile: 10,
} as const;

export const spacing = {
  screenPad: 20,
  cardPad: 18,
  gapCards: 12,
  gapInner: 8,
} as const;

export const typography = {
  fontFamily: undefined, // system default — matches the web app's Inter-first stack closely enough on-device
  title: { fontSize: 20, fontWeight: '600' as const },
  sectionTitle: { fontSize: 18, fontWeight: '700' as const },
  body: { fontSize: 15 },
  caption: { fontSize: 13, color: colors.textSecondary },
  label: { fontSize: 10, color: colors.textMuted, textTransform: 'uppercase' as const },
};
