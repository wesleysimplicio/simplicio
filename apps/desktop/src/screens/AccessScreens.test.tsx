import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { RuntimeInstallScreen, SignInScreen } from "./AccessScreens";

describe("native installation evidence", () => {
  it("shows only the full logo and Install Now before preparation", () => {
    const html = renderToStaticMarkup(<RuntimeInstallScreen phase="idle" error={null} onInstall={() => {}} />);
    expect(html).toContain('alt="Simplicio"');
    expect(html).toContain("Install Now");
    expect(html).not.toContain("<h1");
    expect(html).not.toContain("<header");
    expect(html).not.toContain("<footer");
    expect(html).not.toMatch(/<p[ >]/);
  });
  it("shows only the logo and primary action in idle login", () => {
    const html = renderToStaticMarkup(<SignInScreen initialStep="login" busy={false} error={null} onLogin={() => {}} />);
    expect(html).toContain('alt="Simplicio"');
    expect(html).toContain("Continuar com Google");
    expect(html).not.toContain("<h1");
    expect(html).not.toContain("<footer");
    expect(html).not.toMatch(/<p[ >]/);
  });
  it("renders the multicolor Google mark instead of a generic text glyph", () => {
    const html = renderToStaticMarkup(<SignInScreen initialStep="login" busy={false} error={null} onLogin={() => {}} />);
    expect(html).toContain('<svg class="google-mark"');
    for (const color of ["#4285F4", "#34A853", "#FBBC05", "#EA4335"]) expect(html).toContain(color);
    expect(html).not.toContain('aria-hidden="true">G</span>');
    expect(html).toContain("Continuar com Google");
  });
  it("does not invent substep progress before the native receipt", () => {
    const html = renderToStaticMarkup(<RuntimeInstallScreen phase="installing" error={null} onInstall={() => {}} />);
    expect(html.match(/data-state="awaiting"/g)).toHaveLength(3);
    expect(html.match(/data-state="pending"/g)).toHaveLength(2);
    expect(html).not.toContain('data-state="complete"');
    expect(html).not.toContain('data-state="running"');
    expect(html.match(/<progress[^>]*>/)?.[0]).not.toContain("value=");
  });
  it("does not blame package validation for an unlocalized native failure", () => {
    const html = renderToStaticMarkup(<RuntimeInstallScreen phase="failed" error="O destino local não passou na validação." onInstall={() => {}} />);
    expect(html.match(/data-state="unconfirmed"/g)).toHaveLength(3);
    expect(html).not.toContain('data-state="failed"');
    expect(html).toContain("O destino local não passou na validação.");
    expect(html).toContain("Tentar novamente");
  });
  it("prepares memory and clients only after installation confirmation", () => {
    const html = renderToStaticMarkup(<RuntimeInstallScreen phase="preparing" error={null} onInstall={() => {}} />);
    expect(html.match(/data-state="complete"/g)).toHaveLength(3);
    expect(html.match(/data-state="running"/g)).toHaveLength(1);
    expect(html).toContain("seeds, migrations");
  });
  it("shows the redacted preparation summary after Runtime setup", () => {
    const html = renderToStaticMarkup(<RuntimeInstallScreen phase="validating" error={null} onInstall={() => {}}
      preparation={{
        schema: "simplicio.desktop-preparation-result/v1",
        status: "ready",
        effectsApplied: true,
        runtimeDependencies: { status: "ready", pythonRequired: false },
        python: { status: "detected", version: "3.11.9", dependenciesVerified: false },
        memory: { ready: true, items: 142, skills: 58, migrations: 3 },
        clients: { configured: 2, skipped: 1 },
        redacted: true,
      }} />);
    expect(html).toContain("Ambiente preparado");
    expect(html).toContain("3.11.9");
    expect(html).toContain("142 itens");
    expect(html).toContain("2 configurados");
  });
  it("keeps the final snapshot step running after preparation", () => {
    const html = renderToStaticMarkup(<RuntimeInstallScreen phase="validating" error={null} onInstall={() => {}} />);
    expect(html.match(/data-state="complete"/g)).toHaveLength(4);
    expect(html.match(/data-state="running"/g)).toHaveLength(1);
  });
});
