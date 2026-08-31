import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { DesktopApp } from "./App";
import { createDemoSnapshot } from "./demo";
import { MemoryScreen } from "./screens/MemoryScreen";
import { SettingsScreen, redactedDiagnostic } from "./screens/SettingsScreen";
import { ActivityScreen, redactedActivity } from "./screens/ActivityScreen";
import { BotCenterScreen } from "./screens/BotCenterScreen";
import { createDemoBotCenter, createUnavailableBotCenter } from "./bot_center";
import { ProductSurfaceScreen } from "./screens/ProductScreens";
import { SignInScreen } from "./screens/AccessScreens";

describe("Simplicio Desktop product states", () => {
  it("offers welcome then browser login when there is no identity", () => {
    const html = renderToStaticMarkup(
      <DesktopApp snapshot={createDemoSnapshot("signed_out")} />,
    );
    expect(html).toContain("Começar");
    expect(html).not.toContain("Continuar com Google");
    const login = renderToStaticMarkup(<SignInScreen initialStep="login" busy={false} error={null} onLogin={() => undefined} />);
    expect(login).toContain("Continuar com Google");
    expect(login).toContain("Nenhuma senha passa pelo app");
    expect(login).not.toContain('type="password"');
    expect(login).not.toContain('type="email"');
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
    expect(html).toContain("Integrações MCP");
    expect(html).toContain("Demonstração");
  });

  it("opens the workbench with functional destinations and keeps unavailable product previews out of primary navigation", () => {
    const html = renderToStaticMarkup(
      <DesktopApp snapshot={createDemoSnapshot("active")} />,
    );
    expect(html).toContain("Início");
    expect(html).toContain("Adicionar projeto");
    expect(html).not.toContain("Agentes e IDEs");
    expect(html).not.toContain("Automações");
    expect(html).toContain("Atividade");
    expect(html).toContain("Configurações");
    expect(html).toContain("v3.8.39");
    expect(html).toContain("Integrações MCP");
    expect(html).toContain("Relatório de tokens");
    expect(html).not.toContain('aria-label="Chats"');
    expect(html).not.toContain("window-controls");
    expect(html).toContain('aria-label="Buscar projetos e páginas"');
  });

  it("keeps the five main surfaces projection-first and bounded", () => {
    const snapshot = createDemoSnapshot("active");
    const botCenter = createDemoBotCenter(snapshot.generatedAt);
    for (const view of ["today", "chats", "teams", "automations", "apps"] as const) {
      const html = renderToStaticMarkup(<ProductSurfaceScreen view={view} snapshot={snapshot} botCenter={botCenter} />);
      expect(html).toContain("Contrato aguardando o Runtime");
      expect(html).toContain("reason:");
    }
    const today = renderToStaticMarkup(<ProductSurfaceScreen view="today" snapshot={snapshot} botCenter={botCenter} />);
    expect(today).toContain("Focus");
    expect(today).toContain("In Progress");
    expect(today).toContain("Up Next");
    const apps = renderToStaticMarkup(<ProductSurfaceScreen view="apps" snapshot={snapshot} botCenter={botCenter} />);
    expect(apps).toContain("Library");
    expect(apps).toContain("Token Reports");
  });

  it("does not invent cost or cache metrics without evidence", () => {
    const snapshot = createDemoSnapshot("active");
    snapshot.savings.estimatedUsd = null;
    snapshot.savings.providerCache.hitPercent = null;
    snapshot.savings.providerCache.proofKind = "unavailable";
    const html = renderToStaticMarkup(<DesktopApp snapshot={snapshot} />);
    expect(html).toContain("Sem telemetria, sem números presumidos");
    expect(html).not.toContain("0% telemetria do provider");
  });

  it("renders bounded memory metadata without exposing the map", () => {
    const html = renderToStaticMarkup(<MemoryScreen snapshot={createDemoSnapshot("active")} />);
    expect(html).toContain("Pronto para reutilizar");
    expect(html).toContain("preview-20260828");
    expect(html).toContain("Entrega protegida por recibo");
    expect(html).not.toContain("repo_map");
  });

  it("offers account diagnostics and a redacted export", () => {
    const snapshot = createDemoSnapshot("active");
    const html = renderToStaticMarkup(<SettingsScreen snapshot={snapshot} busy={false} onRefresh={() => undefined} onSubscribe={() => undefined} onLogout={() => undefined} logoutBusy={false} />);
    const diagnostic = redactedDiagnostic(snapshot);
    expect(html).toContain("Gerenciar plano");
    expect(html).toContain("Exportar diagnóstico");
    expect(html).toContain("Atualizar estado");
    expect(html).toContain("Sair da conta");
    expect(html).toContain("tenta revogar a sessão remota");
    expect(html).not.toContain("O Runtime revoga a sessão");
    expect(JSON.stringify(diagnostic)).not.toContain("voce@example.com");
    expect(JSON.stringify(diagnostic)).not.toContain("sonnet");
  });

  it("renders bounded activity receipts and redacts details on export", () => {
    const snapshot = createDemoSnapshot("active");
    const html = renderToStaticMarkup(<ActivityScreen snapshot={snapshot} />);
    expect(html).toContain("Exportar recibos");
    expect(html).toContain("Todos");
    expect(html).toContain("máximo 5");
    expect(redactedActivity(snapshot.activity)[0]).not.toHaveProperty("detail");
  });

  it("renders Bot Center from the canonical projection without local authority", () => {
    const botCenter = createDemoBotCenter();
    const html = renderToStaticMarkup(<BotCenterScreen snapshot={botCenter} onAction={async () => undefined} />);
    expect(html).toContain("Bot Center");
    expect(html).toContain("Roster canônico");
    expect(html).toContain("Cora");
    expect(html).toContain("Rooms");
    expect(html).toContain("approval_required");
    expect(html).toContain("computer_backend_unavailable");
    expect(html).toContain("session: bot-cora-session-01");
    expect(botCenter.redaction.secrets).toBe(true);
  });

  it("fails closed when the Runtime has not exposed Agent API", () => {
    const html = renderToStaticMarkup(<BotCenterScreen snapshot={createUnavailableBotCenter()} onAction={async () => undefined} />);
    expect(html).toContain("Contrato indisponível");
    expect(html).toContain("agent_api_unavailable");
    expect(html).toContain("Nenhum Bot exposto pelo Runtime");
    expect(html).toContain("disabled");
  });
});
