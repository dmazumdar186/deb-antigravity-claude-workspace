import type { Config } from 'tailwindcss';

const config: Config = {
  content: ['./app/**/*.{ts,tsx}', './components/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        ink: '#090a0c',
        paper: '#fcfaf5',
        gallery: '#f2efe8',
        steel: '#a6adb5',
      },
      fontFamily: {
        sans: [
          '-apple-system',
          'BlinkMacSystemFont',
          'Segoe UI',
          'Roboto',
          'Helvetica Neue',
          'Arial',
          'sans-serif',
        ],
        mono: [
          'ui-monospace',
          'SFMono-Regular',
          'Menlo',
          'Consolas',
          'Liberation Mono',
          'monospace',
        ],
      },
      maxWidth: {
        content: '1400px',
      },
      letterSpacing: {
        tightest2: '-0.05em',
        wide2: '0.14em',
      },
    },
  },
  plugins: [],
};

export default config;
