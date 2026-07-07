import { defineConfig } from 'astro/config';
import tailwind from '@astrojs/tailwind';

export default defineConfig({
  site: 'https://yoga-jitendra.pages.dev',
  integrations: [tailwind({ applyBaseStyles: false })],
  build: { inlineStylesheets: 'auto' },
  vite: { build: { cssCodeSplit: false } },
});
