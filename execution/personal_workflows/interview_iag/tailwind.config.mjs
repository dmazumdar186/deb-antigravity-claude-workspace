/** @type {import('tailwindcss').Config} */
export default {
  content: ['./src/**/*.{astro,html,ts,tsx,js,jsx,md,mdx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // Brand palette — deep-tech / calm-focus. Interviewer-friendly:
        // reads as "serious enterprise product" but with warmth.
        ink:      { 50: '#F7F7F8', 100: '#EEEEF1', 200: '#D8D9E0', 300: '#B4B6C1',
                    500: '#6E7180', 700: '#3A3D48', 800: '#22242C', 900: '#12141A', 950: '#0A0B10' },
        indigo:   { 400: '#818CF8', 500: '#6366F1', 600: '#4F46E5', 700: '#4338CA' },
        emerald:  { 400: '#34D399', 500: '#10B981', 600: '#059669' },
        amber:    { 400: '#FBBF24', 500: '#F59E0B', 600: '#D97706' },
        rose:     { 400: '#FB7185', 500: '#F43F5E', 600: '#E11D48' },
      },
      fontFamily: {
        sans:    ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        display: ['"Bricolage Grotesque"', 'Inter', 'ui-sans-serif', 'sans-serif'],
        mono:    ['"JetBrains Mono"', 'ui-monospace', 'monospace'],
      },
      animation: {
        'pulse-soft':  'pulse-soft 2.4s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'slide-up':    'slide-up 0.4s cubic-bezier(0.16, 1, 0.3, 1)',
        'fade-in':     'fade-in 0.3s ease-out',
        'score-count': 'score-count 1.2s cubic-bezier(0.16, 1, 0.3, 1)',
      },
      keyframes: {
        'pulse-soft': {
          '0%, 100%': { opacity: '1', transform: 'scale(1)' },
          '50%':      { opacity: '0.7', transform: 'scale(1.03)' },
        },
        'slide-up':   { '0%': { opacity: '0', transform: 'translateY(8px)' },
                        '100%': { opacity: '1', transform: 'translateY(0)' } },
        'fade-in':    { '0%': { opacity: '0' }, '100%': { opacity: '1' } },
        'score-count': { '0%': { transform: 'scale(0.9)', opacity: '0' },
                         '60%': { transform: 'scale(1.05)' },
                         '100%': { transform: 'scale(1)', opacity: '1' } },
      },
    },
  },
};
