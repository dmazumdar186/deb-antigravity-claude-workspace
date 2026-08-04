/**
 * API client for the paired backend.
 *
 * Mirrors the shape of the Phase 4a web template's `functions/api/` handlers
 * so mobile + web speak the same wire format.
 *
 * Two backend tracks are supported per directives/mobile_apps/:
 *   - cf_modal: Cloudflare Worker at $EXPO_PUBLIC_API_BASE_URL
 *   - supabase: Supabase Edge Function at $EXPO_PUBLIC_API_BASE_URL
 *
 * The reference endpoints assumed here (change per app):
 *   GET  /api/health   -> { ok: boolean, version: string, ts: number }
 *   POST /api/echo     -> mirrors body for smoke testing
 */
import axios, { AxiosInstance } from 'axios';
import Constants from 'expo-constants';
import { captureException } from '@/lib/sentry';

const baseURL: string =
  (Constants.expoConfig?.extra as { apiBaseUrl?: string })?.apiBaseUrl ??
  'http://localhost:8787';

export const api: AxiosInstance = axios.create({
  baseURL,
  timeout: 10_000,
  headers: {
    'Content-Type': 'application/json',
  },
});

api.interceptors.response.use(
  (r) => r,
  (err) => {
    // Report but rethrow — callers still handle.
    captureException(err);
    return Promise.reject(err);
  },
);

// ---- Reference endpoints ----

export type HealthResponse = {
  ok: boolean;
  version: string;
  ts: number;
};

export async function getHealth(): Promise<HealthResponse> {
  const { data } = await api.get<HealthResponse>('/api/health');
  return data;
}

export async function postEcho<T extends Record<string, unknown>>(body: T): Promise<T> {
  const { data } = await api.post<T>('/api/echo', body);
  return data;
}
