/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#080a0d",
        panel: "#0e1115",
        "panel-2": "#13171c",
        text: "#f3f5f1",
        muted: "#858e97",
        "muted-deep": "#4f5760",
        acid: "#c7ff38",
        red: "#ff555b",
      },
      fontFamily: {
        mono: ['"DM Mono"', "monospace"],
        sans: ['Manrope', "sans-serif"],
      },
      boxShadow: {
        glow: "0 0 10px rgba(199,255,56,0.5)",
        panel: "0 18px 50px -24px rgba(0,0,0,0.8)",
      },
    },
  },
  plugins: [],
};
