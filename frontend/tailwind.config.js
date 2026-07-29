/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        primary: {
          50: '#eff6ff', 100: '#dbeafe', 200: '#bfdbfe', 300: '#93c5fd',
          400: '#60a5fa', 500: '#3b82f6', 600: '#2563eb', 700: '#1d4ed8',
          800: '#1e40af', 900: '#1e3a8a',
        },
        ink: {
          50:  '#FAF6EE',
          100: '#F2E8D5',
          200: '#E8DEC6',
          300: '#D6CAB1',
          900: '#1F3D38',
          950: '#142824',
        },
        accent: {
          forest: '#1F4D3E',
          teal:   '#3D6B7A',
          amber:  '#E07A35',
          brick:  '#A8523A',
        },
      },
      fontFamily: {
        sans: ['"Plus Jakarta Sans"', '"Noto Sans SC"', 'system-ui', 'sans-serif'],
        serif: ['"Fraunces"', '"Noto Serif SC"', 'Georgia', 'serif'],
      },
      boxShadow: {
        'soft': '0 1px 2px rgba(60,40,20,0.04)',
        'card': '0 2px 8px rgba(60,40,20,0.06)',
        'lift': '0 12px 32px -10px rgba(60,40,20,0.18)',
      },
    },
  },
  plugins: [],
}