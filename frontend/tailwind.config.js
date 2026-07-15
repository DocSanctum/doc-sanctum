/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{vue,ts}'],
  safelist: ['prose-sm', 'prose-base', 'prose-lg'],
  darkMode: 'class',
  theme: {
    extend: {
      // Route the gray scale through CSS variables (defined per app theme in
      // style.css) so 'dark-gray' and 'black' can retarget every existing
      // `dark:bg-gray-900`-style class without touching component templates.
      colors: {
        gray: {
          50: 'rgb(var(--ds-gray-50) / <alpha-value>)',
          100: 'rgb(var(--ds-gray-100) / <alpha-value>)',
          200: 'rgb(var(--ds-gray-200) / <alpha-value>)',
          300: 'rgb(var(--ds-gray-300) / <alpha-value>)',
          400: 'rgb(var(--ds-gray-400) / <alpha-value>)',
          500: 'rgb(var(--ds-gray-500) / <alpha-value>)',
          600: 'rgb(var(--ds-gray-600) / <alpha-value>)',
          700: 'rgb(var(--ds-gray-700) / <alpha-value>)',
          800: 'rgb(var(--ds-gray-800) / <alpha-value>)',
          900: 'rgb(var(--ds-gray-900) / <alpha-value>)',
          950: 'rgb(var(--ds-gray-950) / <alpha-value>)',
        },
      },
      typography: {
        DEFAULT: {
          css: {
            maxWidth: 'none',
          },
        },
      },
    },
  },
  plugins: [require('@tailwindcss/typography')],
}
