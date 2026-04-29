/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans:    ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        display: ['"DM Sans"', 'ui-sans-serif', 'system-ui', 'sans-serif'],
      },
      colors: {
        brand: { DEFAULT: '#0075C9', dark: '#0067B1', light: '#2A8DD3' },
        scm: {
          primary:     '#0075C9',
          secondary:   '#007EA4',
          teal:        '#00AFAA',
          green:       '#86C057',
          forest:      '#006450',
          purple:      '#572F87',
          red:         '#EC0044',
          pink:        '#FB7598',
          yellow:      '#FFB700',
          /* legacy aliases kept for backward compat */
          accent:      '#00AFAA',
          success:     '#86C057',
          successDeep: '#006450',
          warning:     '#FFB700',
          danger:      '#EC0044',
          dangerSoft:  '#FB7598',
        },
        token: {
          bg:      '#F4F7FB',
          surface: '#FFFFFF',
          border:  '#DDE3ED',
        },
      },
    },
  },
  plugins: [],
}
