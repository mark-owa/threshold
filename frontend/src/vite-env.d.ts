/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Base URL of the Threshold API. Empty means same-origin (nginx proxy). */
  readonly VITE_API_URL?: string;
  /** "true" shows the seeded local demo credentials on the sign-in screen. */
  readonly VITE_SHOW_DEMO_CREDENTIALS?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
