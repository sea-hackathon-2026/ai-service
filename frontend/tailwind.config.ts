import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      boxShadow: {
        live: "0 24px 70px rgba(15, 23, 42, 0.24)",
      },
      colors: {
        ink: "#0f172a",
        violetLive: "#8854f8",
      },
    },
  },
  plugins: [],
};

export default config;
