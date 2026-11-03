/** @type {import('tailwindcss').Config} */
export default {
  content: ['./src/**/*.{astro,html,ts,tsx,js,jsx,md,mdx}'],
  theme: {
    extend: {
      colors: {
        cream:      { 50: '#FBF7EE', 100: '#F4EDE1', 200: '#E9DFCB', 300: '#D9C7A7' },
        sand:       { 400: '#C9B48A', 500: '#B39B6D' },
        terracotta: { 400: '#D68A63', 500: '#C9744A', 600: '#A85D37' },
        sage:       { 400: '#8B9A7A', 500: '#6B7A5A', 600: '#525E44' },
        ink:        { 700: '#4A423B', 800: '#2E2A26', 900: '#1C1A17' },
      },
      fontFamily: {
        serif: ['Fraunces', 'Cormorant Garamond', 'Georgia', 'serif'],
        sans:  ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
      },
      maxWidth: {
        prose2: '68ch',
      },
    },
  },
};
