/** @type {import('tailwindcss').Config} */
export default {
  content: ['./src/**/*.{astro,html,ts,tsx,js,jsx,md,mdx}'],
  theme: {
    extend: {
      colors: {
        bone: {
          50:  '#fcfbf8',
          100: '#f7f3ec',
          200: '#ede6d6',
          300: '#ddd2b8',
          400: '#beae8a',
        },
        ink: {
          700: '#3d4148',
          800: '#25282e',
          900: '#16181c',
          950: '#0e0f12',
        },
        brass: {
          300: '#dec487',
          400: '#c8a35c',
          500: '#aa8638',
          600: '#8a6a26',
        },
      },
      fontFamily: {
        serif: ['Newsreader', 'ui-serif', 'Georgia', 'serif'],
        sans: ['Geist', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'Menlo', 'monospace'],
      },
      letterSpacing: {
        tightest: '-0.04em',
      },
      opacity: {
        8: '0.08',
        15: '0.15',
        18: '0.18',
      },
      borderOpacity: {
        8: '0.08',
        10: '0.10',
      },
      backgroundOpacity: {
        8: '0.08',
      },
    },
  },
};
