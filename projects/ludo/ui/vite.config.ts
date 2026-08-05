import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// The UI is a static transcript player (ADR-0003): no backend, no API keys,
// relative asset paths so the build runs from any directory or file:// URL.
export default defineConfig({
  plugins: [react()],
  base: "./",
  server: {
    fs: {
      // The committed fixtures live one directory up, in projects/ludo/games/.
      // They are imported ?raw so the built app works fully offline.
      allow: [".."],
    },
  },
  test: {
    environment: "jsdom",
  },
});
