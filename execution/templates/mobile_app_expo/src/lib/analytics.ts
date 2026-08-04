/**
 * Env-gated analytics (PostHog).
 * When EXPO_PUBLIC_POSTHOG_KEY is empty, initAnalytics is a no-op and
 * capture() silently drops events. No SDK calls happen without a key.
 */
import Constants from 'expo-constants';

type Extra = { posthogKey?: string; posthogHost?: string };
const extra: Extra = (Constants.expoConfig?.extra as Extra) ?? {};
const apiKey = extra.posthogKey ?? '';
const host = extra.posthogHost ?? 'https://eu.posthog.com';

let client: any = null;

export async function initAnalytics(): Promise<void> {
  if (!apiKey) return;
  try {
    const { PostHog } = await import('posthog-react-native');
    client = await PostHog.initAsync(apiKey, { host });
  } catch (err) {
    // Analytics init failing must never crash the app. Log and continue.
    // eslint-disable-next-line no-console
    console.warn('[analytics] init failed, continuing without analytics:', err);
  }
}

export function capture(event: string, properties?: Record<string, unknown>): void {
  if (!client) return;
  try {
    client.capture(event, properties);
  } catch {
    // Same defensive posture as init.
  }
}

export function identify(userId: string, traits?: Record<string, unknown>): void {
  if (!client) return;
  try {
    client.identify(userId, traits);
  } catch {
    // Non-fatal.
  }
}
