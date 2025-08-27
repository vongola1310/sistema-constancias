/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './templates/**/*.html',
    './users/templates/**/*.html',
  ],
  theme: {
    extend: {
      colors: {
        'empresa-green': '#74C054',
      }
    },
  },
  plugins: [],
}