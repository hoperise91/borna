import { defineConfig } from "astro/config";

// Static site. Romanian at /, English at /en/. Road data (PMTiles + JSON) is read from
// PUBLIC_DATA_URL: /data in development (web/public/data, built by `make tiles`), R2 in production.
export default defineConfig({
  output: "static",
  trailingSlash: "always",
  vite: {
    worker: { format: "es" }, // MapLibre's worker is an ES module
  },
});
