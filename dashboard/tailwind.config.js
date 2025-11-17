/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./public/index.html",
    "./src/**/*.{js,jsx,ts,tsx}",
  ],
  safelist: [
    'bg-white',
    'text-slate-900',
    'antialiased'
  ],
  theme: {
    extend: {},
  },
  plugins: [],
};
