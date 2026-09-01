import { expect, test, type Page } from "@playwright/test";
import { createDemoSnapshot } from "../src/demo";
import { desktopHostPluginProjection, hostPluginPlan, hostPluginReceipt } from "./host-plugin-fixtures";

type SetupTestWindow = Window & {
  __setupHostPluginCalls: Array<{ command: string; args: Record<string, unknown> }>;
  __finishHostPluginApply?: () => void;
  __finishHostPluginReconcile?: () => void;
};

async function mockHostPluginResult(page: Page, {
  state = "complete" as "complete" | "partial" | "requires_reconcile",
  status = "verified" as "verified" | "applied_unverified" | "blocked",
  pauseApply = false,
  invalidPlan = false,
  failReconcile = false,
  pauseReconcile = false,
  projectPendingAfterApply = false,
} = {}) {
  const snapshot = createDemoSnapshot("active");
  snapshot.source = "runtime";
  delete snapshot.hostPlugins;
  const plan = hostPluginPlan();
  if (invalidPlan) plan.plan.hosts[1] = { ...plan.plan.hosts[0] };
  const operation = hostPluginReceipt({ state, status, durableByte: "e" });
  const reconciled = hostPluginReceipt({ operation: "reconcile", receiptByte: "e", durableByte: "e" });
  const pendingProjection = desktopHostPluginProjection({ pending: true });
  await page.addInitScript(({ snapshot, plan, operation, reconciled, pendingProjection, pauseApply, failReconcile, pauseReconcile, projectPendingAfterApply }) => {
    const calls: Array<{ command: string; args: Record<string, unknown> }> = [];
    Object.assign(window, { __setupHostPluginCalls: calls, __TAURI_INTERNALS__: {
      invoke: async (command: string, args: Record<string, unknown> = {}) => {
        calls.push({ command, args });
        if (command === "desktop_snapshot" || command === "refresh_desktop_snapshot") return snapshot;
        if (command === "desktop_plan_integrations") return plan;
        if (command === "desktop_apply_host_plugins") {
          if (pauseApply) await new Promise<void>((resolve) => Object.assign(window, { __finishHostPluginApply: resolve }));
          if (projectPendingAfterApply) snapshot.hostPlugins = pendingProjection;
          return operation;
        }
        if (command === "desktop_reconcile_host_plugins") {
          if (pauseReconcile) await new Promise<void>((resolve) => Object.assign(window, { __finishHostPluginReconcile: resolve }));
          if (failReconcile) throw "runtime_install_timeout";
          return reconciled;
        }
        if (command === "plugin:event|listen") return 1;
        if (command === "plugin:event|unlisten") return;
        throw `Unexpected setup host-plugin IPC: ${command}`;
      },
    } });
  }, { snapshot, plan, operation, reconciled, pendingProjection, pauseApply, failReconcile, pauseReconcile, projectPendingAfterApply });
}

async function commandCalls(page: Page, command: string) {
  return page.evaluate((command) => (window as SetupTestWindow).__setupHostPluginCalls.filter((call) => call.command === command), command);
}

