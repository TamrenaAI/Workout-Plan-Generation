import { apiFetch } from './client';

// SQLite stores booleans as 0/1 (see pipeline/inbody_history.py) and the
// route returns the raw dict — these come through the API as 0 | 1, not
// true/false. Coerce with Boolean(...) wherever displayed.
export interface InBodyScan {
  id: number;
  session_id: string | null;
  skeletal_muscle_mass_kg: number;
  body_fat_percent: number;
  bmr_kcal: number | null;
  arm_asymmetry: 0 | 1;
  arm_diff_grams: number;
  leg_asymmetry: 0 | 1;
  leg_diff_grams: number;
  elevated_bf: 0 | 1;
  trunk_underdeveloped: 0 | 1;
  created_at: string;
}

export interface ScanComparison {
  latest: InBodyScan;
  previous: InBodyScan;
  delta: {
    skeletal_muscle_mass_kg: number;
    body_fat_percent: number;
    arm_asymmetry_resolved: boolean;
    leg_asymmetry_resolved: boolean;
    trunk_underdeveloped_resolved: boolean;
  };
}

export function fetchScanHistory(): Promise<InBodyScan[]> {
  return apiFetch<{ scans: InBodyScan[] }>('/progress/scans').then((r) => r.scans);
}

/** null until the user has a second scan to compare against. */
export function fetchLatestComparison(): Promise<ScanComparison | null> {
  return apiFetch<{ comparison: ScanComparison | null }>('/progress/comparison').then((r) => r.comparison);
}
