import { apiFetch } from './client';
import { API_BASE_URL } from '../config';

export interface ExerciseMedia {
  name: string;
  target_muscle: string | null;
  equipment: string | null;
  instructions: string | null;
  image_url: string | null;
  gif_url: string | null;
  attribution: string | null;
}

/** Looks up an exercise's GIF/instructions by name against the real
 * exercises-dataset catalog. The plan's exercise names come from an
 * LLM-generated markdown table with no exercise ID, so the backend
 * matches by fuzzy token overlap — a name the catalog has no good
 * equivalent for (e.g. "Face Pull") 404s rather than returning the wrong
 * exercise's media, so callers should treat a thrown ApiError as "no
 * preview available" rather than a hard failure. */
export function fetchExerciseMedia(name: string): Promise<ExerciseMedia> {
  return apiFetch<ExerciseMedia>(`/exercises/lookup?name=${encodeURIComponent(name)}`);
}

/** gif_url/image_url from fetchExerciseMedia are paths relative to the API
 * origin (e.g. "/media/exercises/gifs/0025-xyz.gif") — join with the API
 * base to get a URI an <Image> component can load. */
export function resolveExerciseMediaUrl(path: string): string {
  return `${API_BASE_URL}${path}`;
}
