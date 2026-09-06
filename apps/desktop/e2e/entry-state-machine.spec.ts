import { expect, test, type Page } from "@playwright/test";
import { createDemoSnapshot } from "../src/demo";

type EntryTestWindow = Window & {
  __entryCalls: Array<{ command: string; args: Record<string, unknown> }>;
  __finishRuntimeInstall?: () => void;
  __finishRuntimeRefresh?: () => void;
};

async function mockEntryFlow(page: Page, initial: "missing" | "degraded" | "signed_out" | "active", pauseInstall = false) {
  const snapshots = {
    signed_out: createDemoSnapshot("signed_out"),
    active: createDemoSnapshot("active"),
    degraded: createDemoSnapshot("signed_out"),
  };
  snapshots.degraded.runtime.state = "degraded";
  for (const snapshot of Object.values(snapshots)) snapshot.source = "runtime";
  const receipt = {
    schema: "simplicio.desktop-runtime-install/v1",
    status: "installed",
    scope: "runtime_core",
    source: "packaged_sidecar",
    installed: true,
    current: true,
    validated: true,
    backupAvailable: false,
    pluginsMutated: false,
    runtime: { state: "healthy", version: "3.8.40", config: { token: "secret-token" } },
    path: "/Users/private/.simplicio/bin/simplicio",
    rawOutput: "secret-token",
  };
  await page.addInitScript(({ snapshots, receipt, initial, pauseInstall }) => {
    let installed = initial !== "missing";
    let runtimeHealthy = initial !== "degraded";
    let access: "signed_out" | "active" = initial === "active" ? "active" : "signed_out";
    let callbackSequence = 0;
    const calls: Array<{ command: string; args: Record<string, unknown> }> = [];
    Object.assign(window, {
      isTauri: true,
      __entryCalls: calls,
      __TAURI_EVENT_PLUGIN_INTERNALS__: { unregisterListener: () => undefined },
      __TAURI_INTERNALS__: {
        transformCallback: () => ++callbackSequence,
        invoke: async (command: string, args: Record<string, unknown> = {}) => {
          if (command === "desktop_runtime_install_status") return { schema: "simplicio.desktop-install-status/v1", status: "clear", redacted: true };
          if (command === "desktop_preparation_status") return true;
          if (command === "desktop_prepare_runtime_environment") {
            calls.push({ command, args });
            return {
              schema: "simplicio.desktop-preparation-result/v1",
              status: "ready",
              effectsApplied: true,
              runtimeDependencies: { status: "ready", pythonRequired: false },
              python: { status: "not_detected", dependenciesVerified: false },
              memory: { ready: true, items: 100, skills: 50, migrations: 1 },
              clients: { configured: 0, skipped: 0 },
              redacted: true,
            };
          }
          calls.push({ command, args });
          if (command === "plugin:event|listen") return ++callbackSequence;
          if (command === "plugin:event|unlisten") return;
          if (command === "desktop_snapshot") {
            if (!installed) throw "runtime_install_required";
            if (!runtimeHealthy) return snapshots.degraded;
            return snapshots[access];
          }
          if (command === "desktop_install_runtime") {
            if (pauseInstall) {
              await new Promise<void>((resolve) => Object.assign(window, { __finishRuntimeInstall: resolve }));
            }
            installed = true;
            runtimeHealthy = true;
            return receipt;
          }
          if (command === "refresh_desktop_snapshot") {
            if (pauseInstall) {
              await new Promise<void>((resolve) => Object.assign(window, { __finishRuntimeRefresh: resolve }));
            }
            return snapshots[access];
          }
          if (command === "desktop_login") {
            access = "active";
            return snapshots.active;
          }
          if (command === "desktop_logout") {
            access = "signed_out";
            return snapshots.signed_out;
          }
          throw `Unexpected entry IPC: ${command}`;
        },
      },
    });
  }, { snapshots, receipt, initial, pauseInstall });
}

async function entryCalls(page: Page) {
  return page.evaluate(() => (window as EntryTestWindow).__entryCalls);
}

function count(calls: Array<{ command: string }>, command: string) {
  return calls.filter((call) => call.command === command).length;
}

function expectNoHostPluginEffects(calls: Array<{ command: string }>) {
  for (const command of ["desktop_plan_integrations", "desktop_apply_host_plugins", "desktop_reconcile_host_plugins"]) {
    expect(count(calls, command)).toBe(0);
  }
}

