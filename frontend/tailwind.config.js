/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        base: '#0B1020',
        'bg-card': '#121826',
        'bg-card-elevated': '#1a2235',
        'bg-sidebar': '#0d1525',
        primary: '#4F7CFF',
        success: '#22C55E',
        danger: '#EF4444',
        warning: '#F59E0B',
        'text-primary': '#F1F5F9',
        'text-secondary': '#94A3B8',
        'text-muted': '#475569',
        border: {
          DEFAULT: 'rgba(255,255,255,0.06)',
          hover: 'rgba(255,255,255,0.12)',
        },
      },
      fontFamily: {
        sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'sans-serif'],
        mono: ['"JetBrains Mono"', '"Fira Code"', 'monospace'],
      },
      animation: {
        shimmer: 'shimmer 1.5s infinite',
        'fade-in-up': 'fadeInUp 0.3s ease-out forwards',
        'live-blink': 'live-blink 1.4s ease-in-out infinite',
        'pulse-primary': 'pulse-primary 2s ease-in-out infinite',
        'pulse-success': 'pulse-success 2s ease-in-out infinite',
        'pulse-danger': 'pulse-danger 2s ease-in-out infinite',
      },
      keyframes: {
        shimmer: {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
        fadeInUp: {
          from: { opacity: '0', transform: 'translateY(12px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
        'live-blink': {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.3' },
        },
        'pulse-primary': {
          '0%, 100%': { boxShadow: '0 0 0 0 rgba(79,124,255,0.4)' },
          '50%': { boxShadow: '0 0 0 6px rgba(79,124,255,0)' },
        },
        'pulse-success': {
          '0%, 100%': { boxShadow: '0 0 0 0 rgba(34,197,94,0.4)' },
          '50%': { boxShadow: '0 0 0 6px rgba(34,197,94,0)' },
        },
        'pulse-danger': {
          '0%, 100%': { boxShadow: '0 0 0 0 rgba(239,68,68,0.4)' },
          '50%': { boxShadow: '0 0 0 6px rgba(239,68,68,0)' },
        },
      },
      boxShadow: {
        card: '0 4px 24px rgba(0,0,0,0.4)',
        'card-lg': '0 8px 32px rgba(0,0,0,0.5)',
        'primary-glow': '0 0 0 1px rgba(79,124,255,0.2), 0 8px 32px rgba(79,124,255,0.08)',
        'success-glow': '0 0 0 1px rgba(34,197,94,0.2), 0 8px 32px rgba(34,197,94,0.08)',
        'danger-glow': '0 0 0 1px rgba(239,68,68,0.2), 0 8px 32px rgba(239,68,68,0.08)',
      },
    },
  },
  plugins: [],
};
