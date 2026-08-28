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

  it("exposes the complete v1 shell only after active access", () => {
    const html = renderToStaticMarkup(
      <DesktopApp snapshot={createDemoSnapshot("active")} />,
    );
    expect(html).toContain("Início");
    expect(html).toContain("Providers");
    expect(html).toContain("Atividade");
    expect(html).toContain("Memória");
    expect(html).toContain("Configurações");
    expect(html).toContain("v3.8.36");
  });

  it("does not invent cost or cache metrics without evidence", () => {
    const snapshot = createDemoSnapshot("active");
    snapshot.savings.estimatedUsd = null;
    snapshot.savings.providerCache.hitPercent = null;
    snapshot.savings.providerCache.proofKind = "unavailable";
    const html = renderToStaticMarkup(<DesktopApp snapshot={snapshot} />);
    expect(html).toContain("sem telemetria");
    expect(html).not.toContain("0% telemetria do provider");
  });
});
