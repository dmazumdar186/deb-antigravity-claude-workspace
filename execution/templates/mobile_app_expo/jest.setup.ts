/**
 * Jest setup for React Native Testing Library.
 * Adds custom matchers and silences known no-op warnings.
 */
import '@testing-library/jest-native/extend-expect';

// Silence Reanimated warning in test env (harmless).
jest.mock('react-native-reanimated', () => {
  try {
    return require('react-native-reanimated/mock');
  } catch {
    return {};
  }
});

// Silence AsyncStorage warning in unit tests.
jest.mock('@react-native-async-storage/async-storage', () =>
  require('@react-native-async-storage/async-storage/jest/async-storage-mock'),
);
