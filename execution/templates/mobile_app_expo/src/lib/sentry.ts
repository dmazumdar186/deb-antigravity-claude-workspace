/**
 * Env-gated Sentry init.
 * When EXPO_PUBLIC_SENTRY_DSN is empty (dev/local), initSentry is a no-op and
 * wrapWithSentry returns the component unchanged. No runtime Sentry imports
 * happen on the free path.
 */
import Constants from 'expo-constants';
import type { ComponentType } from 'react';

const dsn: string = (Constants.expoConfig?.extra as { sentryDsn?: string })?.sentryDsn ?? '';

let SentryModule: typeof import('@sentry/react-native') | null = null;

export function initSentry(): void {
  if (!dsn) {
    // No-op in dev / when DSN is not set.
    return;
  }
  // Lazy import so bundlers don't pull the SDK on the free path.
  SentryModule = require('@sentry/react-native');
  SentryModule?.init({
    dsn,
    tracesSampleRate: 0.1,
    // enableAutoSessionTracking: true is default.
    debug: __DEV__,
  });
}

export function wrapWithSentry<P extends object>(Component: ComponentType<P>): ComponentType<P> {
  if (!dsn || !SentryModule) {
    return Component;
  }
  return SentryModule.wrap(Component);
}

export function captureException(err: unknown): void {
  if (!SentryModule) return;
  SentryModule.captureException(err);
}
