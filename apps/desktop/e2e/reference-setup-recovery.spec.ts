import { expect, test, type Page } from "@playwright/test";
import { createDemoSnapshot } from "../src/demo";
import { desktopHostPluginProjection, hostPluginPlan, hostPluginReceipt } from "./host-plugin-fixtures";

type RecoveryWindow = Window & {
  __referenceRecoveryCalls: Array<{ command: string; args: Record<string, unknown> }>;
};

async function calls(page: Page, command: string) {
  return page.evaluate((command) => (window as RecoveryWindow).__referenceRecoveryCalls.filter((call) => call.command === command), command);
}

test("a Runtime-owned pending receipt blocks another plan and reconciles exactly once on explicit consent (mocked IPC)", async ({ page }) => {
  const snapshot = createDemoSnapshot("active");
  snapshot.source = "runtime";
  snapshot.hostPlugins = desktopHostPluginProjection({ pending: true });
  const reconciled = hostPluginReceipt({ operation: "reconcile", receiptByte: "e", durableByte: "e" });
  await page.addInitScript(({ snapshot, reconciled }) => {
    const calls: Array<{ command: string; args: Record<string, unknown> }> = [];
    Object.assign(window, { __referenceRecoveryCalls: calls, __TAURI_INTERNALS__: {
      invoke: async (command: string, args: Record<string, unknown> = {}) => {
        calls.push({ command, args });
        if (command === "desktop_snapshot" || command === "refresh_desktop_snapshot") return snapshot;
        if (command === "desktop_reconcile_host_plugins") return reconciled;
        if (command === "plugin:event|listen") return 1;
        if (command === "plugin:event|unlisten") return;
        throw "unexpected_reference_recovery_command";
      },
    } });
  }, { snapshot, reconciled });

  await page.goto("/?view=setup");
  await expect(page.getByRole("button", { name: "Configurar Simplicio", exact: true })).toBeDisabled();
  await expect(page.getByRole("button", { name: "Reconciliar recibo", exact: true })).toBeEnabled();
  expect(await calls(page, "desktop_plan_integrations")).toHaveLength(0);
  expect(await calls(page, "desktop_apply_host_plugins")).toHaveLength(0);

  await page.getByRole("button", { name: "Reconciliar recibo", exact: true }).dblclick();
  await expect(page.getByRole("heading", { name: "Configuração concluída", exact: true })).toBeVisible();
  expect(await calls(page, "desktop_reconcile_host_plugins")).toEqual([{
    command: "desktop_reconcile_host_plugins",
    args: { receiptId: `sha256:${"e".repeat(64)}` },
  }]);
  expect(await calls(page, "desktop_apply_host_plugins")).toHaveLength(0);
  expect(await calls(page, "desktop_plan_integrations")).toHaveLength(0);
});

test("a canonical partial apply exposes one explicit reconcile without replaying apply (mocked IPC)", async ({ page }) => {
  const snapshot = createDemoSnapshot("active");
  snapshot.source = "runtime";
  delete snapshot.hostPlugins;
  const plan = hostPluginPlan();
  const partial = hostPluginReceipt({ state: "partial", receiptByte: "d", durableByte: "e" });
  const reconciled = hostPluginReceipt({ operation: "reconcile", receiptByte: "e", durableByte: "e" });
  await page.addInitScript(({ snapshot, plan, partial, reconciled }) => {
    const calls: Array<{ command: string; args: Record<string, unknown> }> = [];
    Object.assign(window, { __referenceRecoveryCalls: calls, __TAURI_INTERNALS__: {
      invoke: async (command: string, args: Record<string, unknown> = {}) => {
        calls.push({ command, args });
        if (command === "desktop_snapshot" || command === "refresh_desktop_snapshot") return snapshot;
        if (command === "desktop_plan_integrations") return plan;
        if (command === "desktop_apply_host_plugins") return partial;
        if (command === "desktop_reconcile_host_plugins") return reconciled;
        if (command === "plugin:event|listen") return 1;
        if (command === "plugin:event|unlisten") return;
        throw "unexpected_reference_recovery_command";
      },
    } });
  }, { snapshot, plan, partial, reconciled });

  await page.goto("/?view=setup");
  await page.getByRole("button", { name: "Configurar Simplicio", exact: true }).click();
  await page.getByRole("checkbox", { name: /Autorizo o Runtime/ }).check();
  await page.getByRole("button", { name: "Instalar e conectar", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Não foi possível concluir.", exact: true })).toBeVisible();
  await expect(page.getByRole("alert")).toContainText("resultado parcial");
  expect(await calls(page, "desktop_apply_host_plugins")).toHaveLength(1);

  await page.getByRole("button", { name: "Reconciliar recibo", exact: true }).dblclick();
  await expect(page.getByRole("heading", { name: "Configuração concluída", exact: true })).toBeVisible();
  expect(await calls(page, "desktop_apply_host_plugins")).toHaveLength(1);
  expect(await calls(page, "desktop_reconcile_host_plugins")).toEqual([{
    command: "desktop_reconcile_host_plugins",
    args: { receiptId: `sha256:${"e".repeat(64)}` },
  }]);
  expect(await calls(page, "refresh_desktop_snapshot")).toHaveLength(1);
  expect(await calls(page, "desktop_plan_integrations")).toHaveLength(1);
});
