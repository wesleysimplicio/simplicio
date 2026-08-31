import { expect, test } from "@playwright/test";
import { createDemoSnapshot } from "../src/demo";

test("a typed partial receipt shows sanitized steps without enabling another install (mocked IPC)", async ({ page }) => {
  const snapshot = createDemoSnapshot("active");
  snapshot.source = "runtime";
  await page.addInitScript(({ snapshot }) => {
    let applications = 0;
    Object.assign(window, { __installDiagnosticApplications: () => applications, __TAURI_INTERNALS__: {
      invoke: async (command: string) => {
        if (command === "desktop_snapshot" || command === "refresh_desktop_snapshot") return snapshot;
        if (command === "desktop_plan_integrations") return {
          schema: "simplicio.desktop-integration-plan/v1", source: "runtime",
          planDigest: "sha256:" + "a".repeat(64),
          changes: [{ label: "hermes", exists: true, changed: true }],
        };
        if (command === "desktop_repair_providers") {
          applications += 1;
          throw {
            schema: "simplicio.desktop-install-error/v1", code: "integration_install_exit_code:1",
            diagnostic: { schema: "simplicio.desktop-install-diagnostic/v1", status: "partial", failedSteps: ["hermes"], unknownFailedSteps: 0 },
            detail: "DO_NOT_LEAK /private/test-user",
          };
        }
        if (command === "plugin:event|listen") return 1;
        if (command === "plugin:event|unlisten") return;
        throw "unexpected_install_diagnostic_command";
      },
    } });
  }, { snapshot });
  await page.goto("/?view=setup");
  await page.getByRole("button", { name: "Configurar Simplicio", exact: true }).click();
  await page.getByRole("checkbox", { name: /Autorizo o Runtime/ }).check();
  await page.getByRole("button", { name: "Instalar e conectar", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Não foi possível concluir.", exact: true })).toBeVisible();
  await expect(page.getByRole("alert")).toContainText("Etapas com falha: Hermes.");
  await expect(page.getByRole("alert")).toContainText("código 1.");
  await expect(page.locator("body")).not.toContainText("DO_NOT_LEAK");
  await expect(page.locator("body")).not.toContainText("/private/test-user");
  await expect(page.getByRole("button", { name: "Revisar novamente", exact: true })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Instalar e conectar", exact: true })).toHaveCount(0);
  await page.getByRole("button", { name: "Voltar ao app", exact: true }).click();
  await page.getByRole("button", { name: "Integrações MCP", exact: true }).click();
  const integration = page.getByRole("region", { name: "Configuração do MCP", exact: true });
  await expect(integration.getByRole("button", { name: "Revisar configuração MCP", exact: true })).toBeDisabled();
  await integration.getByRole("button", { name: "Atualizar diagnóstico", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Runtime e diagnóstico", exact: true })).toBeVisible();
  expect(await page.evaluate(() => (window as Window & { __installDiagnosticApplications: () => number }).__installDiagnosticApplications())).toBe(1);
});
