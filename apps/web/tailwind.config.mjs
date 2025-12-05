/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./app/**/*.{js,ts,jsx,tsx}",
    "./components/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          sky: "#38bdf8",
          purple: "#a855f7",
          emerald: "#10b981",
        },
        surface: {
          0: "#020617",
          1: "#0f172a",
          2: "#1e293b",
          3: "#334155",
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['JetBrains Mono', 'ui-monospace', 'SFMono-Regular', 'monospace'],
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'glow': 'glow 2s ease-in-out infinite alternate',
        'slide-up': 'slideUp 0.3s ease-out',
        'slide-in': 'slideIn 0.3s ease-out',
        'fade-in': 'fadeIn 0.4s ease-out',
        'scale-in': 'scaleIn 0.2s ease-out',
      },
      keyframes: {
        glow: {
          '0%': { boxShadow: '0 0 20px rgba(56, 189, 248, 0.3)' },
          '100%': { boxShadow: '0 0 40px rgba(56, 189, 248, 0.5), 0 0 60px rgba(56, 189, 248, 0.2)' },
        },
        slideUp: {
          '0%': { opacity: '0', transform: 'translateY(10px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        slideIn: {
          '0%': { opacity: '0', transform: 'translateX(-10px)' },
          '100%': { opacity: '1', transform: 'translateX(0)' },
        },
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        scaleIn: {
          '0%': { opacity: '0', transform: 'scale(0.95)' },
          '100%': { opacity: '1', transform: 'scale(1)' },
        },
      },
      backgroundImage: {
        'gradient-radial': 'radial-gradient(var(--tw-gradient-stops))',
        'gradient-conic': 'conic-gradient(from 180deg at 50% 50%, var(--tw-gradient-stops))',
        'mesh': 'radial-gradient(at 40% 20%, hsla(210, 100%, 16%, 1) 0px, transparent 50%), radial-gradient(at 80% 0%, hsla(220, 100%, 16%, 1) 0px, transparent 50%), radial-gradient(at 0% 50%, hsla(260, 100%, 16%, 1) 0px, transparent 50%)',
      },
      boxShadow: {
        'glow-sm': '0 0 15px rgba(56, 189, 248, 0.3)',
        'glow-md': '0 0 30px rgba(56, 189, 248, 0.4)',
        'glow-lg': '0 0 45px rgba(56, 189, 248, 0.5)',
        'glow-emerald': '0 0 30px rgba(16, 185, 129, 0.4)',
        'glow-amber': '0 0 30px rgba(245, 158, 11, 0.4)',
        'glow-rose': '0 0 30px rgba(244, 63, 94, 0.4)',
        'inner-glow': 'inset 0 1px 0 0 rgba(255, 255, 255, 0.05)',
      },
    },
  },
  plugins: [],
};
