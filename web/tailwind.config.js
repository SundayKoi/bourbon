/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bourbon: {
          50: "#fdf6ec",
          100: "#f8e4c3",
          500: "#c4892a",
          700: "#8b5e15",
          900: "#4a2f08",
        },
      },
      fontFamily: {
        display: ["Georgia", "serif"],
      },
    },
  },
  plugins: [],
};
