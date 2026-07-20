import { apiFetch } from './client';

export type Difficulty = 'too_easy' | 'just_right' | 'too_hard';

export interface ExerciseFeedbackInput {
  name: string;
  completed: boolean;
  difficulty: Difficulty;
  pain: boolean;
  note?: string;
}

export interface WorkoutFeedbackResult {
  feedback_recorded: boolean;
  adjustment_triggered: boolean;
  summary: string | null;
}

/** Calls the existing POST /workouts/{session_id}/feedback (api/routes/workouts.py) —
 * no backend changes accompany this client. If nothing in `exercises` is flagged
 * (all just_right/no pain), the backend responds fast with adjustment_triggered:
 * false and no agent runs; otherwise this call blocks on a real Plan Adjuster
 * run and can take from a few seconds to over a minute. */
export function submitWorkoutFeedback(
  sessionId: string,
  dayLabel: string,
  exercises: ExerciseFeedbackInput[],
): Promise<WorkoutFeedbackResult> {
  return apiFetch<WorkoutFeedbackResult>(`/workouts/${sessionId}/feedback`, {
    method: 'POST',
    body: { day_label: dayLabel, exercises },
  });
}
