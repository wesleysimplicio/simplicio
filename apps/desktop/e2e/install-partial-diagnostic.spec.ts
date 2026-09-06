import { expect, test } from "@playwright/test";
import { createDemoSnapshot } from "../src/demo";
import { hostPluginPlan, hostPluginReceipt } from "./host-plugin-fixtures";

test("a canonical partial receipt stays sanitized and cannot enable another apply (mocked IPC)", async ({ page }) => {
  const snapshot = createDemoSnapshot("active");
  snapshot.source = "runtime";
  delete snapshot.hostPlugins;
  const plan = hostPluginPlan();
  const partial = hostPluginReceipt({ state: "partial", durableByte: "e" });
  Object.assign(partial.receipt, { raw_stdout: "DO_NOT_LEAK", backup_path: "/private/test-user" });
  Object.assign(partial.snapshot, { raw_stderr: "DO_NOT_LEAK", config_path: "/private/test-user" });
  await page.addInitScript(({ snapshot, plan, partial }) => {
    let applications = 0;
    Object.assign(window, { __installDiagnosticApplications: () => applications, __TAURI_INTERNALS__: {
      invoke: async (command: string) => {
        if (command === "desktop_runtime_install_status") return { schema: "simplicio.desktop-install-status/v1", status: "clear", redacted: true };
        if (command === "desktop_preparation_status") return true;
        if (command === "desktop_snapshot" || command === "refresh_desktop_snapshot") return snapshot;
        if (command === "desktop_plan_integrations") return plan;
        if (command === "desktop_apply_host_plugins") {
          applications += 1;
          return partial;
        }
        if (command === "plugin:event|listen") return 1;
        if (command === "plugin:event|unlisten") return;
        throw "unexpected_install_diagnostic_command";
      },
    } });
  }, { snapshot, plan, partial });

  await page.goto("/?view=setup");
  await page.getByRole("button", { name: "Install Now", exact: true }).click();
  await page.getByRole("checkbox", { name: /Autorizo o Runtime/ }).check();
  await page.getByRole("button", { name: "Instalar e conectar", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Não foi possível concluir.", exact: true })).toBeVisible();
  await expect(page.getByRole("alert")).toContainText("resultado parcial");
  await expect(page.getByRole("region", { name: "Resultado dos plugins", exact: true })).toContainText("Falhou");
  await expect(page.locator("body")).not.toContainText("DO_NOT_LEAK");
  await expect(page.locator("body")).not.toContainText("/private/test-user");
  await expect(page.getByRole("button", { name: "Reconciliar recibo", exact: true })).toBeEnabled();
  await expect(page.getByRole("button", { name: "Instalar e conectar", exact: true })).toHaveCount(0);
  expect(await page.evaluate(() => (window as Window & { __installDiagnosticApplications: () => number }).__installDiagnosticApplications())).toBe(1);
});
