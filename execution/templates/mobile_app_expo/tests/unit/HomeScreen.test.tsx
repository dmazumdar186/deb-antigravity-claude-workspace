/**
 * HomeScreen unit test — proves the full stack renders under a QueryClient.
 * Mocks the api layer so no network hits happen.
 */
import React from 'react';
import { render, waitFor } from '@testing-library/react-native';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { HomeScreen } from '@/screens/HomeScreen';

jest.mock('@/services/api', () => ({
  getHealth: jest.fn().mockResolvedValue({
    ok: true,
    version: 'test-1.0.0',
    ts: 1_700_000_000_000,
  }),
}));

function wrap(children: React.ReactNode) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

describe('HomeScreen', () => {
  it('renders app slug title', () => {
    const { getByTestId } = render(wrap(<HomeScreen />));
    expect(getByTestId('home-screen')).toBeTruthy();
  });

  it('shows the health payload after fetch', async () => {
    const { getByTestId, findByTestId } = render(wrap(<HomeScreen />));
    expect(getByTestId('loading-indicator')).toBeTruthy();
    const payload = await findByTestId('health-payload');
    await waitFor(() => {
      expect(payload).toBeTruthy();
    });
  });
});
