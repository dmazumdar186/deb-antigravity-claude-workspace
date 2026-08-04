import React from 'react';
import { View, Text, StyleSheet, ActivityIndicator } from 'react-native';
import { useApiHealth } from '@/hooks/useApiHealth';

/**
 * Starter screen. Wires the whole stack:
 *   PersistQueryClientProvider -> useQuery -> api.ts -> paired backend /api/health.
 *
 * Replace with your real screens; keep the same wiring pattern.
 */
export function HomeScreen() {
  const { data, isLoading, error } = useApiHealth();

  return (
    <View style={styles.container} testID="home-screen">
      <Text style={styles.title}>{'{{APP_SLUG}}'}</Text>

      {isLoading && <ActivityIndicator testID="loading-indicator" />}

      {error && (
        <Text style={styles.error} testID="error-message">
          Backend unreachable: {error.message}
        </Text>
      )}

      {data && (
        <View testID="health-payload">
          <Text style={styles.line}>ok: {String(data.ok)}</Text>
          <Text style={styles.line}>version: {data.version}</Text>
          <Text style={styles.line}>ts: {new Date(data.ts).toISOString()}</Text>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    padding: 24,
    justifyContent: 'center',
    alignItems: 'center',
  },
  title: {
    fontSize: 24,
    fontWeight: '600',
    marginBottom: 24,
  },
  line: {
    fontSize: 14,
    marginVertical: 2,
  },
  error: {
    color: '#c33',
    fontSize: 14,
  },
});
