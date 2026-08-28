import type { ReactNode } from "react";

export function Brand({ compact = false }: { compact?: boolean }) {
  return (
    <div className="brand" aria-label="Simplicio">
      <svg className="brand-mark" viewBox="0 0 44 44" aria-hidden="true">
        <path className="brand-mark-shell" d="M22 2.5 39 12v20L22 41.5 5 32V12Z" />
        <path
          className="brand-mark-path"
          d="m29.8 13.6-7.9-4.4-8.2 4.6v8.5l8.2 4.6 4.1-2.3v3.7l-4.1 2.3-8.2-4.6-4.5 2.6 12.7 7.1 12.6-7.1v-8.8l-8.1-4.5-4.5 2.5 4.5 2.5 3.4-1.9v3.8l-7.9 4.4-3.7-2.1v-7.7l3.7-2.1 3.5 1.9Z"
        />
      </svg>
      {!compact && (
        <div className="brand-copy">
          <strong>Simplicio</strong>
          <span>DESKTOP</span>
        </div>
      )}
    </div>
  );
}

export type GlyphName =
  | "home"
  | "providers"
  | "activity"
  | "memory"
  | "settings"
  | "arrow"
  | "check"
  | "shield"
  | "spark"
  | "refresh"
  | "lock";

const paths: Record<GlyphName, ReactNode> = {
  home: <path d="M3 10.8 12 3l9 7.8v9.7a.5.5 0 0 1-.5.5H15v-6H9v6H3.5a.5.5 0 0 1-.5-.5Z" />,
  providers: (
    <>
      <path d="M8 3v5M16 3v5M6 8h12v3a6 6 0 0 1-6 6v4" />
      <path d="M9 21h6" />
    </>
  ),
  activity: <path d="M3 12h4l2.2-6 4.2 12 2.2-6H21" />,
  memory: (
    <>
      <path d="M9 4.3A4 4 0 0 0 5.5 10 4.2 4.2 0 0 0 7 18h2" />
      <path d="M15 4.3A4 4 0 0 1 18.5 10 4.2 4.2 0 0 1 17 18h-2M9 3v18M15 3v18M9 8h3M12 13h3" />
    </>
  ),
  settings: (
    <>
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1-2.8 2.8-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.6v.2h-4V21a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1L4.2 17l.1-.1a1.7 1.7 0 0 0 .3-1.9A1.7 1.7 0 0 0 3 14H2.8v-4H3a1.7 1.7 0 0 0 1.6-1 1.7 1.7 0 0 0-.3-1.9L4.2 7 7 4.2l.1.1A1.7 1.7 0 0 0 9 4.6 1.7 1.7 0 0 0 10 3v-.2h4V3a1.7 1.7 0 0 0 1 1.6 1.7 1.7 0 0 0 1.9-.3l.1-.1L19.8 7l-.1.1a1.7 1.7 0 0 0-.3 1.9 1.7 1.7 0 0 0 1.6 1h.2v4H21a1.7 1.7 0 0 0-1.6 1Z" />
    </>
  ),
  arrow: <path d="M5 12h14M14 7l5 5-5 5" />,
  check: <path d="m5 12 4 4L19 6" />,
  shield: <path d="M12 2.8 20 6v5.4c0 5-3.4 8.6-8 10-4.6-1.4-8-5-8-10V6Z" />,
  spark: <path d="m12 2 1.8 6.2L20 10l-6.2 1.8L12 18l-1.8-6.2L4 10l6.2-1.8Z" />,
  refresh: (
    <>
      <path d="M20 11a8 8 0 0 0-14.7-4.2L3 10" />
      <path d="M3 4v6h6M4 13a8 8 0 0 0 14.7 4.2L21 14M21 20v-6h-6" />
    </>
  ),
  lock: (
    <>
      <rect x="5" y="10" width="14" height="11" rx="2" />
      <path d="M8 10V7a4 4 0 0 1 8 0v3M12 14v3" />
    </>
  ),
};

export function Glyph({ name, size = 20 }: { name: GlyphName; size?: number }) {
  return (
    <svg
      className="glyph"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {paths[name]}
    </svg>
  );
}
