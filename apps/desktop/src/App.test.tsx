import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { DesktopApp } from "./App";
import { createDemoSnapshot } from "./demo";

describe("Simplicio Desktop product states", () => {
  it("offers browser login when there is no identity", () => {
    const html = renderToStaticMarkup(
      <DesktopApp snapshot={createDemoSnapshot("signed_out")} />,
    );
    expect(html).toContain("Continuar com Google");
    expect(html).toContain("Nenhuma senha passa pelo app");
  });

  it("keeps the Runtime disabled when entitlement is inactive", () => {
    const html = renderToStaticMarkup(
      <DesktopApp snapshot={createDemoSnapshot("inactive")} />,
    );
    expect(html).toContain("Acesso necessário");
    expect(html).toContain("Ver planos");
    expect(html).toContain("Runtime desabilitado");
  });

  it("does not mislabel an unknown entitlement as unpaid", () => {
    const html = renderToStaticMarkup(
      <DesktopApp snapshot={createDemoSnapshot("unknown")} />,
    );
    expect(html).toContain("Não foi possível verificar");
    expect(html).toContain("não o tratamos como assinatura inativa");
    expect(html).not.toContain("Acesso necessário");
  });

  it("shows verified Runtime and provider data only to active access", () => {
    const html = renderToStaticMarkup(
      <DesktopApp snapshot={createDemoSnapshot("active")} />,
    );
    expect(html).toContain("Runtime online");
    expect(html).toContain("Providers");
    expect(html).toContain("Demonstração");
  });
});
