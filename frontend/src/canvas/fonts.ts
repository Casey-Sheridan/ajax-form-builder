export interface FontDef {
  family: string;
  /** "local" = TTF file lives in backend/assets/fonts; "google" = fetched from Google Fonts */
  source: "local" | "google";
}

export const APPROVED_FONTS: FontDef[] = [
  // ── Local (backend TTF files already present) ──────────────────────────────
  { family: "Montserrat", source: "local" },
  { family: "Liberation Sans", source: "local" },
  { family: "Orbitron", source: "local" },

  // ── Google Fonts ───────────────────────────────────────────────────────────
  { family: "Inter", source: "google" },
  { family: "Roboto", source: "google" },
  { family: "Open Sans", source: "google" },
  { family: "Lato", source: "google" },
  { family: "Poppins", source: "google" },
  { family: "Raleway", source: "google" },
  { family: "Oswald", source: "google" },
  { family: "Barlow Condensed", source: "google" },
  { family: "Bebas Neue", source: "google" },
  { family: "Playfair Display", source: "google" },
  { family: "Merriweather", source: "google" },
  { family: "Space Mono", source: "google" },
];

export const LOCAL_FONTS = APPROVED_FONTS.filter((f) => f.source === "local");

/** Local fonts that are NOT available on Google Fonts and must be served from the backend. */
export const BACKEND_FONTS: { family: string; regular: string; bold: string }[] = [
  {
    family: "Liberation Sans",
    regular: "LiberationSans-Regular.ttf",
    bold: "LiberationSans-Bold.ttf",
  },
];

/** Fonts loaded from Google — includes Montserrat + Orbitron for browser preview */
export const GOOGLE_LOADABLE_FONTS = APPROVED_FONTS.filter(
  (f) => f.source === "google" || f.family === "Montserrat" || f.family === "Orbitron"
);

export const DEFAULT_FONT_FAMILY = "Montserrat";

/** Build a single Google Fonts CSS URL for all loadable fonts (400 + 700 weights). */
export function buildGoogleFontsUrl(families: string[]): string {
  const params = families
    .map((f) => `family=${encodeURIComponent(f)}:wght@400;700`)
    .join("&");
  return `https://fonts.googleapis.com/css2?${params}&display=swap`;
}
