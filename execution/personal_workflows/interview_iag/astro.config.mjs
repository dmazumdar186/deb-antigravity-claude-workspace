import { defineConfig } from 'astro/config';
import tailwind from '@astrojs/tailwind';
import react from '@astrojs/react';

export default defineConfig({
  site: 'https://agentup-iag.pages.dev',
  integrations: [
    tailwind({ applyBaseStyles: false }),
    react(),
  ],
  build: { inlineStylesheets: 'auto' },
  vite: {
    build: { cssCodeSplit: false },
    ssr: { noExternal: ['recharts'] },
  },
});
