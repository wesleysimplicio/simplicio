import { describe, expect, it } from "vitest";
import { copy, locale, t } from "./i18n";
import { designTokens } from "./design_tokens";

describe("desktop design system", () => {
  it("keeps the initial locale and UI copy separate from Runtime data", () => {
    expect(locale).toBe("pt-BR");
    expect(t("nav.settings")).toBe("Configurações");
    expect(Object.keys(copy).every((key) => key.startsWith("nav.") || key.startsWith("provider."))).toBe(true);
  });

  it("centralizes interaction tokens and keeps touch targets usable", () => {
    expect(designTokens.targetMinimum).toBe("44px");
    expect(designTokens.focus).toContain("2px");
    expect(designTokens.radius.md).toBe("9px");
    expect(designTokens.motion.instant).toBe("100ms");
    expect(designTokens.motion.standard).toBe("220ms");
    expect(designTokens.motion.deliberate).toBe("320ms");
    expect(designTokens.motion.ambient).toBe("3200ms");
  });
});
