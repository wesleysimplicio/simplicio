import { expect, test, type Page } from "@playwright/test";
import { createDemoSnapshot } from "../src/demo";

type RecoveryWindow = Window & { __referenceRecoveryCalls: string[] };

async function prepareRecovery(page: Page, failure: string) {
  const snapshot = createDemoSnapshot("active");
  snapshot.source = "runtime";
  await page.addInitScript(({ snapshot, failure }) => {
    const calls: string[] = [];
    Object.assign(window, { __referenceRecoveryCalls: calls, __TAURI_INTERNALS__: {
      invoke: async (command: string) => {
        calls.push(command);
        if (command === "desktop_snapshot" || command === "refresh_desktop_snapshot") return snapshot;
        if (command === "desktop_install_diagnostic") return {
          schema: "simplicio.desktop-install-attempt/v1", status: "clear", error: null,
        };
        if (command === "desktop_plan_integrations") return {
          schema: "simplicio.desktop-integration-plan/v1", source: "runtime",
          planDigest: "sha256:" + "a".repeat(64),
          changes: [{ label: "codex", exists: false, changed: true }],
        };
        if (command === "desktop_repair_providers") {
          if (failure === "verification_failed") return snapshot;
          throw failure;
        }
        if (command === "plugin:event|listen") return 1;
        if (command === "plugin:event|unlisten") return;
        throw "unexpected_reference_recovery_command";
      },
    } });
  }, { snapshot, failure });
  await page.goto("/?view=setup");
  await page.getByRole("button", { name: "Configurar Simplicio", exact: true }).click();
  await page.getByRole("checkbox", { name: /Autorizo o Runtime/ }).check();
  await page.getByRole("button", { name: "Instalar e conectar", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Não foi possível concluir.", exact: true })).toBeVisible();
}

async function count(page: Page, command: string) {
  return page.evaluate((command) => (window as RecoveryWindow).__referenceRecoveryCalls.filter((call) => call === command).length, command);
}

for (const failure of ["integration_install_timeout", "integration_install_busy", "integration_install_applied_snapshot_unavailable", "verification_failed"]) {
  test(`${failure} stays read-only across Setup, Providers and diagnostic refresh (mocked IPC)`, async ({ page }) => {
    await prepareRecovery(page, failure);
    await expect(page.getByRole("button", { name: "Revisar novamente", exact: true })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Instalar e conectar", exact: true })).toHaveCount(0);
    const confirmedReceipt = failure === "integration_install_applied_snapshot_unavailable" || failure === "verification_failed";
    await expect(page.getByRole("progressbar")).toHaveAttribute("value", confirmedReceipt ? "3" : "2");
    const diagnostic = page.getByRole("button", { name: confirmedReceipt ? "Atualizar diagnóstico" : "Abrir diagnóstico", exact: true });
    await expect(diagnostic).toBeEnabled();
    expect(await count(page, "desktop_repair_providers")).toBe(1);
    const plans = await count(page, "desktop_plan_integrations");
    await page.getByRole("button", { name: "Voltar ao app", exact: true }).click();
    await page.getByRole("button", { name: "Integrações MCP", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Integrações MCP", exact: true })).toBeVisible();
    const integration = page.getByRole("region", { name: "Configuração do MCP", exact: true });
    await expect(integration.getByRole("button", { name: "Revisar configuração MCP", exact: true })).toBeDisabled();
    await expect(integration.getByRole("button", { name: "Aplicar configuração MCP", exact: true })).toHaveCount(0);
    await expect(integration.getByRole("checkbox", { name: /Autorizo o Runtime/ })).toHaveCount(0);
    const refreshes = await count(page, "refresh_desktop_snapshot");
    await page.getByRole("button", { name: "Verificar", exact: true }).click();
    await expect.poll(() => count(page, "refresh_desktop_snapshot")).toBeGreaterThan(refreshes);
    await expect(page.getByRole("button", { name: "Verificar", exact: true })).toBeEnabled();
    await expect(integration.getByRole("button", { name: "Revisar configuração MCP", exact: true })).toBeDisabled();
    const diagnosticRefreshes = await count(page, "refresh_desktop_snapshot");
    await integration.getByRole("button", { name: "Atualizar diagnóstico", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Runtime e diagnóstico", exact: true })).toBeVisible();
    await expect.poll(() => count(page, "refresh_desktop_snapshot")).toBeGreaterThan(diagnosticRefreshes);
    await page.getByRole("button", { name: "Integrações MCP", exact: true }).click();
    await expect(integration.getByRole("button", { name: "Revisar configuração MCP", exact: true })).toBeDisabled();
    await expect(integration.getByRole("button", { name: "Aplicar configuração MCP", exact: true })).toHaveCount(0);
    expect(await count(page, "desktop_plan_integrations")).toBe(plans);
    await page.getByRole("button", { name: "Instalação guiada", exact: true }).click();
    await expect(page.getByRole("button", { name: "Configurar Simplicio", exact: true })).toBeDisabled();
    await expect(page.getByRole("button", { name: confirmedReceipt ? "Atualizar diagnóstico" : "Abrir diagnóstico", exact: true })).toBeEnabled();
    await expect(page.getByRole("button", { name: "Agora não", exact: true })).toBeEnabled();
    await expect(page.getByRole("alert")).toBeVisible();
    expect(await count(page, "desktop_plan_integrations")).toBe(plans);
    expect(await count(page, "desktop_repair_providers")).toBe(1);
  });
}

for (const failure of ["integration_plan_changed_review_again", "integration_install_not_started"]) {
  test(`${failure} requires fresh plans and new consent across Setup and Providers (mocked IPC)`, async ({ page }) => {
    await prepareRecovery(page, failure);
    await page.getByRole("button", { name: "Revisar novamente", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Tudo pronto para revisar.", exact: true })).toBeVisible();
    await expect(page.getByRole("checkbox", { name: /Autorizo o Runtime/ })).not.toBeChecked();
    await expect(page.getByRole("button", { name: "Instalar e conectar", exact: true })).toBeDisabled();
    expect(await count(page, "desktop_repair_providers")).toBe(1);
    expect(await count(page, "desktop_plan_integrations")).toBe(2);
    await page.getByRole("button", { name: "Voltar ao app", exact: true }).click();
    await page.getByRole("button", { name: "Integrações MCP", exact: true }).click();
    const integration = page.getByRole("region", { name: "Configuração do MCP", exact: true });
    await expect(integration.getByRole("button", { name: "Revisar configuração MCP", exact: true })).toBeEnabled();
    await integration.getByRole("button", { name: "Revisar configuração MCP", exact: true }).click();
    await expect(integration.getByRole("checkbox", { name: /Autorizo o Runtime/ })).not.toBeChecked();
    await expect(integration.getByRole("button", { name: "Aplicar configuração MCP", exact: true })).toBeDisabled();
    expect(await count(page, "desktop_plan_integrations")).toBe(3);
    expect(await count(page, "desktop_repair_providers")).toBe(1);
    await page.getByRole("button", { name: "Instalação guiada", exact: true }).click();
    await expect(page.getByRole("button", { name: "Configurar Simplicio", exact: true })).toBeEnabled();
    await page.getByRole("button", { name: "Configurar Simplicio", exact: true }).click();
    await expect(page.getByRole("checkbox", { name: /Autorizo o Runtime/ })).not.toBeChecked();
    await expect(page.getByRole("button", { name: "Instalar e conectar", exact: true })).toBeDisabled();
    expect(await count(page, "desktop_plan_integrations")).toBe(4);
    expect(await count(page, "desktop_repair_providers")).toBe(1);
  });
}
