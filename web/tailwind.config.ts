import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#1C211C",
        muted: "#5E675C",
        line: "#E4DED2",
        paper: "#F7F4EE",
        card: "#FFFcf7",
        forest: "#2C6A4A",
        forestDark: "#1F4C35",
        clay: "#C46B3A",
        gold: "#C6A15B",
      },
      fontFamily: {
        sans: ["var(--font-sans)", "system-ui", "sans-serif"],
        serif: ["var(--font-serif)", "Georgia", "serif"],
      },
      boxShadow: {
        card: "0 1px 0 rgba(28,33,28,0.04), 0 12px 32px -20px rgba(28,33,28,0.25)",
      },
    },
  },
  plugins: [],
};

export default config;
