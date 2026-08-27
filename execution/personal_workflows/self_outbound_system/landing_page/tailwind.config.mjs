/** @type {import('tailwindcss').Config} */
export default {
  content: ['./src/**/*.{astro,html,ts,tsx,js,jsx,md,mdx}'],
  theme: {
    extend: {
      colors: {
        // Restrained professional palette.
        // Deep neutrals + warm amber accent (per operator brief:
        // "warm accent like amber-500, NOT startup-blue").
        paper:  { 50: '#FAFAF7', 100: '#F5F4EF', 200: '#EAE8DF' },
        ink:    { 500: '#4B4740', 700: '#2B2924', 800: '#1E1D19', 900: '#141311' },
        accent: { 400: '#F5B84A', 500: '#E39F1F', 600: '#C08211' },
        rule:   { DEFAULT: 'rgba(30, 29, 25, 0.10)' },
      },
      fontFamily: {
        // Bricolage Grotesque (body) + Newsreader (headers) - a distinctive
        // editorial pair with quiet personality. Chosen over Inter/Fraunces
        // and Instrument Sans/Serif which are increasingly common across
        // AI-generated UIs.
        serif: ['Newsreader', 'Cormorant Garamond', 'Georgia', 'serif'],
        sans:  ['Bricolage Grotesque', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        mono:  ['ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
      },
      maxWidth: {
        prose2: '68ch',
        wrap:   '1120px',
      },
    },
  },
};
