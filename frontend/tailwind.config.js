/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#f4f4f4",
          100: "#c67bdf",
          200: "#adefee",
          300: "#8727c9",
          400: "#c20ffe",
          500: "#970efe",
          600: "#6705f6",
          700: "#7d0afb",
          800: "#e00fff",
          900: "#010101",
          950: "#010101",
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};
