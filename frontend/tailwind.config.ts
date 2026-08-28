import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#eef4ff",
          100: "#dbe7fe",
          500: "#3b6ef6",
          600: "#2952d6",
          700: "#213f9f",
        },
      },
    },
  },
  plugins: [],
};

export default config;
