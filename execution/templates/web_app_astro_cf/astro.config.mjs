import { defineConfig } from 'astro/config';
import tailwind from '@astrojs/tailwind';
import sitemap from '@astrojs/sitemap';

// Astro 5.x + Cloudflare Pages reference config.
// - i18n scaffold: FR default, EN mirror under /en. Delete i18n block if
//   the project is monolingual.
// - inlineStylesheets:auto keeps first-paint fast without ballooning HTML.
// - Set `site` to the live production URL BEFORE first deploy (used by
//   sitemap + canonical link + open-graph).
export default defineConfig({
  site: 'https://<PROJECT_DOMAIN>',
  i18n: {
    defaultLocale: 'fr',
    locales: ['fr', 'en'],
    routing: { prefixDefaultLocale: false, redirectToDefaultLocale: false },
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
