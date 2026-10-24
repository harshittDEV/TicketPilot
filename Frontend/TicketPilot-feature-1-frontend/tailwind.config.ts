import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: {
          DEFAULT: "#FAF8F5", // Warm ivory/pearl
          subtle: "#F4F0E8",
          warm: "#EDE6D8",
        },
        surface: {
          DEFAULT: "#FFFFFF",
          elevated: "#FFFFFF",
          dim: "#F8F6F0",
        },
        glass: {
          surface: "rgba(255, 255, 255, 0.72)",
          "surface-strong": "rgba(255, 255, 255, 0.88)",
          subtle: "rgba(255, 255, 255, 0.5)",
          border: "rgba(230, 222, 210, 0.65)",
          highlight: "rgba(255, 255, 255, 0.9)",
          dark: "rgba(33, 43, 38, 0.05)",
        },
        ink: {
          DEFAULT: "#18221D", // Deep ink
          muted: "#4A5A52",
          subtle: "#6B7C73",
          faint: "#8C9D94",
        },
        accent: {
          emerald: "#1B5E3C", // Botanical green / emerald accent
          "emerald-light": "#E8F5EE",
          "emerald-hover": "#14482E",
          sky: "#0284C7", // Soft sky blue
          "sky-light": "#E0F2FE",
          coral: "#E05D44", // Restrained peach/warm coral
          "coral-light": "#FEECE8",
          lavender: "#7C6A96", // Muted lavender secondary accent
          "lavender-light": "#F2EFF7",
        },
        railway: {
          ac: "#0D5C3A",
          nonac: "#B45309",
        },
        semantic: {
          success: "#166534",
          "success-bg": "#DCFCE7",
          warning: "#B45309",
          "warning-bg": "#FEF3C7",
          error: "#B91C1C",
          "error-bg": "#FEE2E2",
          info: "#0369A1",
          "info-bg": "#E0F2FE",
        },
      },
      boxShadow: {
        glass: "0 8px 32px 0 rgba(31, 38, 135, 0.06), 0 1px 2px 0 rgba(0, 0, 0, 0.03)",
        "glass-hover": "0 14px 38px 0 rgba(31, 38, 135, 0.1), 0 2px 4px 0 rgba(0, 0, 0, 0.04)",
        "glass-card": "0 4px 20px -2px rgba(27, 43, 35, 0.05), inset 0 1px 0 0 rgba(255, 255, 255, 0.8)",
        "glass-elevated": "0 16px 40px -4px rgba(27, 43, 35, 0.08), inset 0 1px 0 0 rgba(255, 255, 255, 0.9)",
      },
      backdropBlur: {
        xs: "2px",
        glass: "14px",
      },
      fontFamily: {
        sans: ["system-ui", "-apple-system", "BlinkMacSystemFont", "'Segoe UI'", "Roboto", "sans-serif"],
        serif: ["'Instrument Serif'", "'Newsreader'", "Georgia", "serif"],
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "Monaco", "Consolas", "monospace"],
      },
      animation: {
        "float-gentle": "floatGentle 6s ease-in-out infinite",
        "pulse-subtle": "pulseSubtle 3s ease-in-out infinite",
      },
      keyframes: {
        floatGentle: {
          "0%, 100%": { transform: "translateY(0px)" },
          "50%": { transform: "translateY(-4px)" },
        },
        pulseSubtle: {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.7" },
        },
      },
    },
  },
  plugins: [],
};

export default config;
