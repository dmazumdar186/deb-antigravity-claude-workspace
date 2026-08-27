import { defineConfig } from 'astro/config';
import tailwind from '@astrojs/tailwind';
import sitemap from '@astrojs/sitemap';

export default defineConfig({
  site: 'https://debanjanm.com',
  integrations: [
    tailwind({ applyBaseStyles: false }),
    sitemap(),
  ],
  build: { inlineStylesheets: 'auto' },
  vite: { build: { cssCodeSplit: false } },
});
