import { defineConfig } from 'astro/config';
import tailwind from '@astrojs/tailwind';
import sitemap from '@astrojs/sitemap';

export default defineConfig({
  site: 'https://yogaavecjitendra.fr',
  i18n: {
    defaultLocale: 'fr',
    locales: ['fr', 'en'],
    routing: { prefixDefaultLocale: false, redirectToDefaultLocale: false },
    // No fallback: if an EN page is missing we prefer a 404 over silently
    // serving French at /en/... which would poison Google's index.
  },
  integrations: [
    tailwind({ applyBaseStyles: false }),
    sitemap({
      i18n: {
        defaultLocale: 'fr',
        locales: { fr: 'fr-FR', en: 'en-US' },
      },
    }),
  ],
  build: { inlineStylesheets: 'auto' },
  vite: { build: { cssCodeSplit: false } },
});
