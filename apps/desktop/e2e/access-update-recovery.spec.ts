import { expect, test, type Page } from "@playwright/test";
import { createDemoSnapshot } from "../src/demo";
import { DESKTOP_RELEASES_API, DESKTOP_RELEASES_URL, DESKTOP_UPDATE_EVENT } from "../src/desktop_updates";

type AccessUpdateWindow = Window & {
  __accessUpdateCalls: string[];
  __accessUpdateMenu: () => void;
  __accessUpdateListeners: () => number;
};

async function mockAccessUpdates(page: Page, state: "signed_out" | "unknown" | "active", authOnlyUnsupported = false) {
  const snapshots = {
    signed_out: createDemoSnapshot("signed_out"),
    unknown: createDemoSnapshot("unknown"),
    active: createDemoSnapshot("active"),
  };
  for (const snapshot of Object.values(snapshots)) snapshot.source = "runtime";
  await page.addInitScript(({ snapshots, state, eventName, authOnlyUnsupported }) => {
    let sequence = 0;
    const callbacks = new Map<number, (event: unknown) => void>();
    const listeners = new Map<number, { event: string; handler: number }>();
    const calls: string[] = [];
    Object.assign(window, {
      isTauri: true,
      __accessUpdateCalls: calls,
      __accessUpdateListeners: () => [...listeners.values()].filter((entry) => entry.event === eventName).length,
      __accessUpdateMenu: () => {
        for (const [id, entry] of listeners) {
          if (entry.event === eventName) callbacks.get(entry.handler)?.({ event: eventName, id, payload: null });
        }
      },
      __TAURI_EVENT_PLUGIN_INTERNALS__: { unregisterListener: (_event: string, id: number) => listeners.delete(id) },
      __TAURI_INTERNALS__: {
        transformCallback: (callback: (event: unknown) => void) => { const id = ++sequence; callbacks.set(id, callback); return id; },
        invoke: async (command: string, args: Record<string, unknown> = {}) => {
          calls.push(command);
          if (command === "plugin:event|listen") {
            const id = ++sequence;
            listeners.set(id, { event: String(args.event), handler: Number(args.handler) });
            return id;
          }
          if (command === "plugin:event|unlisten") return;
          if (command === "desktop_snapshot") return snapshots[state];
          if (command === "refresh_desktop_snapshot") return authOnlyUnsupported ? snapshots.unknown : snapshots[state];
          if (command === "desktop_login" && authOnlyUnsupported) throw "runtime_auth_only_unsupported";
          if (command === "desktop_logout" && authOnlyUnsupported) return snapshots.signed_out;
          if (command === "plugin:app|version") return "3.8.39";
          if (command === "desktop_update_target") return { platform: "macos", arch: "arm64" };
          throw new Error(`Unexpected access update recovery IPC: ${command}`);
        },
      },
    });
  }, { snapshots, state, eventName: DESKTOP_UPDATE_EVENT, authOnlyUnsupported });
  const name = "Simplicio-3.8.40-arm64.dmg";
  await page.route((url) => url.href === DESKTOP_RELEASES_API, (route) => route.fulfill({
    status: 200,
    headers: { "content-type": "application/json", "access-control-allow-origin": "*" },
    body: JSON.stringify([{
      tag_name: "v3.8.40", draft: false, prerelease: false,
      html_url: `${DESKTOP_RELEASES_URL}/tag/v3.8.40`,
      assets: [{ name, state: "uploaded", size: 100_000, browser_download_url: `${DESKTOP_RELEASES_URL}/download/v3.8.40/${name}` }],
    }]),
  }));
}

async function showAndCloseUpdates(page: Page) {
  await expect.poll(() => page.evaluate(() => (window as AccessUpdateWindow).__accessUpdateListeners())).toBe(1);
  await page.evaluate(() => (window as AccessUpdateWindow).__accessUpdateMenu());
  const dialog = page.getByRole("dialog");
  await expect(dialog).toHaveAttribute("data-update-state", "available");
  await expect(dialog).toContainText("Versão deste aplicativo: 3.8.39");
  await expect(dialog).toContainText("Download e instalação manuais");
  await expect(page.getByRole("button", { name: "Ver releases oficiais", exact: true })).toBeEnabled();
  await page.getByRole("button", { name: "Fechar atualizações", exact: true }).click();
  await expect(dialog).toHaveCount(0);
}