test("first opening installs packaged Runtime exactly once, validates a fresh snapshot, then shows login", async ({ page }) => {
  await mockEntryFlow(page, "missing", true);
  await page.goto("/");
  await expect(page.getByRole("button", { name: "Install Now", exact: true })).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Navegação principal" })).toHaveCount(0);
  await expect(page.getByRole("progressbar")).toHaveCount(0);

  const install = page.getByRole("button", { name: "Install Now", exact: true });
  await install.evaluate((button: HTMLButtonElement) => { button.click(); button.click(); });
  await expect(page.getByRole("button", { name: "Preparando…", exact: true })).toBeDisabled();
  await expect(page.getByRole("progressbar")).not.toHaveAttribute("value");
  await expect(page.locator(".setup-steps [data-state=complete]")).toHaveCount(0);
  await expect(page.getByText("Conferir o Runtime e as dependências empacotadas.", { exact: true })).toBeVisible();
  const installCalls = await entryCalls(page);
  expect(count(installCalls, "desktop_install_runtime")).toBe(1);

  await page.evaluate(() => (window as EntryTestWindow).__finishRuntimeInstall?.());
  const preparingCalls = await entryCalls(page);
  expect(count(preparingCalls, "desktop_prepare_runtime_environment")).toBe(1);
  await expect(page.getByRole("progressbar")).toHaveAttribute("value", "80");
  await expect(page.getByText("Runtime 3.8.40 validado", { exact: true })).toBeVisible();
  await expect(page.locator("body")).not.toContainText("/Users/private");
  await expect(page.locator("body")).not.toContainText("secret-token");

  await page.evaluate(() => (window as EntryTestWindow).__finishRuntimeRefresh?.());
  await expect(page.getByRole("button", { name: "Começar", exact: true })).toBeVisible();
  const calls = await entryCalls(page);
  expect(count(calls, "desktop_install_runtime")).toBe(1);
  expect(count(calls, "desktop_prepare_runtime_environment")).toBe(1);
  expect(calls.find((call) => call.command === "desktop_install_runtime")?.args).toEqual({});
  expect(count(calls, "refresh_desktop_snapshot")).toBe(1);
  expect(count(calls, "desktop_login")).toBe(0);
  expectNoHostPluginEffects(calls);
});

test("a degraded Runtime never skips the core repair gate", async ({ page }) => {
  await mockEntryFlow(page, "degraded");
  await page.goto("/");
  await expect(page.getByRole("button", { name: "Install Now", exact: true })).toBeVisible();
  const calls = await entryCalls(page);
  expect(count(calls, "desktop_install_runtime")).toBe(0);
  expect(count(calls, "desktop_login")).toBe(0);
  expectNoHostPluginEffects(calls);
});

test("a current Runtime skips installation and Google login opens the normal app without plugin setup", async ({ page }) => {
  await mockEntryFlow(page, "signed_out");
  await page.goto("/?view=settings");
  await expect(page.getByRole("button", { name: "Começar", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Começar", exact: true }).click();
  await page.getByRole("button", { name: "Continuar com Google", exact: true })
    .evaluate((button: HTMLButtonElement) => { button.click(); button.click(); });
  await expect(page.getByRole("heading", { name: "Simplicio", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Um bom começo.", exact: true })).toHaveCount(0);
  const calls = await entryCalls(page);
  expect(count(calls, "desktop_install_runtime")).toBe(0);
  expect(count(calls, "desktop_login")).toBe(1);
  expectNoHostPluginEffects(calls);
});

test("a current Runtime and active session skip both installation and login", async ({ page }) => {
  await mockEntryFlow(page, "active");
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Simplicio", exact: true })).toBeVisible();
  const calls = await entryCalls(page);
  expect(count(calls, "desktop_install_runtime")).toBe(0);
  expect(count(calls, "desktop_login")).toBe(0);
  expectNoHostPluginEffects(calls);
});

test("logout returns only to login and does not reinstall Runtime or mutate plugins", async ({ page }) => {
  await mockEntryFlow(page, "active");
  await page.goto("/?view=settings");
  await page.getByRole("button", { name: "Sair da conta", exact: true }).click();
  await expect(page.getByRole("button", { name: "Começar", exact: true })).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Navegação principal" })).toHaveCount(0);
  const calls = await entryCalls(page);
  expect(count(calls, "desktop_logout")).toBe(1);
  expect(count(calls, "desktop_install_runtime")).toBe(0);
  expect(count(calls, "desktop_login")).toBe(0);
  expectNoHostPluginEffects(calls);
});


test("logout and relogin preserve the installed Runtime without reinstalling", async ({ page }) => {
  await mockEntryFlow(page, "active");
  await page.goto("/?view=settings");
  await page.getByRole("button", { name: "Sair da conta", exact: true }).click();
  await expect(page.getByRole("button", { name: "Começar", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Começar", exact: true }).click();
  await page.getByRole("button", { name: "Continuar com Google", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Simplicio", exact: true })).toBeVisible();

  const calls = await entryCalls(page);
  expect(count(calls, "desktop_logout")).toBe(1);
  expect(count(calls, "desktop_login")).toBe(1);
  expect(count(calls, "desktop_install_runtime")).toBe(0);
  expectNoHostPluginEffects(calls);
});
