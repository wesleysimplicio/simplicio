export const designTokens = {
  color: {
    ink: "#25261f",
    muted: "#777567",
    canvas: "#ffffff",
    surface: "#ffffff",
    green: "#54a879",
    greenDark: "#2f704e",
    warning: "#bb7b34",
  },
  space: { xs: "4px", sm: "8px", md: "12px", lg: "16px", xl: "24px" },
  radius: { sm: "7px", md: "9px", lg: "13px", pill: "999px" },
  motion: {
    instant: "100ms",
    fast: "160ms",
    standard: "220ms",
    deliberate: "320ms",
    ambient: "3200ms",
  },
  focus: "2px solid #2f704e",
  targetMinimum: "44px",
} as const;
