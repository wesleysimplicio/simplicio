import { expect, test, type Page } from "@playwright/test";
import { createDemoSnapshot } from "../src/demo";
import { DESKTOP_RELEASES_API, DESKTOP_RELEASES_URL, DESKTOP_UPDATE_EVENT } from "../src/desktop_updates";

type UpdatesWindow = Window & {
  __updatesCalls: Array<{ command: string; args: Record<string, unknown> }>;
  __updatesMenu: () => void;
  __updatesListeners: () => number;
  __updatesResolveOpen: (index: number) => void;
  __updatesRejectOpen: (index: number) => void;
};

async function mockUpdates(page: Page) {
  const snapshot = createDemoSnapshot("active");
  snapshot.source = "runtime";
  await page.clock.install();
  await page.addInitScript(({ snapshot, eventName }) => {
    let sequence = 0;
    const callbacks = new Map<number, (event: unknown) => void>();
    const listeners = new Map<number, { event: string; handler: number }>();
    const openers: Array<{ resolve: () => void; reject: () => void }> = [];
    const calls: UpdatesWindow["__updatesCalls"] = [];
    Object.assign(window, {
      isTauri: true,
      __updatesCalls: calls,
      __updatesListeners: () => listeners.size,
      __updatesMenu: () => {
        for (const [id, entry] of listeners) {
          if (entry.event === eventName) callbacks.get(entry.handler)?.({ event: eventName, id, payload: null });
        }
      },
      __updatesResolveOpen: (index: number) => openers[index].resolve(),
      __updatesRejectOpen: (index: number) => openers[index].reject(),
      __TAURI_EVENT_PLUGIN_INTERNALS__: { unregisterListener: (_event: string, id: number) => listeners.delete(id) },
      __TAURI_INTERNALS__: {
        transformCallback: (callback: (event: unknown) => void) => { const id = ++sequence; callbacks.set(id, callback); return id; },
        invoke: async (command: string, args: Record<string, unknown> = {}) => {
          calls.push({ command, args });
          if (command === "plugin:event|listen") {
            const id = ++sequence;
            listeners.set(id, { event: String(args.event), handler: Number(args.handler) });
            return id;
          }
          if (command === "plugin:event|unlisten") return;
          if (command === "plugin:app|version") return "3.8.39";
          if (command === "desktop_update_target") return { platform: "macos", arch: "arm64" };
          if (command === "desktop_snapshot" || command === "refresh_desktop_snapshot") return snapshot;
          if (command === "desktop_open_releases") return new Promise<void>((resolve, reject) => openers.push({ resolve, reject: () => reject(new Error("mock opener failed")) }));
          throw new Error(`Unexpected update test IPC: ${command}`);
        },
      },
    });
  }, { snapshot, eventName: DESKTOP_UPDATE_EVENT });
  const name = "Simplicio-3.8.40-arm64.dmg";
  await page.route((url) => url.href === DESKTOP_RELEASES_API, (route) => route.fulfill({
    status: 200, headers: { "content-type": "application/json", "access-control-allow-origin": "*" },
    body: JSON.stringify([{ tag_name: "v3.8.40", draft: false, prerelease: false, html_url: `${DESKTOP_RELEASES_URL}/tag/v3.8.40`,
      assets: [{ name, state: "uploaded", size: 100_000, browser_download_url: `${DESKTOP_RELEASES_URL}/download/v3.8.40/${name}` }],
    }]),
  }));
  await page.goto("/");
  await expect.poll(() => page.evaluate(() => (window as UpdatesWindow).__updatesListeners())).toBe(1);
}

async function showUpdates(page: Page) {
  await page.evaluate(() => (window as UpdatesWindow).__updatesMenu());
  await expect(page.getByRole("dialog")).toHaveAttribute("data-update-state", "available");
}

async function openerCalls(page: Page) {
  return page.evaluate(() => (window as UpdatesWindow).__updatesCalls.filter((entry) => entry.command === "desktop_open_releases"));
}

test("pending release opener times out honestly and ignores late completion after an explicit retry (mocked IPC)", async ({ page }) => {
  await mockUpdates(page);
  await showUpdates(page);
  await expect(page.getByRole("dialog")).toContainText("Versão deste aplicativo: 3.8.39");
  const subscriptions = await page.evaluate(() => (window as UpdatesWindow).__updatesCalls.filter((entry) => entry.command === "plugin:event|listen"));
  expect(subscriptions.every((entry) => JSON.stringify(entry.args.target) === JSON.stringify({ kind: "AnyLabel", label: "main" }))).toBe(true);
  await page.getByRole("button", { name: "Ver releases oficiais", exact: true }).dblclick();
  await expect(page.getByRole("button", { name: "Abrindo…", exact: true })).toBeDisabled();
  expect(await openerCalls(page)).toEqual([{ command: "desktop_open_releases", args: {} }]);

  await page.clock.fastForward(8_001);
  await expect(page.getByRole("alert")).toContainText("Não foi possível confirmar a abertura; confira o navegador.");
  await expect(page.getByRole("button", { name: "Ver releases oficiais", exact: true })).toBeEnabled();
  expect(await openerCalls(page)).toHaveLength(1);
  await page.getByRole("button", { name: "Ver releases oficiais", exact: true }).click();
  expect(await openerCalls(page)).toHaveLength(2);
  await page.evaluate(() => (window as UpdatesWindow).__updatesResolveOpen(0));
  await expect(page.getByRole("button", { name: "Abrindo…", exact: true })).toBeDisabled();
  await page.evaluate(() => (window as UpdatesWindow).__updatesResolveOpen(1));
  await expect(page.getByRole("button", { name: "Ver releases oficiais", exact: true })).toBeEnabled();
  await expect(page.getByRole("alert")).toHaveCount(0);
});

test("closing a pending opener preserves uncertainty on reopen and ignores its late rejection (mocked IPC)", async ({ page }) => {
  await mockUpdates(page);
  await showUpdates(page);
  await page.getByRole("button", { name: "Ver releases oficiais", exact: true }).click();
  await expect(page.getByRole("button", { name: "Abrindo…", exact: true })).toBeDisabled();
  await page.getByRole("button", { name: "Fechar atualizações", exact: true }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);

  await showUpdates(page);
  await expect(page.getByRole("alert")).toContainText("A tentativa anterior ainda pode concluir.");
  await expect(page.getByRole("button", { name: "Ver releases oficiais", exact: true })).toBeEnabled();
  await page.evaluate(() => (window as UpdatesWindow).__updatesRejectOpen(0));
  await expect(page.getByRole("alert")).toContainText("A tentativa anterior ainda pode concluir.");
  await page.clock.fastForward(8_001);
  await expect(page.getByRole("alert")).toContainText("Uma nova tentativa só será feita se você clicar novamente.");
  expect(await openerCalls(page)).toEqual([{ command: "desktop_open_releases", args: {} }]);
  await expect(page.getByRole("dialog")).toHaveAttribute("data-update-state", "available");
});
