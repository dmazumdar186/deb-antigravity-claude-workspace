import { ExpoConfig, ConfigContext } from 'expo/config';

/**
 * Expo config (TypeScript form).
 *
 * Reads env vars from the shell / EAS / .env (via expo-constants).
 * Bundle IDs must be filled in before the first EAS build.
 */
export default ({ config }: ConfigContext): ExpoConfig => ({
  ...config,
  name: '{{APP_SLUG}}',
  slug: '{{APP_SLUG}}',
  version: '1.0.0',
  orientation: 'portrait',
  icon: './assets/icon.png',
  userInterfaceStyle: 'automatic',
  scheme: '{{APP_SLUG}}',
  ios: {
    supportsTablet: true,
    bundleIdentifier: process.env.IOS_BUNDLE_ID ?? 'com.example.{{APP_SLUG}}',
  },
  android: {
    package: process.env.ANDROID_PACKAGE ?? 'com.example.{{APP_SLUG}}',
    adaptiveIcon: {
      backgroundColor: '#E6F4FE',
      foregroundImage: './assets/android-icon-foreground.png',
      backgroundImage: './assets/android-icon-background.png',
      monochromeImage: './assets/android-icon-monochrome.png',
    },
    predictiveBackGestureEnabled: false,
  },
  web: {
    favicon: './assets/favicon.png',
  },
  plugins: [
    'expo-notifications',
    [
      '@sentry/react-native/expo',
      {
        organization: process.env.SENTRY_ORG,
        project: process.env.SENTRY_PROJECT,
      },
    ],
  ],
  extra: {
    apiBaseUrl: process.env.EXPO_PUBLIC_API_BASE_URL ?? 'http://localhost:8787',
    sentryDsn: process.env.EXPO_PUBLIC_SENTRY_DSN ?? '',
    posthogKey: process.env.EXPO_PUBLIC_POSTHOG_KEY ?? '',
    posthogHost: process.env.EXPO_PUBLIC_POSTHOG_HOST ?? 'https://eu.posthog.com',
    // easProjectId is written here by scaffold + `eas init`.
    eas: {
      projectId: process.env.EAS_PROJECT_ID ?? '',
    },
  },
  updates: {
    // Set to your Update URL once EAS Update is configured.
    url: process.env.EAS_UPDATE_URL,
  },
  runtimeVersion: {
    policy: 'appVersion',
  },
});