async function accountAndInstallCalls(page: Page) {
  const calls = await page.evaluate(() => (window as AccessUpdateWindow).__accessUpdateCalls);
  return calls.filter((command) => [
    "desktop_login", "desktop_logout", "desktop_open_subscription",
    "desktop_plan_integrations", "desktop_apply_host_plugins", "desktop_open_releases",
  ].includes(command));
}

test("signed-out welcome and Google entry retain manual updates without account or installation effects (mocked IPC/metadata)", async ({ page }) => {
  await mockAccessUpdates(page, "signed_out");
  await page.goto("/");
  const start = page.getByRole("button", { name: "Começar", exact: true });
  await expect(start).toBeVisible();
  await showAndCloseUpdates(page);
  await expect(start).toBeFocused();
  await start.click();
  const google = page.getByRole("button", { name: "Continuar com Google", exact: true });
  await expect(google).toBeFocused();
  await showAndCloseUpdates(page);
  await expect(google).toBeFocused();
  expect(await accountAndInstallCalls(page)).toEqual([]);
});

test("unknown access retains manual updates and explicit account recovery (mocked IPC/metadata)", async ({ page }) => {
  await mockAccessUpdates(page, "unknown");
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Tente novamente", exact: true })).toBeVisible();
  await showAndCloseUpdates(page);
  for (const name of ["Tentar novamente", "Entrar ou reconectar", "Abrir diagnóstico", "Sair da conta"]) {
    await expect(page.getByRole("button", { name, exact: true })).toBeEnabled();
  }
  expect(await accountAndInstallCalls(page)).toEqual([]);
});

test("guided setup retains manual updates and an exit without applying a plan (mocked IPC/metadata)", async ({ page }) => {
  await mockAccessUpdates(page, "active");
  await page.goto("/?view=setup");
  await expect(page.getByRole("heading", { name: "Um bom começo.", exact: true })).toBeVisible();
  await showAndCloseUpdates(page);
  await expect(page.getByRole("button", { name: "Configurar Simplicio", exact: true })).toBeEnabled();
  await expect(page.getByRole("button", { name: "Agora não", exact: true })).toBeEnabled();
  expect(await accountAndInstallCalls(page)).toEqual([]);
});

test("unsupported authentication-only Runtime explains the update path and permits verification and sign-out without retrying OAuth (mocked IPC/metadata)", async ({ page }) => {
  await mockAccessUpdates(page, "signed_out", true);
  await page.goto("/");
  await page.getByRole("button", { name: "Começar", exact: true }).click();
  await page.getByRole("button", { name: "Continuar com Google", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Tente novamente", exact: true })).toBeVisible();
  await expect(page.getByRole("alert")).toContainText("O Runtime não oferece login separado da instalação.");
  await expect(page.getByRole("alert")).toContainText("Atualize o Simplicio Desktop para entrar com Google com segurança.");
  await expect(page.getByRole("alert")).not.toContainText("runtime_auth_only_unsupported");
  await expect(page.getByRole("navigation", { name: "Navegação principal" })).toHaveCount(0);
  await showAndCloseUpdates(page);
  expect(await accountAndInstallCalls(page)).toEqual(["desktop_login"]);
  await page.getByRole("button", { name: "Abrir diagnóstico", exact: true }).click();
  await expect(page.getByText("Estado de acesso desconhecido", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Tentar novamente", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Tente novamente", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Entrar ou reconectar", exact: true })).toBeEnabled();
  expect(await accountAndInstallCalls(page)).toEqual(["desktop_login"]);
  const calls = await page.evaluate(() => (window as AccessUpdateWindow).__accessUpdateCalls);
  expect(calls.filter((command) => command === "refresh_desktop_snapshot")).toHaveLength(1);
  await page.getByRole("button", { name: "Sair da conta", exact: true }).click();
  await expect(page.getByRole("button", { name: "Começar", exact: true })).toBeVisible();
  expect(await accountAndInstallCalls(page)).toEqual(["desktop_login", "desktop_logout"]);
});
