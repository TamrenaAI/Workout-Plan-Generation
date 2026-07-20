/** Mirrors api/routes/plan.py's generate_plan form fields exactly — the
 * PillSelect options each step offers are constrained to values the
 * backend already validates (VALID_EXPERIENCE, the 2-6 days range, the
 * "{n}min" duration pattern), so there's no client-side re-validation of
 * those to keep in sync. */
export interface IntakeData {
  goal: string;
  days_per_week: number;
  experience: 'beginner' | 'intermediate' | 'advanced';
  session_duration: string;
  injuries?: string;
  priority?: string;
  age?: number;
  sleep_quality?: 'good' | 'average' | 'poor';
  job_type?: 'desk' | 'light_physical' | 'heavy_physical';
  current_program?: string;
}

export interface CapturedImage {
  uri: string;
  mimeType: string;
}
