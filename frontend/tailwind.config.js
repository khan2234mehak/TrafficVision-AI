const c = (v) => `rgb(var(--${v}) / <alpha-value>)`;
/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: ["class", '[data-theme="dark"]'],
  theme: {
    extend: {
      colors: {
        bg: c("bg"), surface: c("surface"), raised: c("raised"), line: c("line"),
        ink: c("ink"), muted: c("muted"), brand: c("brand"), cyan: c("cyan"),
        ok: c("ok"), warn: c("warn"), danger: c("danger"), orange: c("orange"),
      },
      fontFamily: {
        display: ['"Sora"', "system-ui", "sans-serif"],
        sans: ['"IBM Plex Sans"', "system-ui", "sans-serif"],
      },
      boxShadow: { panel: "0 1px 0 rgb(var(--line) / .6), 0 12px 32px -18px rgb(0 0 0 / .55)" },
    },
  },
  plugins: [],
};
