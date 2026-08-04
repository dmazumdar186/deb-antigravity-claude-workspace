/**
 * useApiHealth — reference react-query hook.
 * Demonstrates: react-query + typed api client + offline-persistent cache.
 */
import { useQuery } from '@tanstack/react-query';
import { getHealth, type HealthResponse } from '@/services/api';

export function useApiHealth() {
  return useQuery<HealthResponse, Error>({
    queryKey: ['health'],
    queryFn: getHealth,
    refetchInterval: 1000 * 60, // poll every minute while foregrounded
  });
}