async function reviewAndApply(page: Page) {
  await page.goto("/?view=setup");
  await page.getByRole("button", { name: "Configurar Simplicio", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Tudo pronto para revisar.", exact: true })).toBeVisible();
  await page.getByRole("checkbox", { name: /Autorizo o Runtime/ }).check();
  await page.getByRole("button", { name: "Instalar e conectar", exact: true }).click();
}

test("one consent submits one digest and uses the returned canonical receipt without any post-apply query (mocked IPC)", async ({ page }) => {
  await mockHostPluginResult(page, { pauseApply: true });
  await page.goto("/?view=setup");
  await page.getByRole("button", { name: "Configurar Simplicio", exact: true }).click();
  await page.getByRole("checkbox", { name: /Autorizo o Runtime/ }).check();
  await page.getByRole("button", { name: "Instalar e conectar", exact: true }).dblclick();
  await expect(page.getByRole("heading", { name: "Configurando o Simplicio…", exact: true })).toBeVisible();
  await expect(page.getByRole("progressbar")).toHaveAttribute("value", "2");
  expect(await commandCalls(page, "desktop_apply_host_plugins")).toEqual([{
    command: "desktop_apply_host_plugins",
    args: { planDigest: `sha256:${"a".repeat(64)}` },
  }]);
  await page.evaluate(() => (window as SetupTestWindow).__finishHostPluginApply?.());
  await expect(page.getByRole("heading", { name: "Configuração concluída", exact: true })).toBeVisible();
  await expect(page.getByRole("progressbar")).toHaveAttribute("value", "4");
  await expect(page.getByText(/não executou uma segunda leitura, verificação ou aplicação/)).toBeVisible();
  expect(await commandCalls(page, "refresh_desktop_snapshot")).toHaveLength(1);
  expect(await commandCalls(page, "desktop_plan_integrations")).toHaveLength(1);
  expect(await commandCalls(page, "desktop_apply_host_plugins")).toHaveLength(1);
  expect(await commandCalls(page, "desktop_reconcile_host_plugins")).toHaveLength(0);
});

for (const [status, heading, row] of [
  ["applied_unverified", "Aplicado; verificação indisponível", "Aplicado; verificação indisponível"],
  ["blocked", "Concluído com ações manuais", "Ação manual necessária"],
] as const) {
  test(`${status} remains an honest canonical result without a synthetic verification (mocked IPC)`, async ({ page }) => {
    await mockHostPluginResult(page, { status });
    await reviewAndApply(page);
    await expect(page.getByRole("heading", { name: heading, exact: true })).toBeVisible();
    await expect(page.getByRole("region", { name: "Resultado dos plugins", exact: true })).toContainText(row);
    expect(await commandCalls(page, "refresh_desktop_snapshot")).toHaveLength(1);
    expect(await commandCalls(page, "desktop_plan_integrations")).toHaveLength(1);
    expect(await commandCalls(page, "desktop_apply_host_plugins")).toHaveLength(1);
  });
}

for (const state of ["partial", "requires_reconcile"] as const) {
  test(`${state} reconciles only after one explicit click and never replays apply (mocked IPC)`, async ({ page }) => {
    await mockHostPluginResult(page, { state });
    await reviewAndApply(page);
    await expect(page.getByRole("heading", { name: "Não foi possível concluir.", exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Reconciliar recibo", exact: true })).toBeEnabled();
    expect(await commandCalls(page, "desktop_reconcile_host_plugins")).toHaveLength(0);
    await page.getByRole("button", { name: "Reconciliar recibo", exact: true }).dblclick();
    await expect(page.getByRole("heading", { name: "Configuração concluída", exact: true })).toBeVisible();
    expect(await commandCalls(page, "desktop_apply_host_plugins")).toHaveLength(1);
    expect(await commandCalls(page, "desktop_reconcile_host_plugins")).toEqual([{
      command: "desktop_reconcile_host_plugins",
      args: { receiptId: `sha256:${"e".repeat(64)}` },
    }]);
    expect(await commandCalls(page, "refresh_desktop_snapshot")).toHaveLength(1);
    expect(await commandCalls(page, "desktop_plan_integrations")).toHaveLength(1);
  });
}

test("an uncertain reconcile is not replayed by a double click and requires a new state consultation (mocked IPC)", async ({ page }) => {
  await mockHostPluginResult(page, { state: "partial", failReconcile: true, pauseReconcile: true });
  await reviewAndApply(page);
  const reconcile = page.getByRole("button", { name: "Reconciliar recibo", exact: true });
  await reconcile.evaluate((button) => { (button as HTMLButtonElement).click(); (button as HTMLButtonElement).click(); });
  expect(await commandCalls(page, "desktop_reconcile_host_plugins")).toHaveLength(1);
  await page.evaluate(() => (window as SetupTestWindow).__finishHostPluginReconcile?.());
  await expect(page.getByRole("alert")).toContainText("não confirmou");
  await expect(page.getByRole("button", { name: "Consultar estado no diagnóstico", exact: true })).toBeEnabled();
  expect(await commandCalls(page, "desktop_reconcile_host_plugins")).toHaveLength(1);
  expect(await commandCalls(page, "desktop_apply_host_plugins")).toHaveLength(1);
});

test("a later normal snapshot supersedes the ephemeral apply result without an implicit reconcile (mocked IPC)", async ({ page }) => {
  await mockHostPluginResult(page, { projectPendingAfterApply: true });
  await page.goto("/?view=providers");
  await page.getByRole("button", { name: "Revisar configuração MCP", exact: true }).click();
  await page.getByRole("checkbox", { name: /Autorizo o Runtime/ }).check();
  await page.getByRole("button", { name: "Aplicar configuração MCP", exact: true }).click();
  await expect(page.getByRole("region", { name: "Resultado dos plugins", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Verificar", exact: true }).click();
  await expect(page.getByRole("region", { name: "Estado dos plugins", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Reconciliar recibo", exact: true })).toBeEnabled();
  expect(await commandCalls(page, "desktop_apply_host_plugins")).toHaveLength(1);
  expect(await commandCalls(page, "desktop_reconcile_host_plugins")).toHaveLength(0);
  expect(await commandCalls(page, "desktop_plan_integrations")).toHaveLength(1);
  expect(await commandCalls(page, "refresh_desktop_snapshot")).toHaveLength(1);
});

test("an invalid eight-host plan fails closed before consent or apply (mocked IPC)", async ({ page }) => {
  await mockHostPluginResult(page, { invalidPlan: true });
  await page.goto("/?view=setup");
  await page.getByRole("button", { name: "Configurar Simplicio", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("oito hosts");
  await expect(page.getByRole("button", { name: "Instalar e conectar", exact: true })).toHaveCount(0);
  expect(await commandCalls(page, "desktop_apply_host_plugins")).toHaveLength(0);
});

test("the browser preview consumes its local canonical fixture and never calls a native effect", async ({ page }) => {
  await page.goto("/?view=setup");
  await page.getByRole("button", { name: "Configurar Simplicio", exact: true }).click();
  await page.getByRole("checkbox", { name: /Autorizo o Runtime/ }).check();
  await page.getByRole("button", { name: "Simular configuração", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Prévia concluída.", exact: true })).toBeVisible();
  await expect(page.getByText("Esta é uma demonstração. Nenhum arquivo foi alterado.", { exact: true })).toBeVisible();
});
