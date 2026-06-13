/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        paper: "#FDF6EC",
        "paper-deep": "#F6E9D6",
        ink: "#3A3230",
        "ink-soft": "#7A6E66",
        terracotta: "#E8896B",
        "terracotta-deep": "#D26B4C",
        sage: "#8AA399",
      },
      fontFamily: {
        display: ['Fraunces', 'serif'],
        body: ['Quicksand', 'sans-serif'],
        hand: ['Caveat', 'cursive'],
      },
      boxShadow: {
        card: "0 1px 2px rgba(58,50,48,0.04), 0 8px 24px -12px rgba(58,50,48,0.18)",
        lift: "0 2px 4px rgba(58,50,48,0.06), 0 18px 40px -16px rgba(58,50,48,0.28)",
      },
    },
  },
  plugins: [],
};
