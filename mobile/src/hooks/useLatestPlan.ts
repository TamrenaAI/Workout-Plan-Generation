import { useEffect, useState } from 'react';

import { ApiError } from '../api/client';
import { fetchSessionPlan } from '../api/plan';
import { fetchSessions, PlanSession } from '../api/sessions';
import { parsePlanMarkdown, PlanSection } from '../lib/parsePlan';

interface LatestPlanState {
  isLoading: boolean;
  error: string | null;
  session: PlanSession | null;
  status: 'ready' | 'pending' | null;
  /** Day sections only (dayNumber !== null), in the order they appear in the plan. */
  days: PlanSection[];
}

const INITIAL_STATE: LatestPlanState = {
  isLoading: true,
  error: null,
  session: null,
  status: null,
  days: [],
};

/** Shared by HomeScreen and WorkoutScreen — both need "the current plan's
 * training days," just for different amounts of detail. Fetches the most
 * recently generated session and parses its persisted weekly schedule
 * (GET /sessions/{id}/plan) rather than duplicating this fetch+parse in
 * each screen. */
export function useLatestPlan(): LatestPlanState {
  const [state, setState] = useState<LatestPlanState>(INITIAL_STATE);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const sessions = await fetchSessions();
        if (sessions.length === 0) {
          if (!cancelled) setState({ ...INITIAL_STATE, isLoading: false });
          return;
        }

        const latest = sessions[0];
        const response = await fetchSessionPlan(latest.session_id);
        const days = response.plan
          ? parsePlanMarkdown(response.plan).filter((s) => s.dayNumber !== null)
          : [];

        if (!cancelled) {
          setState({ isLoading: false, error: null, session: latest, status: response.status, days });
        }
      } catch (err) {
        if (!cancelled) {
          setState({
            ...INITIAL_STATE,
            isLoading: false,
            error: err instanceof ApiError ? err.message : 'Could not load your plan.',
          });
        }
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, []);

  return state;
}
