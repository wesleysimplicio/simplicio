import { expect, test, type Page } from "@playwright/test";
import { createDemoSnapshot } from "../src/demo";

type AccountTestWindow = Window & { __accountEffectCalls: string[] };

async function mockAccountEffects(page: Page, options: {
  initial: "signed_out" | "active";
  loginResult?: "failed" | "unknown";
  refreshFails?: boolean;
}) {
  const states = {
    signed_out: createDemoSnapshot("signed_out"),
    unknown: createDemoSnapshot("unknown"),
    active: createDemoSnapshot("active"),
  };
  for (const snapshot of Object.values(states)) snapshot.source = "runtime";
  await page.addInitScript(({ states, options }) => {
    let current = options.initial;
    const calls: string[] = [];
    Object.assign(window, { __accountEffectCalls: calls, __TAURI_INTERNALS__: {
      invoke: async (command: string) => {
        calls.push(command);
        if (command === "desktop_snapshot") return states[current];
        if (command === "desktop_install_diagnostic") return {
          schema: "simplicio.desktop-install-attempt/v1", status: "clear", error: null,
        };
        if (command === "desktop_login") {
          // OAuth completed, but its following snapshot was not confirmed.
          current = "active";
          if (options.loginResult === "failed") throw "runtime_query_timeout";
          return states.unknown;
        }
        if (command === "desktop_logout") {
          // Local logout completed; a later query failed. Do not infer success in the UI.
          current = "signed_out";
          throw "runtime_query_timeout";
        }
        if (command === "refresh_desktop_snapshot") {
          if (options.refreshFails) throw "runtime_query_timeout";
          return states[current];
        }
        if (command === "plugin:event|listen") return 1;
        if (command === "plugin:event|unlisten") return;
        throw `Unexpected account verification IPC: ${command}`;
      },
    } });
  }, { states, options });
}

async function accountCalls(page: Page) {
  return page.evaluate(() => (window as AccountTestWindow).__accountEffectCalls);
}

for (const loginResult of ["failed", "unknown"] as const) {
  test(`${loginResult} first Google login can verify the account and resume guided installation without a second login`, async ({ page }) => {
    await mockAccountEffects(page, { initial: "signed_out", loginResult });
    await page.goto("/?view=settings");
    await page.getByRole("button", { name: "Começar", exact: true }).click();
    await page.getByRole("button", { name: "Continuar com Google", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Tente novamente", exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Sair da conta", exact: true })).toBeEnabled();
    await expect(page.getByRole("heading", { name: "Ative o Simplicio", exact: true })).toHaveCount(0);
    await expect(page.getByRole("navigation", { name: "Navegação principal" })).toHaveCount(0);
    if (loginResult === "failed") await expect(page.getByRole("alert")).toContainText("O resultado final do login não foi confirmado");
    await page.getByRole("button", { name: "Tentar novamente", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Um bom começo.", exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Configurar Simplicio", exact: true })).toBeEnabled();
    const calls = await accountCalls(page);
    expect(calls.filter(command => command === "desktop_login")).toHaveLength(1);
    expect(calls.filter(command => command === "refresh_desktop_snapshot")).toHaveLength(1);
    expect(calls).not.toContain("desktop_logout");
    expect(calls).not.toContain("desktop_plan_integrations");
    expect(calls).not.toContain("desktop_repair_providers");
  });
}

test("an unconfirmed logout leaves active screens and can verify signed-out state without repeating logout", async ({ page }) => {
  await mockAccountEffects(page, { initial: "active" });
  await page.goto("/?view=settings");
  await page.getByRole("button", { name: "Sair da conta", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Tente novamente", exact: true })).toBeVisible();
  await expect(page.getByRole("alert")).toContainText("A saída da conta não foi confirmada");
  await expect(page.getByRole("navigation", { name: "Navegação principal" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Começar", exact: true })).toHaveCount(0);
  await page.getByRole("button", { name: "Tentar novamente", exact: true }).click();
  await expect(page.getByRole("button", { name: "Começar", exact: true })).toBeVisible();
  const calls = await accountCalls(page);
  expect(calls.filter(command => command === "desktop_logout")).toHaveLength(1);
  expect(calls.filter(command => command === "refresh_desktop_snapshot")).toHaveLength(1);
  expect(calls).not.toContain("desktop_login");
  expect(calls).not.toContain("desktop_repair_providers");
});

test("failed verification after ambiguous login stays unknown and never grants access or installs", async ({ page }) => {
  await mockAccountEffects(page, { initial: "signed_out", loginResult: "failed", refreshFails: true });
  await page.goto("/");
  await page.getByRole("button", { name: "Começar", exact: true }).click();
  await page.getByRole("button", { name: "Continuar com Google", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Tente novamente", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Tentar novamente", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("nenhum resultado atual foi confirmado");
  await expect(page.getByRole("button", { name: "Entrar ou reconectar", exact: true })).toBeEnabled();
  await expect(page.getByRole("heading", { name: "Um bom começo.", exact: true })).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "Ative o Simplicio", exact: true })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Começar", exact: true })).toHaveCount(0);
  expect(await accountCalls(page)).not.toContain("desktop_repair_providers");
});
