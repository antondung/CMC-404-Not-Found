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
        background: "#f8f9fa",
        surface: "#ffffff",
        primary: "#344767", // dark blue/gray for text
        muted: "#8392ab",
        border: "#e9ecef",
        accent: "#cb0c9f", // Soft UI primary pink/purple
        secondaryAccent: "#17c1e8", // Soft UI info blue
        destructive: "#ea0606",
        success: "#82d616",
        warning: "#fbcf33",
      },
      fontFamily: {
        sans: ['Inter', 'sans-serif'],
      },
      boxShadow: {
        'soft': '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)',
        'card': '0 20px 27px 0 rgba(0, 0, 0, 0.05)',
      },
      backgroundImage: {
        'gradient-accent': 'linear-gradient(310deg, #7928ca, #ff0080)',
        'gradient-info': 'linear-gradient(310deg, #2152ff, #21d4fd)',
        'gradient-success': 'linear-gradient(310deg, #17ad37, #98ec2d)',
        'gradient-warning': 'linear-gradient(310deg, #f53939, #fbcf33)',
        'gradient-danger': 'linear-gradient(310deg, #ea0606, #ff667c)',
        'gradient-dark': 'linear-gradient(310deg, #141727, #3a416f)',
      },
      keyframes: {
        'fade-in-up': {
          '0%': { opacity: '0', transform: 'translateY(15px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
      },
      animation: {
        'fade-in-up': 'fade-in-up 0.5s ease-out forwards',
      }
    },
  },
  plugins: [],
}
