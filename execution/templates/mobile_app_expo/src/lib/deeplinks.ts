/**
 * Deep link + universal link config.
 *
 * URL scheme is set in app.config.ts (scheme: '{{APP_SLUG}}').
 * For iOS universal links + Android app links, additionally:
 *   - Host an `apple-app-site-association` JSON at your domain root
 *   - Host a `.well-known/assetlinks.json` for Android
 *   - Add `associatedDomains` to ios.entitlements and `intentFilters` to android
 *
 * See: https://docs.expo.dev/guides/deep-linking/
 */
import * as Linking from 'expo-linking';

export const prefixes = [
  Linking.createURL('/'),
  '{{APP_SLUG}}://',
  // Add production URL(s) here once the app has a hosted landing page:
  // 'https://{{APP_SLUG}}.example.com',
];

export const linkingConfig = {
  prefixes,
  config: {
    screens: {
      Home: '',
      // Add nested screens here as the app grows, e.g.:
      // Detail: 'item/:id',
    },
  },
};

/** Small helper for constructing outbound links (share sheets, notification payloads). */
export function makeLink(path: string = ''): string {
  return Linking.createURL(path);
}
