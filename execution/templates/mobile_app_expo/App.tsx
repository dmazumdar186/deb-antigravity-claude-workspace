import React, { useEffect } from 'react';
import { StatusBar } from 'expo-status-bar';
import { PersistQueryClientProvider } from '@tanstack/react-query-persist-client';
import { queryClient, asyncStoragePersister } from '@/lib/query-client';
import { initSentry, wrapWithSentry } from '@/lib/sentry';
import { initAnalytics } from '@/lib/analytics';
import { HomeScreen } from '@/screens/HomeScreen';

/**
 * Root component.
 * Sets up: react-query (offline-persistent), Sentry (env-gated), PostHog (env-gated).
 */
function App() {
  useEffect(() => {
    initSentry();
    initAnalytics();
  }, []);

  return (
    <PersistQueryClientProvider
      client={queryClient}
      persistOptions={{ persister: asyncStoragePersister }}
    >
      <HomeScreen />
      <StatusBar style="auto" />
    </PersistQueryClientProvider>
  );
}

// Sentry wraps the root; no-op if DSN absent.
export default wrapWithSentry(App);
