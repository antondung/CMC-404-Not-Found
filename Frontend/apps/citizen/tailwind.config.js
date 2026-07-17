/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
    "../../packages/ui-legal/**/*.{js,ts,jsx,tsx}"
  ],
  theme: {
    extend: {
      colors: {
        background: "#F8FAFC", // slate-50
        surface: "#FFFFFF",
        primary: "#0F172A",    // slate-900
        muted: "#64748B",      // slate-500
        border: "#E2E8F0",     // slate-200
        accent: "#2563EB",     // blue-600
        destructive: "#EF4444",// red-500
        success: "#10B981",    // emerald-500
        warning: "#F59E0B",    // amber-500
      },
      fontFamily: {
        sans: ['Inter', 'sans-serif'],
      },
      boxShadow: {
        'soft': '0 1px 3px 0 rgba(0, 0, 0, 0.05), 0 1px 2px -1px rgba(0, 0, 0, 0.03)',
        'card': '0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -2px rgba(0, 0, 0, 0.025)',
      }
    },
  },
  plugins: [],
}
