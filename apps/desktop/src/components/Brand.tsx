import type { ReactNode } from "react";

export function Brand({ compact = false }: { compact?: boolean }) {
  return (
    <div className="brand" aria-label="Simplicio">
      <img className="brand-mark" src="/icon.png" width="30" height="30" alt="" />
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
  | "chat"
  | "teams"
  | "automation"
  | "apps"
  | "providers"
  | "activity"
  | "memory"
  | "settings"
  | "arrow"
  | "chevron"
  | "search"
  | "plus"
  | "live"
  | "attention"
  | "check"
  | "shield"
  | "spark"
  | "refresh"
  | "folder"
  | "sidebar"
  | "back"
  | "close"
  | "external"
  | "keyboard"
  | "monitor"
  | "lock";

const paths: Record<GlyphName, ReactNode> = {
  folder: <path d="M3 7V5a2 2 0 0 1 2-2h5l2 3h7a2 2 0 0 1 2 2v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7Z" />,
  sidebar: <><rect x="3" y="4" width="18" height="16" rx="2" /><path d="M9 4v16" /></>,
  back: <path d="M19 12H5l5-5M5 12l5 5" />,
  close: <path d="m6 6 12 12M6 18 18 6" />,
  external: <><path d="M14 3h7v7M21 3l-9 9" /><path d="M10 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-5" /></>,
  keyboard: <><rect x="2" y="5" width="20" height="14" rx="2" /><path d="M6 9h.01M10 9h.01M14 9h.01M18 9h.01M6 12h.01M10 12h.01M14 12h.01M18 12h.01M7 16h10" /></>,
  monitor: <><rect x="3" y="3" width="18" height="13" rx="2" /><path d="M8 21h8M12 16v5" /></>,
  home: <path d="M3 10.8 12 3l9 7.8v9.7a.5.5 0 0 1-.5.5H15v-6H9v6H3.5a.5.5 0 0 1-.5-.5Z" />,
  chat: (
    <>
      <path d="M4 5.2A2.2 2.2 0 0 1 6.2 3h11.6A2.2 2.2 0 0 1 20 5.2v7.6a2.2 2.2 0 0 1-2.2 2.2H10l-4.8 4v-4.4A2.2 2.2 0 0 1 4 12.8Z" />
      <path d="M8 8h8M8 11h5" />
    </>
  ),
  teams: (
    <>
      <circle cx="9" cy="8" r="3" />
      <path d="M3.5 20a5.5 5.5 0 0 1 11 0M17 6a2.5 2.5 0 1 1 0 5M16 14a4.5 4.5 0 0 1 4 4.5" />
    </>
  ),
  automation: (
    <>
      <circle cx="12" cy="12" r="3" />
      <path d="M12 2v3M12 19v3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M2 12h3M19 12h3M4.9 19.1 7 17M17 7l2.1-2.1" />
    </>
  ),
  apps: (
    <>
      <rect x="3" y="3" width="7" height="7" rx="1.4" />
      <rect x="14" y="3" width="7" height="7" rx="1.4" />
      <rect x="3" y="14" width="7" height="7" rx="1.4" />
      <rect x="14" y="14" width="7" height="7" rx="1.4" />
    </>
  ),
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
  chevron: <path d="m7 9 5 5 5-5" />,
  search: <><circle cx="10.8" cy="10.8" r="6.3" /><path d="m16 16 4.5 4.5" /></>,
  plus: <path d="M12 5v14M5 12h14" />,
  live: <><circle cx="12" cy="12" r="8.5" /><path d="M9 9.2v5.6l5-2.8Z" /></>,
  attention: <><path d="M12 3 21 20H3Z" /><path d="M12 9v4M12 16h.01" /></>,
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
