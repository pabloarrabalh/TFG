/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: [
    './index.html',
    './src/**/*.{js,jsx,ts,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        'primary': '#39ff14',
        'primary-dark': '#2ccb10',
        'background-dark': '#050505',
        'surface-dark': '#121212',
        'surface-dark-lighter': '#1e1e1e',
        'border-dark': '#262626',
        'surface-light': '#1a1a1a',
      },
      fontFamily: {
        display: ['Lexend', 'sans-serif'],
        body: ['Noto Sans', 'sans-serif'],
      },
      backgroundImage: {
        'gradient-radial': 'radial-gradient(var(--tw-gradient-stops))',
      },
      boxShadow: {
        'neon': '0 0 10px rgba(57,255,20,0.2), 0 0 20px rgba(57,255,20,0.1)',
        'neon-lg': '0 0 20px rgba(57,255,20,0.3), 0 0 40px rgba(57,255,20,0.15)',
      },
    },
  },
  plugins: [
    require('@tailwindcss/forms'),
  ],
}
