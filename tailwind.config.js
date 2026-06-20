/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: 'class',
  content: [
    './templates/**/*.html',
    './apps/**/*.html',
  ],
  theme: {
    extend: {
      colors: {
        primary: '#7c6cff',
        'primary-2': '#a78bfa',
      },
    },
  },
}
