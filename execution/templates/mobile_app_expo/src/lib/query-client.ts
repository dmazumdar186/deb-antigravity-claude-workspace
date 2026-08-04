/**
 * react-query client with AsyncStorage persistence.
 * Offline-first default: cache survives app restarts; stale-while-revalidate on refetch.
 */
import AsyncStorage from '@react-native-async-storage/async-storage';
import { QueryClient } from '@tanstack/react-query';
import { createAsyncStoragePersister } from '@tanstack/query-async-storage-persister';

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Keep cached data available for 24h even when stale.
      gcTime: 1000 * 60 * 60 * 24,
      // Consider data fresh for 5 min before background refetch.
      staleTime: 1000 * 60 * 5,
      retry: 2,
      refetchOnWindowFocus: false,
    },
  },
});

export const asyncStoragePersister = createAsyncStoragePersister({
  storage: AsyncStorage,
  key: '{{APP_SLUG}}-query-cache',
  throttleTime: 1000,
});
